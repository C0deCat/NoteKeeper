"""Submit recording for processing use case."""

from notekeeper.application.commands import SubmitRecordingForProcessingCommand
from notekeeper.application.ports import (
    AudioMetadataReader,
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
    ) -> None:
        self._campaign_repository = campaign_repository
        self._audio_track_repository = audio_track_repository
        self._job_repository = job_repository
        self._metadata_reader = metadata_reader
        self._source_metadata_reader = source_metadata_reader
        self._artifact_storage = artifact_storage
        self._clock = clock
        self._id_generator = id_generator

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
        if source_path is not None:
            metadata = self._source_metadata_reader.read(source_path)
            artifact = self._artifact_storage.import_file(
                campaign_id=campaign.id,
                folder="records",
                source_path=source_path,
            )
        else:
            artifact = ArtifactRef(
                uri=artifact_uri or "",
                kind=command.artifact_kind,
            )
            metadata = self._metadata_reader.read(artifact)

        audio_track = AudioTrack(
            id=AudioTrackId(self._id_generator.audio_track_id()),
            campaign_id=campaign.id,
            artifact=artifact,
            metadata=metadata,
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
        return SubmitRecordingForProcessingResult(
            campaign=updated_campaign,
            audio_track=audio_track,
            job=job,
        )
