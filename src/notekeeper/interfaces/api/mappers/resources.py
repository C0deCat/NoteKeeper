"""Map domain and application values to stable API response DTOs."""

from __future__ import annotations

from notekeeper.application import ProgressEvent
from notekeeper.domain import (
    AudioMetadata,
    AudioTrack,
    Campaign,
    Participant,
    PipelineWarning,
    ProcessingJob,
    VoiceSample,
)

from ..schemas import (
    AudioMetadataResponse,
    CampaignResponse,
    JobResponse,
    ParticipantResponse,
    ProgressResponse,
    RecordingResponse,
    TimeRangeResponse,
    VoiceSampleResponse,
    WarningResponse,
)


def campaign_response(campaign: Campaign) -> CampaignResponse:
    return CampaignResponse(
        campaign_id=str(campaign.id),
        workspace_id=str(campaign.workspace_id),
        name=campaign.name,
    )


def participant_response(participant: Participant) -> ParticipantResponse:
    return ParticipantResponse(
        participant_id=str(participant.id),
        campaign_id=str(participant.campaign_id),
        display_name=participant.display_name,
    )


def voice_sample_response(sample: VoiceSample) -> VoiceSampleResponse:
    return VoiceSampleResponse(
        sample_id=str(sample.id),
        campaign_id=str(sample.campaign_id),
        participant_id=str(sample.participant_id),
        recorded_at=sample.recorded_at,
        metadata=audio_metadata_response(sample.metadata),
    )


def recording_response(recording: AudioTrack) -> RecordingResponse:
    return RecordingResponse(
        recording_id=str(recording.id),
        campaign_id=str(recording.campaign_id),
        title=recording.title,
        metadata=audio_metadata_response(recording.metadata),
    )


def audio_metadata_response(metadata: AudioMetadata) -> AudioMetadataResponse:
    return AudioMetadataResponse(
        duration_seconds=metadata.duration_seconds,
        sample_rate_hz=metadata.sample_rate_hz,
        channels=metadata.channels,
        codec=metadata.codec,
        format=metadata.format,
        bitrate_bps=metadata.bitrate_bps,
        file_size_bytes=metadata.file_size_bytes,
        checksum=metadata.checksum,
    )


def job_response(
    job: ProcessingJob,
    progress: ProgressEvent | None = None,
) -> JobResponse:
    return JobResponse(
        job_id=str(job.id),
        campaign_id=str(job.campaign_id),
        recording_id=str(job.audio_track_id),
        status=job.status.value,
        created_at=job.created_at,
        updated_at=job.updated_at,
        transcript_id=str(job.transcript_id) if job.transcript_id else None,
        recap_id=str(job.recap_id) if job.recap_id else None,
        warnings=[warning_response(value) for value in job.warnings],
        error_message=job.error_message,
        progress=progress_response(progress) if progress is not None else None,
    )


def warning_response(warning: PipelineWarning) -> WarningResponse:
    return WarningResponse(
        kind=warning.kind.value,
        message=warning.message,
        time_range=(
            TimeRangeResponse(
                start_seconds=warning.time_range.start_seconds,
                end_seconds=warning.time_range.end_seconds,
            )
            if warning.time_range is not None
            else None
        ),
        speaker_label=(
            warning.speaker_label.value if warning.speaker_label is not None else None
        ),
        participant_id=(
            str(warning.participant_id) if warning.participant_id is not None else None
        ),
    )


def progress_response(event: ProgressEvent) -> ProgressResponse:
    return ProgressResponse(
        operation_id=event.operation_id,
        kind=event.kind.value,
        stage_index=event.stage_index,
        stage_count=event.stage_count,
        timing_available=event.timing_available,
        stage=event.progress.stage,
        percent=event.progress.percent,
        expected_duration=event.progress.expected_duration,
        current_duration=event.progress.current_duration,
        remaining_duration=event.progress.remaining_duration,
    )


__all__ = [
    "audio_metadata_response",
    "campaign_response",
    "job_response",
    "participant_response",
    "progress_response",
    "recording_response",
    "voice_sample_response",
    "warning_response",
]
