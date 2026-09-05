from __future__ import annotations

import asyncio
import wave
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from notekeeper.application import ProgressEvent, ProgressEventKind
from notekeeper.composition import (
    NoteKeeperSettings,
    build_local_api_runtime,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    ProgressBar,
    Recap,
    Transcript,
    WorkspaceRole,
)
from notekeeper.interfaces.api import create_api_app
from notekeeper.interfaces.api.routers.jobs import _event_stream


def _settings(tmp_path: Path, **overrides) -> NoteKeeperSettings:
    values = {
        "_env_file": None,
        "auth_enabled": True,
        "local_auth_users_path": tmp_path / "users.json",
        "storage_root": tmp_path / "artifacts",
        "sqlite_path": tmp_path / "notekeeper.sqlite3",
        "processing_work_root": tmp_path / "work",
    }
    values.update(overrides)
    return NoteKeeperSettings(**values)


@pytest.fixture
def runtime(tmp_path: Path):
    return build_local_api_runtime(_settings(tmp_path))


@pytest.fixture
def client(runtime):
    with TestClient(create_api_app(runtime), raise_server_exceptions=False) as value:
        yield value


def _login(client: TestClient, login: str = "root", password: str = "root"):
    response = client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _workspace_id(client: TestClient, token: str) -> str:
    response = client.get("/api/v1/workspaces", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["items"][0]["workspace_id"]


def _create_campaign(client: TestClient, token: str, workspace_id: str) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/campaigns",
        headers=_headers(token),
        json={"name": "Demo"},
    )
    assert response.status_code == 201
    assert response.headers["location"].endswith(response.json()["campaign_id"])
    return response.json()["campaign_id"]


def test_health_auth_rotation_logout_and_request_ids(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["profile"] == "local"
    assert health.headers["x-request-id"].startswith("req_")

    registered = client.post(
        "/api/v1/auth/register",
        json={"login": "alice", "password": "secret"},
    )
    assert registered.status_code == 201
    assert registered.headers["cache-control"] == "no-store"
    first = registered.json()

    me = client.get("/api/v1/me", headers=_headers(first["access_token"]))
    assert me.status_code == 200
    assert me.json()["login"] == "alice"
    assert me.json()["default_workspace_id"] is not None

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert refreshed.status_code == 200
    second = refreshed.json()
    assert second["access_token"] != first["access_token"]
    assert (
        client.get("/api/v1/me", headers=_headers(first["access_token"])).status_code
        == 401
    )
    replay = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["request_id"].startswith("req_")

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": second["refresh_token"]},
    )
    assert logout.status_code == 204
    assert (
        client.get("/api/v1/me", headers=_headers(second["access_token"])).status_code
        == 401
    )


def test_api_requires_enabled_auth(tmp_path: Path) -> None:
    settings = _settings(tmp_path, auth_enabled=False)
    with pytest.raises(ValueError, match="NOTEKEEPER_AUTH_ENABLED=true"):
        build_local_api_runtime(settings)


def test_campaign_participant_tenancy_and_live_roles(
    client: TestClient,
    runtime,
) -> None:
    root = _login(client)
    root_token = root["access_token"]
    root_workspace = _workspace_id(client, root_token)
    root_campaign = _create_campaign(client, root_token, root_workspace)

    alice_registration = client.post(
        "/api/v1/auth/register",
        json={"login": "alice", "password": "secret"},
    ).json()
    alice_token = alice_registration["access_token"]
    alice_workspace = _workspace_id(client, alice_token)
    assert alice_workspace != root_workspace

    hidden = client.get(
        f"/api/v1/workspaces/{alice_workspace}/campaigns/{root_campaign}",
        headers=_headers(alice_token),
    )
    assert hidden.status_code == 404
    inaccessible_workspace = client.get(
        f"/api/v1/workspaces/{alice_workspace}/campaigns",
        headers=_headers(root_token),
    )
    assert inaccessible_workspace.status_code == 404

    root_user = runtime.resolve_user(root_token)
    root_session = runtime.workspace_session(root_user, root_workspace)
    assert root_session.use_cases.settings is not None
    root_session.use_cases.settings.add_member("alice", WorkspaceRole.VIEWER)

    forbidden = client.post(
        f"/api/v1/workspaces/{root_workspace}/campaigns",
        headers=_headers(alice_token),
        json={"name": "Forbidden"},
    )
    assert forbidden.status_code == 403

    root_session.use_cases.settings.update_member_role("alice", WorkspaceRole.EDITOR)
    allowed = client.post(
        f"/api/v1/workspaces/{root_workspace}/campaigns",
        headers=_headers(alice_token),
        json={"name": "Allowed"},
    )
    assert allowed.status_code == 201

    root_session.use_cases.settings.remove_member("alice")
    revoked = client.get(
        f"/api/v1/workspaces/{root_workspace}/campaigns",
        headers=_headers(alice_token),
    )
    assert revoked.status_code == 404


def test_direct_job_transcript_recap_and_sse_ids_are_tenant_scoped(
    client: TestClient,
    runtime,
) -> None:
    root = _login(client)
    root_token = root["access_token"]
    root_workspace = _workspace_id(client, root_token)
    campaign_id = _create_campaign(client, root_token, root_workspace)
    now = datetime.now(timezone.utc)
    job = ProcessingJob(
        id="job-root",
        campaign_id=campaign_id,
        audio_track_id="recording-root",
        status=JobStatus.FAILED,
        created_at=now,
        updated_at=now,
        transcript_id="transcript-root",
        recap_id="recap-root",
        error_message="failed",
    )
    transcript = Transcript(
        id="transcript-root",
        campaign_id=campaign_id,
        audio_track_id="recording-root",
    )
    recap = Recap(
        id="recap-root",
        transcript_id=transcript.id,
        markdown="# Root recap",
    )
    runtime._host.system_repositories.job_repository.save(job)
    runtime._host.system_repositories.transcript_repository.save(transcript)
    runtime._host.system_repositories.recap_repository.save(recap)

    alice = client.post(
        "/api/v1/auth/register",
        json={"login": "alice", "password": "secret"},
    ).json()
    alice_token = alice["access_token"]
    alice_workspace = _workspace_id(client, alice_token)
    for suffix in (
        "jobs/job-root",
        "jobs/job-root/events",
        "transcripts/transcript-root",
        "recaps/recap-root",
    ):
        response = client.get(
            f"/api/v1/workspaces/{alice_workspace}/{suffix}",
            headers=_headers(alice_token),
        )
        assert response.status_code == 404

    events = client.get(
        f"/api/v1/workspaces/{root_workspace}/jobs/job-root/events",
        headers=_headers(root_token),
    )
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in events.text
    assert '"status":"failed"' in events.text
    assert "failed" not in client.get(
        f"/api/v1/workspaces/{root_workspace}/recaps/recap-root",
        headers=_headers(root_token),
    ).text


def test_multipart_uploads_queue_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_local_api_runtime(_settings(tmp_path))
    monkeypatch.setattr(runtime._host.job_manager, "enqueue", lambda job_id: None)
    monkeypatch.setattr(
        runtime._host.job_manager,
        "request_cancel",
        lambda job_id: None,
    )
    audio = tmp_path / "sample.wav"
    _write_wav(audio)
    with TestClient(create_api_app(runtime), raise_server_exceptions=False) as client:
        token = _login(client)["access_token"]
        workspace_id = _workspace_id(client, token)
        campaign_id = _create_campaign(client, token, workspace_id)
        participant = client.post(
            f"/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/participants",
            headers=_headers(token),
            json={"display_name": "Alice"},
        ).json()
        participant_id = participant["participant_id"]

        with audio.open("rb") as source:
            sample = client.post(
                f"/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}"
                f"/participants/{participant_id}/voice-samples",
                headers=_headers(token),
                files={"file": ("sample.wav", source, "audio/wav")},
            )
        assert sample.status_code == 201
        assert "uri" not in sample.text

        with audio.open("rb") as source:
            recording = client.post(
                f"/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings",
                headers=_headers(token),
                files={"file": ("recording.wav", source, "audio/wav")},
                data={"title": "Session"},
            )
        assert recording.status_code == 201
        payload = recording.json()
        assert payload["job"]["status"] == "pending"
        assert "uri" not in recording.text
        assert list(runtime.upload_directory.glob("*")) == []

        job_id = payload["job"]["job_id"]
        queued = client.post(
            f"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/queue",
            headers=_headers(token),
        )
        assert queued.status_code == 202
        assert queued.json()["status"] == "queued"
        assert queued.headers["location"].endswith(job_id)
        canceled = client.post(
            f"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/cancel",
            headers=_headers(token),
        )
        assert canceled.status_code == 200
        assert canceled.json()["status"] == "canceled"


def test_upload_validation_envelope_and_openapi(tmp_path: Path) -> None:
    runtime = build_local_api_runtime(_settings(tmp_path, api_upload_max_bytes=8))
    with TestClient(create_api_app(runtime), raise_server_exceptions=False) as client:
        token = _login(client)["access_token"]
        workspace_id = _workspace_id(client, token)
        campaign_id = _create_campaign(client, token, workspace_id)
        path = (
            f"/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings"
        )
        too_large = client.post(
            path,
            headers=_headers(token),
            files={"file": ("large.wav", b"0123456789", "audio/wav")},
        )
        assert too_large.status_code == 413
        assert too_large.json()["error"]["code"] == "payload_too_large"
        assert too_large.headers["x-request-id"].startswith("req_")

        unsupported = client.post(
            path,
            headers=_headers(token),
            files={"file": ("sample.txt", b"audio", "text/plain")},
        )
        assert unsupported.status_code == 415
        assert unsupported.json()["error"]["code"] == "unsupported_media_type"

        schema = client.get("/openapi.json").json()
        assert (
            "/api/v1/workspaces/{workspace_id}/jobs/{job_id}/events"
            in schema["paths"]
        )
        protected = schema["paths"][
            "/api/v1/workspaces/{workspace_id}/campaigns"
        ]["get"]
        assert protected["security"] == [{"NoteKeeperBearer": []}]
        recording_schema = schema["components"]["schemas"]["RecordingResponse"]
        assert "artifact" not in recording_schema["properties"]


def test_chunked_upload_is_stopped_by_stream_body_limit(tmp_path: Path) -> None:
    runtime = build_local_api_runtime(_settings(tmp_path, api_upload_max_bytes=8))
    with TestClient(create_api_app(runtime), raise_server_exceptions=False) as client:
        token = _login(client)["access_token"]
        workspace_id = _workspace_id(client, token)
        campaign_id = _create_campaign(client, token, workspace_id)
        boundary = "notekeeper-test-boundary"
        prefix = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="large.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode("ascii")
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/campaigns/{campaign_id}/recordings",
            content=(
                chunk
                for chunk in (prefix, b"x" * 600_000, b"y" * 600_000, suffix)
            ),
            headers={
                **_headers(token),
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )

        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"
        assert response.headers["x-request-id"].startswith("req_")


def test_sse_emits_progress_terminal_status_and_unsubscribes() -> None:
    now = datetime.now(timezone.utc)
    pending = ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="recording-1",
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    failed = ProcessingJob(
        id="job-1",
        campaign_id="campaign-1",
        audio_track_id="recording-1",
        status=JobStatus.FAILED,
        created_at=now,
        updated_at=now,
        error_message="failed",
    )
    stream = _FakeProgressStream()
    runtime = SimpleNamespace(
        progress_events=stream,
        sse_heartbeat_seconds=1.0,
    )
    session = SimpleNamespace(
        use_cases=SimpleNamespace(
            jobs=SimpleNamespace(
                get_status=_StaticUseCase(SimpleNamespace(job=failed)),
            )
        )
    )
    request = SimpleNamespace(is_disconnected=_always_connected)

    async def exercise() -> None:
        generator = _event_stream(request, session, runtime, pending)
        assert "event: status" in await anext(generator)
        stream.emit(
            ProgressEvent(
                operation_id="job-1",
                stage_index=1,
                stage_count=1,
                timing_available=True,
                kind=ProgressEventKind.FAILED,
                progress=ProgressBar(stage="transcribing"),
            )
        )
        assert "event: progress" in await anext(generator)
        terminal = await anext(generator)
        assert "event: status" in terminal
        assert '"status":"failed"' in terminal
        with pytest.raises(StopAsyncIteration):
            await anext(generator)

    asyncio.run(exercise())
    assert stream.unsubscribed is True


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 1600)


class _StaticUseCase:
    def __init__(self, result) -> None:
        self._result = result

    def execute(self, command):
        return self._result


class _FakeProgressStream:
    def __init__(self) -> None:
        self.listener = None
        self.unsubscribed = False

    def subscribe(self, operation_id, listener, *, replay_latest=True):
        self.listener = listener

        def unsubscribe() -> None:
            self.unsubscribed = True

        return unsubscribe

    def emit(self, event) -> None:
        assert self.listener is not None
        self.listener(event)


async def _always_connected() -> bool:
    return False
