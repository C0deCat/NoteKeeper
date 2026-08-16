"""Persistence ports for domain entities and processing records."""

from typing import Protocol

from notekeeper.application.results import SpeakerMappingRecord, SpeakerReviewSubmission
from notekeeper.domain import (
    AudioTrack,
    AudioTrackId,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    ProcessingJob,
    ProcessingJobId,
    Recap,
    RecapId,
    Transcript,
    TranscriptId,
    VoiceSample,
    VoiceSampleId,
    UserId,
    Workspace,
    WorkspaceId,
    WorkspaceMembership,
)


class WorkspaceRepository(Protocol):
    def get(self, workspace_id: WorkspaceId) -> Workspace | None: ...

    def list_for_user(self, user_id: UserId) -> tuple[Workspace, ...]: ...

    def membership(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
    ) -> WorkspaceMembership | None: ...

    def ensure_personal(self, user_id: UserId, name: str) -> WorkspaceMembership: ...


class CampaignRepository(Protocol):
    def get(self, campaign_id: CampaignId) -> Campaign | None: ...

    def list(self) -> tuple[Campaign, ...]: ...

    def save(self, campaign: Campaign) -> None: ...

    def delete(self, campaign_id: CampaignId) -> None: ...


class ParticipantRepository(Protocol):
    def get(self, participant_id: ParticipantId) -> Participant | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[Participant, ...]: ...

    def save(self, participant: Participant) -> None: ...

    def delete(self, participant_id: ParticipantId) -> None: ...


class VoiceSampleRepository(Protocol):
    def get(self, voice_sample_id: VoiceSampleId) -> VoiceSample | None: ...

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> VoiceSample | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[VoiceSample, ...]: ...

    def list_for_participant(
        self,
        participant_id: ParticipantId,
    ) -> tuple[VoiceSample, ...]: ...

    def save(self, voice_sample: VoiceSample) -> None: ...

    def delete(self, voice_sample_id: VoiceSampleId) -> None: ...


class AudioTrackRepository(Protocol):
    def get(self, audio_track_id: AudioTrackId) -> AudioTrack | None: ...

    def get_by_artifact_uri(
        self,
        campaign_id: CampaignId,
        artifact_uri: str,
    ) -> AudioTrack | None: ...

    def list_for_campaign(self, campaign_id: CampaignId) -> tuple[AudioTrack, ...]: ...

    def save(self, audio_track: AudioTrack) -> None: ...

    def delete(self, audio_track_id: AudioTrackId) -> None: ...


class TranscriptRepository(Protocol):
    def get(self, transcript_id: TranscriptId) -> Transcript | None: ...

    def list_for_audio_track(
        self, audio_track_id: AudioTrackId
    ) -> tuple[Transcript, ...]: ...

    def save(self, transcript: Transcript) -> None: ...

    def delete(self, transcript_id: TranscriptId) -> None: ...


class RecapRepository(Protocol):
    def get(self, recap_id: RecapId) -> Recap | None: ...

    def list_for_transcript(self, transcript_id: TranscriptId) -> tuple[Recap, ...]: ...

    def save(self, recap: Recap) -> None: ...

    def delete(self, recap_id: RecapId) -> None: ...


class JobRepository(Protocol):
    def get(self, job_id: ProcessingJobId) -> ProcessingJob | None: ...

    def list_for_campaign(
        self, campaign_id: CampaignId
    ) -> tuple[ProcessingJob, ...]: ...

    def list_for_audio_track(
        self,
        audio_track_id: AudioTrackId,
    ) -> tuple[ProcessingJob, ...]: ...

    def list_by_statuses(
        self,
        statuses: tuple[JobStatus, ...],
    ) -> tuple[ProcessingJob, ...]: ...

    def has_for_campaign_with_statuses(
        self,
        campaign_id: CampaignId,
        statuses: tuple[JobStatus, ...],
    ) -> bool: ...

    def save(self, job: ProcessingJob) -> None: ...

    def save_if_status(
        self,
        job: ProcessingJob,
        expected_status: JobStatus,
    ) -> bool: ...

    def delete(self, job_id: ProcessingJobId) -> None: ...


class SpeakerMappingRepository(Protocol):
    def save_many(self, records: tuple[SpeakerMappingRecord, ...]) -> None: ...

    def list_for_job(
        self,
        job_id: ProcessingJobId,
    ) -> tuple[SpeakerMappingRecord, ...]: ...

    def list_for_transcript(
        self,
        transcript_id: TranscriptId,
    ) -> tuple[SpeakerMappingRecord, ...]: ...


class SpeakerReviewSubmissionRepository(Protocol):
    def get(
        self,
        job_id: ProcessingJobId,
    ) -> SpeakerReviewSubmission | None: ...

    def save(self, submission: SpeakerReviewSubmission) -> None: ...

    def delete(self, job_id: ProcessingJobId) -> None: ...
