"""Submit recording for processing use case."""

from notekeeper.application.commands import SubmitRecordingForProcessingCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioRecordingNormalizer,
    AudioTrackRepository,
    CampaignArtifactStorage,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
    SourceAudioMetadataReader,
)
from notekeeper.application.results import SubmitRecordingForProcessingResult
from notekeeper.application.use_cases.utils import (
    _require_campaign,
    delete_artifact_with_warning,
    resolve_audio_source,
)
from notekeeper.domain import (
    ArtifactRef,
    AudioTrack,
    AudioTrackId,
    CampaignId,
    JobStatus,
    ProcessingJob,
    ProcessingJobId,
    add_audio_track,
    ensure_campaign_ready_for_processing,
)


class SubmitRecordingForProcessing:
    def __init__(
        self,
        campaign_repository: CampaignRepository,
        audio_track_repository: AudioTrackRepository,
        job_repository: JobRepository,
        metadata_reader: AudioMetadataReader,
        source_metadata_reader: SourceAudioMetadataReader,
        artifact_storage: CampaignArtifactStorage,
        clock: Clock,
        id_generator: IdGenerator,
        *,
        audio_normalizer: AudioRecordingNormalizer,
    ) -> None:
        self._campaign_repository = campaign_repository
        self._audio_track_repository = audio_track_repository
        self._job_repository = job_repository
        self._metadata_reader = metadata_reader
        self._source_metadata_reader = source_metadata_reader
        self._artifact_storage = artifact_storage
        self._clock = clock
        self._id_generator = id_generator
        self._audio_normalizer = audio_normalizer

    def execute(
        self,
        command: SubmitRecordingForProcessingCommand,
    ) -> SubmitRecordingForProcessingResult:
        campaign = _require_campaign(
            self._campaign_repository,
            CampaignId(command.campaign_id),
        )
        ensure_campaign_ready_for_processing(campaign)

        artifact_uri, source_path = resolve_audio_source(
            command.artifact_uri,
            command.source_path,
        )
        audio_track_id = AudioTrackId(self._id_generator.audio_track_id())
        managed_source_artifact = None
        if source_path is not None:
            source_metadata = self._source_metadata_reader.read(source_path)
            normalized = self._audio_normalizer.normalize_source(
                campaign_id=campaign.id,
                audio_track_id=audio_track_id,
                source_path=source_path,
                source_metadata=source_metadata,
            )
        else:
            managed_source_artifact = ArtifactRef(
                uri=artifact_uri or "",
                kind=command.artifact_kind,
            )
            source_metadata = self._metadata_reader.read(managed_source_artifact)
            normalized = self._audio_normalizer.normalize_artifact(
                campaign_id=campaign.id,
                audio_track_id=audio_track_id,
                source_artifact=managed_source_artifact,
                source_metadata=source_metadata,
            )

        audio_track = AudioTrack(
            id=audio_track_id,
            campaign_id=campaign.id,
            artifact=normalized.audio_artifact,
            metadata=normalized.metadata,
            title=command.title,
        )
        updated_campaign = add_audio_track(campaign, audio_track)
        self._campaign_repository.save(updated_campaign)
        self._audio_track_repository.save(audio_track)

        now = self._clock.now()
        job = ProcessingJob(
            id=ProcessingJobId(self._id_generator.processing_job_id()),
            campaign_id=campaign.id,
            audio_track_id=audio_track.id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self._job_repository.save(job)
        cleanup_warnings = ()
        if (
            managed_source_artifact is not None
            and managed_source_artifact.uri != normalized.audio_artifact.uri
        ):
            cleanup_warnings = delete_artifact_with_warning(
                self._artifact_storage,
                managed_source_artifact,
            )
        return SubmitRecordingForProcessingResult(
            campaign=updated_campaign,
            audio_track=audio_track,
            job=job,
            normalized_count=1,
            bytes_freed=normalized.bytes_freed,
            cleanup_warnings=cleanup_warnings,
        )
