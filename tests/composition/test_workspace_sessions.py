from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest

from notekeeper.application import (
    AuthorizationError,
    CreateCampaignCommand,
    ListCampaignsCommand,
    NotFoundError,
    PortExecutionError,
    QueueProcessingJobCommand,
    UpdateCampaignCommand,
)
from notekeeper.composition import (
    NoteKeeperSettings,
    build_application_session,
    build_local_host,
    build_worker_runtime,
)
from notekeeper.domain import (
    JobStatus,
    ProcessingJob,
    User,
    UserId,
    WorkspaceId,
)


def _settings(tmp_path: Path) -> NoteKeeperSettings:
    return NoteKeeperSettings(
        _env_file=None,
        auth_enabled=True,
        local_auth_users_path=tmp_path / "users.json",
        storage_root=tmp_path / "artifacts",
        sqlite_path=tmp_path / "notekeeper.sqlite3",
        processing_work_root=tmp_path / "work",
    )


def test_sessions_keep_workspace_state_isolated_on_one_host(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path))
    root = host.authenticate("root", "root")
    alice = host.register("alice", "secret")
    root_campaign = root.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Root")
    ).campaign
    alice_campaign = alice.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Alice")
    ).campaign

    with ThreadPoolExecutor(max_workers=2) as executor:
        root_result = executor.submit(
            root.use_cases.campaigns.list.execute,
            ListCampaignsCommand(),
        ).result()
        alice_result = executor.submit(
            alice.use_cases.campaigns.list.execute,
            ListCampaignsCommand(),
        ).result()

    assert root_result.campaigns == (root_campaign,)
    assert alice_result.campaigns == (alice_campaign,)
    assert root.access.workspace_id != alice.access.workspace_id


def test_dashboard_decorators_are_limited_to_local_interface_sessions(
    tmp_path: Path,
) -> None:
    host = build_local_host(_settings(tmp_path))
    received = []
    host.dashboard_events.subscribe(received.append)
    user = host.authenticator.authenticate("root", "root")

    request_session = build_application_session(host, user)
    request_session.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Request")
    )
    assert received == []

    local_session = host.authenticate("root", "root")
    local_session.use_cases.campaigns.create.execute(CreateCampaignCommand(name="Local"))
    assert len(received) == 1


def test_viewer_session_reads_but_cannot_mutate(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path))
    root = host.authenticate("root", "root")
    campaign = root.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Shared")
    ).campaign
    viewer = User(UserId("viewer-user"), "viewer")
    with host.services.database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_memberships (workspace_id, user_id, role)
            VALUES (?, ?, 'viewer')
            """,
            (str(root.access.workspace_id), str(viewer.id)),
        )
    session = build_application_session(host, viewer, root.access.workspace_id)

    assert session.use_cases.campaigns.list.execute(
        ListCampaignsCommand()
    ).campaigns == (campaign,)
    with pytest.raises(AuthorizationError):
        session.use_cases.campaigns.create.execute(CreateCampaignCommand(name="No"))
    with pytest.raises(AuthorizationError):
        session.use_cases.campaigns.update.execute(
            UpdateCampaignCommand(campaign_id=str(campaign.id), name="No")
        )
    with pytest.raises(AuthorizationError):
        session.use_cases.jobs.queue.execute(
            QueueProcessingJobCommand(job_id="missing")
        )


def test_editor_session_can_mutate_workspace_data(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path))
    root = host.authenticate("root", "root")
    campaign = root.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Shared")
    ).campaign
    editor = User(UserId("editor-user"), "editor")
    with host.services.database.connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_memberships (workspace_id, user_id, role)
            VALUES (?, ?, 'editor')
            """,
            (str(root.access.workspace_id), str(editor.id)),
        )

    session = build_application_session(host, editor, root.access.workspace_id)
    updated = session.use_cases.campaigns.update.execute(
        UpdateCampaignCommand(campaign_id=str(campaign.id), name="Edited")
    ).campaign

    assert updated.name == "Edited"


def test_foreign_active_job_does_not_leak_campaign_existence(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path))
    root = host.authenticate("root", "root")
    alice = host.register("alice", "secret")
    campaign = root.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Private")
    ).campaign
    host.system_repositories.job_repository.save(
        ProcessingJob(
            id="root-job",
            campaign_id=campaign.id,
            audio_track_id="track",
            status=JobStatus.RUNNING,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
    )

    with pytest.raises(NotFoundError, match="was not found"):
        alice.use_cases.campaigns.update.execute(
            UpdateCampaignCommand(campaign_id=str(campaign.id), name="Probe")
        )


def test_worker_rejects_mismatched_workspace_identity(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    host = build_local_host(settings)
    session = host.authenticate("root", "root")
    campaign = session.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Worker")
    ).campaign
    job = ProcessingJob(
        id="job",
        campaign_id=campaign.id,
        audio_track_id="track",
        status=JobStatus.QUEUED,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    host.system_repositories.job_repository.save(job)
    worker = build_worker_runtime(settings)

    with pytest.raises(PortExecutionError, match="does not belong"):
        worker.execute(WorkspaceId("another-workspace"), job.id)
