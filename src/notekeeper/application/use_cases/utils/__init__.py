"""Shared application use-case lookup helpers."""

from .audio_sources import resolve_audio_source
from .artifact_cleanup import delete_artifact_with_warning

from notekeeper.application.errors import NotFoundError
from notekeeper.application.ports import (
    AudioTrackRepository,
    CampaignRepository,
    JobRepository,
    RecapRepository,
    TranscriptRepository,
)
from notekeeper.domain import (
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapId,
    Transcript,
    TranscriptId,
)


def _require_campaign(
    campaign_repository: CampaignRepository,
    campaign_id: CampaignId,
) -> Campaign:
    campaign = campaign_repository.get(campaign_id)
    if campaign is None:
        raise NotFoundError(f"campaign {campaign_id} was not found")
    return campaign


def _require_audio_track(
    audio_track_repository: AudioTrackRepository,
    audio_track_id: AudioTrackId,
) -> AudioTrack:
    audio_track = audio_track_repository.get(audio_track_id)
    if audio_track is None:
        raise NotFoundError(f"audio track {audio_track_id} was not found")
    return audio_track


def _require_transcript(
    transcript_repository: TranscriptRepository,
    transcript_id: TranscriptId,
) -> Transcript:
    transcript = transcript_repository.get(transcript_id)
    if transcript is None:
        raise NotFoundError(f"transcript {transcript_id} was not found")
    return transcript


def _require_job(
    job_repository: JobRepository,
    job_id: ProcessingJobId,
) -> ProcessingJob:
    job = job_repository.get(job_id)
    if job is None:
        raise NotFoundError(f"processing job {job_id} was not found")
    return job


def _require_recap(
    recap_repository: RecapRepository,
    recap_id: RecapId,
) -> Recap:
    recap = recap_repository.get(recap_id)
    if recap is None:
        raise NotFoundError(f"recap {recap_id} was not found")
    return recap


__all__ = [
    "_require_audio_track",
    "_require_campaign",
    "_require_job",
    "_require_recap",
    "_require_transcript",
    "delete_artifact_with_warning",
    "resolve_audio_source",
]
