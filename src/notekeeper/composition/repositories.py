"""Typed repository sets used at composition boundaries."""

from dataclasses import dataclass

from notekeeper.application.ports import (
    AudioTrackRepository,
    CampaignRepository,
    JobRepository,
    ParticipantRepository,
    RecapRepository,
    SpeakerMappingRepository,
    SpeakerReviewSubmissionRepository,
    TranscriptRepository,
    VoiceSampleRepository,
)


@dataclass(frozen=True, slots=True)
class RepositorySet:
    campaign_repository: CampaignRepository
    participant_repository: ParticipantRepository
    voice_sample_repository: VoiceSampleRepository
    audio_track_repository: AudioTrackRepository
    transcript_repository: TranscriptRepository
    recap_repository: RecapRepository
    job_repository: JobRepository
    speaker_mapping_repository: SpeakerMappingRepository
    speaker_review_submission_repository: SpeakerReviewSubmissionRepository


@dataclass(frozen=True, slots=True)
class SystemRepositories(RepositorySet):
    """Trusted repositories available to local infrastructure and workers."""


@dataclass(frozen=True, slots=True)
class WorkspaceRepositories(RepositorySet):
    """Repositories permanently constrained to one workspace."""


__all__ = ["RepositorySet", "SystemRepositories", "WorkspaceRepositories"]
