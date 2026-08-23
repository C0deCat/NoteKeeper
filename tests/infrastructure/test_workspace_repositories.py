from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from notekeeper.application import PortExecutionError, SYSTEM_SCOPE, WorkspaceScope
from notekeeper.application.results import SpeakerMappingRecord, SpeakerReviewSubmission
from notekeeper.domain import (
    ArtifactRef,
    AudioMetadata,
    AudioTrack,
    Campaign,
    JobStatus,
    Participant,
    ProcessingJob,
    Recap,
    SpeakerLabel,
    SpeakerMapping,
    SpeakerMappingSource,
    SpeakerMappingStatus,
    Transcript,
    UserId,
    VoiceSample,
    WorkspaceId,
)
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteSpeakerReviewSubmissionRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
    SQLiteWorkspaceRepository,
)


def test_workspace_scope_applies_to_every_repository_family(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    workspaces = SQLiteWorkspaceRepository(database)
    workspace_a = workspaces.ensure_personal(UserId("user-a"), "A").workspace_id
    workspace_b = workspaces.ensure_personal(UserId("user-b"), "B").workspace_id
    values_a = _values("a", workspace_a)
    values_b = _values("b", workspace_b)
    system = _repositories(database, storage, SYSTEM_SCOPE)
    for values in (values_a, values_b):
        system["campaigns"].save(values["campaign"])
        system["jobs"].save(values["job"])
        system["transcripts"].save(values["transcript"])
        system["recaps"].save(values["recap"])
        system["mappings"].save_many((values["mapping"],))
        system["reviews"].save(values["review"])

    scoped = _repositories(database, storage, WorkspaceScope(workspace_a))

    assert scoped["campaigns"].list() == (values_a["campaign"],)
    assert scoped["campaigns"].get(values_b["campaign"].id) is None
    assert scoped["participants"].get(values_b["participant"].id) is None
    assert scoped["participants"].list_for_campaign(values_b["campaign"].id) == ()
    assert scoped["samples"].get(values_b["sample"].id) is None
    assert (
        scoped["samples"].get_by_artifact_uri(
            values_b["campaign"].id,
            values_b["sample"].artifact.uri,
        )
        is None
    )
    assert scoped["samples"].list_for_campaign(values_b["campaign"].id) == ()
    assert scoped["samples"].list_for_participant(values_b["participant"].id) == ()
    assert scoped["tracks"].get(values_b["track"].id) is None
    assert (
        scoped["tracks"].get_by_artifact_uri(
            values_b["campaign"].id,
            values_b["track"].artifact.uri,
        )
        is None
    )
    assert scoped["tracks"].list_for_campaign(values_b["campaign"].id) == ()
    assert scoped["jobs"].get(values_b["job"].id) is None
    assert scoped["jobs"].list_for_campaign(values_b["campaign"].id) == ()
    assert scoped["jobs"].list_for_audio_track(values_b["track"].id) == ()
    assert scoped["jobs"].list_by_statuses((JobStatus.COMPLETED,)) == (
        values_a["job"],
    )
    assert not scoped["jobs"].has_for_campaign_with_statuses(
        values_b["campaign"].id,
        (JobStatus.COMPLETED,),
    )
    assert scoped["transcripts"].get(values_b["transcript"].id) is None
    assert scoped["transcripts"].list_for_audio_track(values_b["track"].id) == ()
    assert scoped["recaps"].get(values_b["recap"].id) is None
    assert scoped["recaps"].list_for_transcript(values_b["transcript"].id) == ()
    assert scoped["mappings"].list_for_job(values_b["job"].id) == ()
    assert scoped["mappings"].list_for_transcript(values_b["transcript"].id) == ()
    assert scoped["reviews"].get(values_b["job"].id) is None

    with pytest.raises(PortExecutionError):
        scoped["campaigns"].save(
            replace(values_b["campaign"], workspace_id=workspace_a)
        )
    for repository_name, value_name in (
        ("participants", "participant"),
        ("samples", "sample"),
        ("tracks", "track"),
        ("jobs", "job"),
        ("transcripts", "transcript"),
    ):
        with pytest.raises(InfrastructureError, match="outside repository scope"):
            scoped[repository_name].save(values_b[value_name])
    hijacked_values = {
        "participants": replace(
            values_b["participant"],
            campaign_id=values_a["campaign"].id,
        ),
        "samples": replace(
            values_b["sample"],
            campaign_id=values_a["campaign"].id,
            participant_id=values_a["participant"].id,
        ),
        "tracks": replace(
            values_b["track"],
            campaign_id=values_a["campaign"].id,
        ),
        "jobs": replace(
            values_b["job"],
            campaign_id=values_a["campaign"].id,
            audio_track_id=values_a["track"].id,
        ),
        "transcripts": replace(
            values_b["transcript"],
            campaign_id=values_a["campaign"].id,
            audio_track_id=values_a["track"].id,
        ),
        "recaps": replace(
            values_b["recap"],
            transcript_id=values_a["transcript"].id,
        ),
    }
    for repository_name, value in hijacked_values.items():
        with pytest.raises(InfrastructureError, match="outside repository scope"):
            scoped[repository_name].save(value)
    with pytest.raises(InfrastructureError, match="outside repository scope"):
        scoped["campaigns"].save(
            replace(
                values_a["campaign"],
                participants=(hijacked_values["participants"],),
                voice_samples=(),
                audio_tracks=(),
            )
        )
    with pytest.raises(InfrastructureError, match="missing transcript"):
        scoped["recaps"].save(values_b["recap"])
    with pytest.raises(InfrastructureError, match="outside repository scope"):
        scoped["mappings"].save_many((values_b["mapping"],))
    with pytest.raises(InfrastructureError, match="outside repository scope"):
        scoped["reviews"].save(values_b["review"])
    assert not scoped["jobs"].save_if_status(
        replace(values_b["job"], status=JobStatus.FAILED),
        JobStatus.COMPLETED,
    )

    scoped["campaigns"].delete(values_b["campaign"].id)
    scoped["participants"].delete(values_b["participant"].id)
    scoped["samples"].delete(values_b["sample"].id)
    scoped["tracks"].delete(values_b["track"].id)
    scoped["jobs"].delete(values_b["job"].id)
    scoped["transcripts"].delete(values_b["transcript"].id)
    scoped["recaps"].delete(values_b["recap"].id)
    scoped["reviews"].delete(values_b["job"].id)

    assert system["campaigns"].get(values_b["campaign"].id) == values_b["campaign"]
    assert system["participants"].get(values_b["participant"].id) is not None
    assert system["samples"].get(values_b["sample"].id) is not None
    assert system["tracks"].get(values_b["track"].id) is not None
    assert system["jobs"].get(values_b["job"].id) == values_b["job"]
    assert system["transcripts"].get(values_b["transcript"].id) is not None
    assert system["recaps"].get(values_b["recap"].id) is not None
    assert system["reviews"].get(values_b["job"].id) is not None


def _repositories(database, storage, scope):
    return {
        "campaigns": SQLiteCampaignRepository(database, scope),
        "participants": SQLiteParticipantRepository(database, scope),
        "samples": SQLiteVoiceSampleRepository(database, scope),
        "tracks": SQLiteAudioTrackRepository(database, scope),
        "jobs": SQLiteJobRepository(database, scope),
        "transcripts": SQLiteTranscriptRepository(database, storage, scope),
        "recaps": SQLiteRecapRepository(database, storage, scope),
        "mappings": SQLiteSpeakerMappingRepository(database, scope),
        "reviews": SQLiteSpeakerReviewSubmissionRepository(database, scope),
    }


def _values(suffix: str, workspace_id: WorkspaceId):
    campaign_id = f"campaign-{suffix}"
    participant = Participant(f"participant-{suffix}", campaign_id, suffix.upper())
    metadata = AudioMetadata(duration_seconds=1.0)
    sample = VoiceSample(
        f"sample-{suffix}",
        campaign_id,
        participant.id,
        ArtifactRef(f"{campaign_id}/sample.wav"),
        metadata,
    )
    track = AudioTrack(
        f"track-{suffix}",
        campaign_id,
        ArtifactRef(f"{campaign_id}/track.wav"),
        metadata,
    )
    campaign = Campaign(
        campaign_id,
        suffix.upper(),
        workspace_id,
        (participant,),
        (sample,),
        (track,),
    )
    job = ProcessingJob(
        f"job-{suffix}",
        campaign_id,
        track.id,
        JobStatus.COMPLETED,
        datetime(2026, 1, 1),
        datetime(2026, 1, 1),
    )
    transcript = Transcript(f"transcript-{suffix}", campaign_id, track.id)
    recap = Recap(f"recap-{suffix}", transcript.id, f"# {suffix}")
    speaker_mapping = SpeakerMapping(
        anonymous_label=SpeakerLabel.anonymous("SPEAKER_00"),
        named_label=SpeakerLabel.named(suffix.upper()),
        participant_id=participant.id,
        confidence=1.0,
        source=SpeakerMappingSource.MANUAL,
        status=SpeakerMappingStatus.CONFIRMED,
    )
    mapping = SpeakerMappingRecord(job.id, transcript.id, speaker_mapping, {})
    review = SpeakerReviewSubmission(job.id, transcript.id, (speaker_mapping,))
    return {
        "campaign": campaign,
        "participant": participant,
        "sample": sample,
        "track": track,
        "job": job,
        "transcript": transcript,
        "recap": recap,
        "mapping": mapping,
        "review": review,
    }
