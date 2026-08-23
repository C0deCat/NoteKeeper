from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from notekeeper.application import (
    AuthorizationError,
    CreateCampaignCommand,
    CreateProcessingJobForAudioTrackCommand,
    InvalidCredentialsError,
    RestartProcessingJobCommand,
)
from notekeeper.composition import NoteKeeperSettings, build_local_host
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    VoiceSample,
    WorkspaceRole,
)


def _settings(tmp_path: Path, *, auth_enabled: bool = False) -> NoteKeeperSettings:
    return NoteKeeperSettings(
        _env_file=None,
        auth_enabled=auth_enabled,
        local_auth_users_path=tmp_path / "users.json",
        cli_auth_session_path=tmp_path / "session.json",
        storage_root=tmp_path / "artifacts",
        sqlite_path=tmp_path / "notekeeper.sqlite3",
        processing_work_root=tmp_path / "work",
        recap_prompts_template_path=Path("data") / "recap_prompts.json",
    )


def _service(runtime):
    service = runtime.use_cases.settings
    assert service is not None
    return service


def test_workspace_settings_inherit_persist_and_reset(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    runtime = build_local_host(settings).interactive_runtime()
    service = _service(runtime)

    inherited = service.get_workspace()
    assert inherited.inherited is True
    assert inherited.whisperx_model_name == "large-v3-turbo"

    updated = service.update_workspace(
        name="Shared games",
        whisperx_model_name="small",
        whisperx_language="ru",
        deepseek_model_name="deepseek-v4-flash",
        deepseek_temperature=1.3,
    )
    assert updated.inherited is False

    reloaded = build_local_host(settings).interactive_runtime()
    persisted = _service(reloaded).get_workspace()
    assert persisted.name == "Shared games"
    assert persisted.whisperx_model_name == "small"
    assert persisted.deepseek_temperature == 1.3

    reset = _service(reloaded).reset_workspace()
    assert reset.inherited is True
    assert reset.name == "Shared games"
    assert reset.whisperx_model_name == "large-v3-turbo"


def test_workspace_membership_switch_default_and_revocation(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path, auth_enabled=True))
    root = host.interactive_runtime()
    root.auth.login("root", "root")
    root_workspace_id = str(_service(root).get_workspace().workspace_id)

    alice = host.interactive_runtime()
    alice.auth.register("alice", "secret")
    alice_personal_id = str(_service(alice).get_workspace().workspace_id)

    _service(root).add_member("alice", WorkspaceRole.EDITOR)
    alice.switch_workspace(root_workspace_id)
    assert str(_service(alice).get_workspace().workspace_id) == root_workspace_id
    assert _service(alice).get_user().default_workspace_id is not None

    _service(root).update_member_role("alice", WorkspaceRole.VIEWER)
    with pytest.raises(AuthorizationError):
        alice.use_cases.campaigns.create.execute(CreateCampaignCommand(name="Denied"))

    _service(root).remove_member("alice")
    with pytest.raises(AuthorizationError):
        _ = alice.use_cases

    logged_in_again = host.interactive_runtime()
    logged_in_again.auth.login("alice", "secret")
    assert str(_service(logged_in_again).get_workspace().workspace_id) == alice_personal_id


def test_user_can_change_login_and_password(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path, auth_enabled=True))
    runtime = host.interactive_runtime()
    runtime.auth.register("alice", "secret")

    updated = runtime.auth.update_login("secret", "alice-renamed")
    assert updated.login == "alice-renamed"
    runtime.auth.update_password("secret", "new-secret")

    fresh = host.interactive_runtime()
    with pytest.raises(InvalidCredentialsError):
        fresh.auth.login("alice-renamed", "secret")
    assert fresh.auth.login("alice-renamed", "new-secret").login == "alice-renamed"


def test_processing_job_captures_and_restart_reuses_settings(tmp_path: Path) -> None:
    host = build_local_host(_settings(tmp_path))
    runtime = host.interactive_runtime()
    service = _service(runtime)
    workspace_id = service.get_workspace().workspace_id
    campaign_id = CampaignId("campaign-settings")
    participant = Participant(ParticipantId("participant-settings"), campaign_id, "A")
    sample = VoiceSample(
        "sample-settings",
        campaign_id,
        participant.id,
        ArtifactRef("sample.wav"),
        AudioMetadata(duration_seconds=1),
    )
    track = AudioTrack(
        AudioTrackId("track-settings"),
        campaign_id,
        ArtifactRef("track.wav"),
        AudioMetadata(duration_seconds=10),
    )
    campaign = Campaign(
        campaign_id,
        "Settings",
        workspace_id,
        (participant,),
        (sample,),
        (track,),
    )
    host.system_repositories.campaign_repository.save(campaign)
    host.system_repositories.participant_repository.save(participant)
    host.system_repositories.voice_sample_repository.save(sample)
    host.system_repositories.audio_track_repository.save(track)

    service.update_workspace(
        whisperx_model_name="small",
        whisperx_language="ru",
        deepseek_model_name="deepseek-v4-flash",
        deepseek_temperature=1.3,
    )
    service.update_campaign(
        str(campaign_id),
        chunk_recap_prompt="snapshot chunk",
        combine_chunks_prompt="snapshot combined",
    )
    created = runtime.use_cases.jobs.create.execute(
        CreateProcessingJobForAudioTrackCommand(audio_track_id=str(track.id))
    ).job
    assert created.settings_snapshot is not None
    assert created.settings_snapshot.whisperx_model_name == "small"
    assert created.settings_snapshot.chunk_recap_prompt == "snapshot chunk"

    failed = replace(
        created,
        status=JobStatus.FAILED,
        updated_at=created.updated_at + timedelta(seconds=1),
    )
    host.system_repositories.job_repository.save(failed)
    restarted = runtime.use_cases.jobs.restart.execute(
        RestartProcessingJobCommand(job_id=str(failed.id))
    ).job
    assert restarted.settings_snapshot == created.settings_snapshot
