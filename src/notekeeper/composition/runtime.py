"""Runtime assembly for user interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from notekeeper.application import (
    AddParticipantToCampaign,
    AddVoiceSample,
    CancelProcessingJob,
    ClearFailedJobsForCampaign,
    CreateCampaign,
    CreateProcessingJobForAudioTrack,
    DeleteAudioTrack,
    DeleteCampaign,
    DeleteParticipant,
    DeleteProcessingJob,
    DeleteVoiceSample,
    ExportRecapMarkdown,
    ExportTranscriptMarkdown,
    GenerateRecap,
    GetCampaign,
    GetJobStatus,
    InspectAudioMetadata,
    InspectLocalAudioFile,
    ListAudioTracks,
    ListCampaigns,
    ListJobsForCampaign,
    ListJobsForCampaignCommand,
    ListParticipants,
    ListVoiceSamples,
    PreviewRecapMarkdown,
    PreviewTranscriptMarkdown,
    RegisterAudioTrack,
    RestartFailedProcessingJob,
    RestartProcessingJob,
    ReviewSpeakerMappings,
    RunProcessingJob,
    SubmitRecordingForProcessing,
    SyncCampaignFolder,
    UpdateAudioTrack,
    UpdateCampaign,
    UpdateParticipant,
)
from notekeeper.application.errors import ApplicationError
from notekeeper.application.ports import ProgressEventStream
from notekeeper.domain import ArtifactRef
from notekeeper.infrastructure.runtime import (
    InMemoryProgressEventHub,
    StreamingProgressTrackerFactory,
)
from notekeeper.interfaces import InterfaceRuntime, RuntimeDiagnostics, Stage1UseCases

from .factory import InfrastructureBundle, build_infrastructure
from .isolated_run_processing_job import IsolatedRunProcessingJob
from .job_pipeline import build_processing_pipeline
from .process_job_executor import LocalProcessJobExecutor
from .settings import NoteKeeperSettings


@dataclass(frozen=True, slots=True)
class NoteKeeperRuntime:
    settings: NoteKeeperSettings
    use_cases: Stage1UseCases
    infrastructure: InfrastructureBundle
    progress_events: ProgressEventStream

    def diagnostics(self, campaign_id: str | None = None) -> RuntimeDiagnostics:
        return RuntimeDiagnostics(
            storage_root=_path_text(self.settings.storage_root),
            sqlite_path=_path_text(self.settings.sqlite_path),
            processing_work_root=_path_text(self.settings.processing_work_root),
            recap_prompts_file=_path_text(self.settings.recap_prompts_file),
            whisperx_model_name=self.settings.whisperx_model_name,
            whisperx_device=self.settings.whisperx_device,
            whisperx_compute_type=self.settings.whisperx_compute_type,
            whisperx_vad_method=self.settings.whisperx_vad_method,
            deepseek_configured=bool(self.settings.deepseek_api_key),
            huggingface_configured=bool(self.settings.whisperx_hf_token),
            recent_messages=_recent_messages(self.use_cases, campaign_id),
        )

    def format_artifact_location(self, artifact: ArtifactRef) -> str:
        if artifact.kind != "file":
            return artifact.uri

        path_for_uri = getattr(
            self.infrastructure.artifact_storage,
            "path_for_uri",
            None,
        )
        if callable(path_for_uri):
            return str(path_for_uri(artifact.uri).resolve(strict=False))

        return str((self.settings.storage_root / Path(artifact.uri)).resolve(strict=False))


def build_runtime(settings: NoteKeeperSettings | None = None) -> NoteKeeperRuntime:
    infrastructure = build_infrastructure(settings)
    infrastructure.transient_audio_cleaner.clean_stale()
    progress_events = InMemoryProgressEventHub()
    return NoteKeeperRuntime(
        settings=infrastructure.settings,
        use_cases=build_stage1_use_cases(
            infrastructure,
            progress_events=progress_events,
        ),
        infrastructure=infrastructure,
        progress_events=progress_events,
    )


def build_stage1_use_cases(
    infrastructure: InfrastructureBundle,
    *,
    progress_events: InMemoryProgressEventHub | None = None,
) -> Stage1UseCases:
    progress_events = progress_events or InMemoryProgressEventHub()
    progress_tracker_factory = StreamingProgressTrackerFactory(progress_events)
    processing_pipeline = build_processing_pipeline(infrastructure)
    process_executor = LocalProcessJobExecutor(
        infrastructure.settings,
        infrastructure.job_repository,
        progress_events,
        infrastructure.transient_audio_cleaner,
    )
    restart_processing_job = RestartProcessingJob(
        infrastructure.campaign_repository,
        infrastructure.audio_track_repository,
        infrastructure.job_repository,
        infrastructure.clock,
        infrastructure.id_generator,
    )
    return Stage1UseCases(
        create_campaign=CreateCampaign(
            infrastructure.campaign_repository,
            infrastructure.id_generator,
            infrastructure.artifact_storage,
        ),
        get_campaign=GetCampaign(infrastructure.campaign_repository),
        list_campaigns=ListCampaigns(infrastructure.campaign_repository),
        update_campaign=UpdateCampaign(infrastructure.campaign_repository),
        delete_campaign=DeleteCampaign(
            infrastructure.campaign_repository,
            infrastructure.artifact_storage,
        ),
        add_participant=AddParticipantToCampaign(
            infrastructure.campaign_repository,
            infrastructure.id_generator,
        ),
        list_participants=ListParticipants(infrastructure.campaign_repository),
        update_participant=UpdateParticipant(infrastructure.campaign_repository),
        delete_participant=DeleteParticipant(infrastructure.campaign_repository),
        add_voice_sample=AddVoiceSample(
            infrastructure.campaign_repository,
            infrastructure.metadata_reader,
            infrastructure.source_metadata_reader,
            infrastructure.artifact_storage,
            infrastructure.id_generator,
        ),
        list_voice_samples=ListVoiceSamples(infrastructure.campaign_repository),
        delete_voice_sample=DeleteVoiceSample(infrastructure.campaign_repository),
        register_audio_track=RegisterAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.metadata_reader,
            infrastructure.id_generator,
            audio_normalizer=infrastructure.audio_normalizer,
            artifact_storage=infrastructure.artifact_storage,
        ),
        list_audio_tracks=ListAudioTracks(infrastructure.campaign_repository),
        update_audio_track=UpdateAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.metadata_reader,
            audio_normalizer=infrastructure.audio_normalizer,
            artifact_storage=infrastructure.artifact_storage,
        ),
        delete_audio_track=DeleteAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
        ),
        create_processing_job_for_audio_track=CreateProcessingJobForAudioTrack(
            infrastructure.campaign_repository,
            infrastructure.audio_track_repository,
            infrastructure.job_repository,
            infrastructure.clock,
            infrastructure.id_generator,
        ),
        submit_recording_for_processing=SubmitRecordingForProcessing(
            infrastructure.campaign_repository,
            infrastructure.audio_track_repository,
            infrastructure.job_repository,
            infrastructure.metadata_reader,
            infrastructure.source_metadata_reader,
            infrastructure.artifact_storage,
            infrastructure.clock,
            infrastructure.id_generator,
            audio_normalizer=infrastructure.audio_normalizer,
        ),
        run_processing_job=IsolatedRunProcessingJob(
            processing_pipeline,
            process_executor,
        ),
        restart_failed_processing_job=restart_processing_job,
        clear_failed_jobs_for_campaign=ClearFailedJobsForCampaign(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
            infrastructure.job_cleaner,
        ),
        delete_processing_job=DeleteProcessingJob(
            infrastructure.job_repository,
            infrastructure.job_cleaner,
        ),
        cancel_processing_job=CancelProcessingJob(
            infrastructure.job_repository,
            infrastructure.clock,
            process_executor,
        ),
        list_jobs_for_campaign=ListJobsForCampaign(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
        ),
        get_job_status=GetJobStatus(infrastructure.job_repository),
        review_speaker_mappings=ReviewSpeakerMappings(
            infrastructure.campaign_repository,
            infrastructure.transcript_repository,
            infrastructure.recap_repository,
            infrastructure.job_repository,
            infrastructure.speaker_mapping_repository,
            infrastructure.tokenizer,
            infrastructure.recap_generator,
            infrastructure.clock,
            infrastructure.id_generator,
            progress_tracker_factory=progress_tracker_factory,
        ),
        generate_recap=GenerateRecap(
            infrastructure.job_repository,
            infrastructure.transcript_repository,
            infrastructure.recap_repository,
            infrastructure.tokenizer,
            infrastructure.recap_generator,
            infrastructure.clock,
            infrastructure.id_generator,
            progress_tracker_factory=progress_tracker_factory,
        ),
        export_transcript_markdown=ExportTranscriptMarkdown(
            infrastructure.transcript_repository,
            infrastructure.artifact_storage,
        ),
        export_recap_markdown=ExportRecapMarkdown(
            infrastructure.recap_repository,
            infrastructure.artifact_storage,
        ),
        preview_transcript_markdown=PreviewTranscriptMarkdown(
            infrastructure.transcript_repository,
        ),
        preview_recap_markdown=PreviewRecapMarkdown(infrastructure.recap_repository),
        inspect_audio_metadata=InspectAudioMetadata(infrastructure.metadata_reader),
        inspect_local_audio_file=InspectLocalAudioFile(
            infrastructure.source_metadata_reader,
        ),
        sync_campaign_folder=SyncCampaignFolder(
            infrastructure.campaign_repository,
            infrastructure.job_repository,
            infrastructure.folder_scanner,
            infrastructure.metadata_reader,
            infrastructure.id_generator,
            audio_normalizer=infrastructure.audio_normalizer,
            artifact_storage=infrastructure.artifact_storage,
        ),
        restart_processing_job=restart_processing_job,
    )


def _recent_messages(
    use_cases: Stage1UseCases,
    campaign_id: str | None,
) -> tuple[str, ...]:
    if campaign_id is None:
        return ()

    try:
        jobs = use_cases.list_jobs_for_campaign.execute(
            ListJobsForCampaignCommand(campaign_id=campaign_id),
        ).jobs
    except ApplicationError as exc:
        return (str(exc),)

    messages: list[str] = []
    for job in reversed(jobs):
        if job.error_message:
            messages.append(f"{job.id}: {job.error_message}")
        for warning in job.warnings:
            messages.append(f"{job.id}: {warning.message}")
        if len(messages) >= 8:
            break
    return tuple(messages[:8])


def _path_text(path: Path) -> str:
    return str(path.resolve(strict=False))
