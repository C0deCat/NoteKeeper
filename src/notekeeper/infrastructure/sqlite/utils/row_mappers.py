"""SQLite row-to-domain mappers."""

import json

from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    AudioTrackId,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    ProcessingJob,
    ProcessingJobId,
    RecapId,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
)

from .serialization import datetime_from_text, metadata_from_dict, warning_from_dict


def participant_from_row(row) -> Participant:
    return Participant(
        id=ParticipantId(row["id"]),
        campaign_id=CampaignId(row["campaign_id"]),
        display_name=row["display_name"],
    )


def voice_sample_from_row(row) -> VoiceSample:
    return VoiceSample(
        id=VoiceSampleId(row["id"]),
        campaign_id=CampaignId(row["campaign_id"]),
        participant_id=ParticipantId(row["participant_id"]),
        artifact=ArtifactRef(
            uri=row["artifact_uri"],
            kind=row["artifact_kind"],
            checksum=row["artifact_checksum"],
        ),
        metadata=metadata_from_dict(json.loads(row["metadata_json"])),
        recorded_at=(
            datetime_from_text(row["recorded_at"])
            if row["recorded_at"] is not None
            else None
        ),
    )


def audio_track_from_row(row) -> AudioTrack:
    return AudioTrack(
        id=AudioTrackId(row["id"]),
        campaign_id=CampaignId(row["campaign_id"]),
        artifact=ArtifactRef(
            uri=row["artifact_uri"],
            kind=row["artifact_kind"],
            checksum=row["artifact_checksum"],
        ),
        metadata=metadata_from_dict(json.loads(row["metadata_json"])),
        title=row["title"],
    )


def job_from_row(row) -> ProcessingJob:
    return ProcessingJob(
        id=ProcessingJobId(row["id"]),
        campaign_id=CampaignId(row["campaign_id"]),
        audio_track_id=AudioTrackId(row["audio_track_id"]),
        status=JobStatus(row["status"]),
        created_at=datetime_from_text(row["created_at"]),
        updated_at=datetime_from_text(row["updated_at"]),
        transcript_id=(
            TranscriptId(row["transcript_id"])
            if row["transcript_id"] is not None
            else None
        ),
        recap_id=RecapId(row["recap_id"]) if row["recap_id"] is not None else None,
        warnings=tuple(
            warning_from_dict(warning)
            for warning in json.loads(row["warnings_json"])
        ),
        error_message=row["error_message"],
    )
