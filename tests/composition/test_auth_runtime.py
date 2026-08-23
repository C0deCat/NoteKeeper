from datetime import datetime
from pathlib import Path

import pytest

from notekeeper.application import (
    CreateCampaignCommand,
    GetCampaignCommand,
    GetJobStatusCommand,
    ListCampaignsCommand,
    NotFoundError,
    PreviewRecapMarkdownCommand,
    PreviewTranscriptMarkdownCommand,
)
from notekeeper.composition import NoteKeeperSettings, build_local_host
from notekeeper.domain import JobStatus, ProcessingJob, Recap, Transcript


def _interactive_runtime(settings: NoteKeeperSettings):
    return build_local_host(settings).interactive_runtime()


def _settings(tmp_path: Path, *, auth_enabled: bool) -> NoteKeeperSettings:
    return NoteKeeperSettings(
        _env_file=None,
        auth_enabled=auth_enabled,
        local_auth_users_path=tmp_path / "users.json",
        cli_auth_session_path=tmp_path / "session.json",
        storage_root=tmp_path / "artifacts",
        sqlite_path=tmp_path / "notekeeper.sqlite3",
        processing_work_root=tmp_path / "work",
    )


def test_runtime_scopes_campaigns_and_direct_job_ids_by_current_user(
    tmp_path: Path,
) -> None:
    host = build_local_host(_settings(tmp_path, auth_enabled=True))
    runtime = host.interactive_runtime()
    runtime.auth.login("root", "root")
    root_campaign = runtime.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Root campaign")
    ).campaign

    runtime.auth.register("alice", "secret")
    alice_campaign = runtime.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Alice campaign")
    ).campaign
    foreign_job = ProcessingJob(
        id="root-job",
        campaign_id=root_campaign.id,
        audio_track_id="root-track",
        status=JobStatus.PENDING,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    host.system_repositories.job_repository.save(foreign_job)
    foreign_transcript = Transcript(
        id="root-transcript",
        campaign_id=root_campaign.id,
        audio_track_id="root-track",
    )
    foreign_recap = Recap(
        id="root-recap",
        transcript_id=foreign_transcript.id,
        markdown="Root recap",
    )
    host.system_repositories.transcript_repository.save(foreign_transcript)
    host.system_repositories.recap_repository.save(foreign_recap)

    assert alice_campaign.workspace_id == runtime.access.workspace_id
    assert alice_campaign.workspace_id != root_campaign.workspace_id
    assert runtime.use_cases.campaigns.list.execute(
        ListCampaignsCommand()
    ).campaigns == (alice_campaign,)
    with pytest.raises(NotFoundError):
        runtime.use_cases.campaigns.get.execute(
            GetCampaignCommand(campaign_id=str(root_campaign.id))
        )
    with pytest.raises(NotFoundError):
        runtime.use_cases.jobs.get_status.execute(
            GetJobStatusCommand(job_id=str(foreign_job.id))
        )
    with pytest.raises(NotFoundError):
        runtime.use_cases.transcripts.preview_markdown.execute(
            PreviewTranscriptMarkdownCommand(transcript_id=str(foreign_transcript.id))
        )
    with pytest.raises(NotFoundError):
        runtime.use_cases.recaps.preview_markdown.execute(
            PreviewRecapMarkdownCommand(recap_id=str(foreign_recap.id))
        )

    runtime.auth.login("root", "root")
    assert runtime.use_cases.campaigns.list.execute(
        ListCampaignsCommand()
    ).campaigns == (root_campaign,)
    assert (
        runtime.use_cases.jobs.get_status.execute(
            GetJobStatusCommand(job_id=str(foreign_job.id))
        ).job
        == foreign_job
    )


def test_disabled_auth_uses_root_without_creating_users_file(tmp_path: Path) -> None:
    runtime = _interactive_runtime(_settings(tmp_path, auth_enabled=False))
    campaign = runtime.use_cases.campaigns.create.execute(
        CreateCampaignCommand(name="Local")
    ).campaign

    assert runtime.auth.current_user is not None
    assert runtime.auth.current_user.login == "root"
    assert campaign.workspace_id == runtime.access.workspace_id
    assert not (tmp_path / "users.json").exists()
