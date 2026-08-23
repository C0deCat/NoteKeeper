"""Infrastructure composition factory."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioProcessor,
    AudioRecordingNormalizer,
    CampaignArtifactStorage,
    CampaignFolderScanner,
    Clock,
    IdGenerator,
    JobCleaner,
    PreparedAudioManifestStore,
    ProgressEventSnapshotStore,
    RecapGenerator,
    RecapGuidances,
    SourceAudioMetadataReader,
    SpeakerIdentifier,
    Tokenizer,
    Transcriber,
    TransientAudioCleaner,
    UserPreferencesRepository,
    WorkspaceRepository,
    WorkspaceSettingsRepository,
)
from notekeeper.application import SYSTEM_SCOPE
from notekeeper.infrastructure.cleanup import (
    LocalJobCleaner,
    LocalTransientAudioCleaner,
)
from notekeeper.infrastructure.deepseek import (
    DeepSeekRecapGenerator,
    LocalDeepSeekRequestLogger,
    NoOpDeepSeekRequestLogger,
)
from notekeeper.infrastructure.ffmpeg import (
    FfmpegAudioProcessor,
    FfmpegRecordingNormalizer,
)
from notekeeper.infrastructure.filesystem import (
    JsonCampaignRecapGuidances,
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
    LocalPreparedAudioManifestStore,
    LocalSourceAudioMetadataReader,
)
from notekeeper.infrastructure.runtime import SystemClock, UuidGenerator
from notekeeper.infrastructure.speaker_mapping import SampleBasedSpeakerIdentifier
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteProgressEventSnapshotStore,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteSpeakerReviewSubmissionRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
    SQLiteWorkspaceRepository,
    SQLiteWorkspaceSettingsRepository,
    SQLiteUserPreferencesRepository,
)
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer
from notekeeper.infrastructure.whisperx import (
    LocalWhisperXPayloadStore,
    WhisperXTranscriber,
)

from .settings import NoteKeeperSettings
from .repositories import SystemRepositories

_FFMPEG_DLL_DIRECTORY_HANDLES: list[object] = []
_CONFIGURED_FFMPEG_DLL_DIRECTORIES: set[str] = set()


@dataclass(frozen=True, slots=True)
class LocalServices:
    settings: NoteKeeperSettings
    database: SQLiteDatabase
    repositories: SystemRepositories
    artifact_storage: CampaignArtifactStorage
    folder_scanner: CampaignFolderScanner
    metadata_reader: AudioMetadataReader
    source_metadata_reader: SourceAudioMetadataReader
    audio_normalizer: AudioRecordingNormalizer
    prepared_audio_manifest_store: PreparedAudioManifestStore
    progress_event_snapshot_store: ProgressEventSnapshotStore
    audio_processor: AudioProcessor
    transcriber: Transcriber
    speaker_identifier: SpeakerIdentifier
    tokenizer: Tokenizer
    recap_guidances: RecapGuidances
    recap_generator: RecapGenerator
    job_cleaner: JobCleaner
    transient_audio_cleaner: TransientAudioCleaner
    clock: Clock
    id_generator: IdGenerator
    workspace_repository: WorkspaceRepository
    workspace_settings_repository: WorkspaceSettingsRepository
    user_preferences_repository: UserPreferencesRepository


def build_local_services(
    settings: NoteKeeperSettings | None = None,
    *,
    on_gpu_phase_completed: Callable[[], None] | None = None,
) -> LocalServices:
    resolved_settings = settings or NoteKeeperSettings()
    _configure_ffmpeg_dll_directory(resolved_settings)
    database = SQLiteDatabase(resolved_settings.sqlite_path)
    database.initialize()

    artifact_storage = LocalCampaignArtifactStorage(resolved_settings.storage_root)
    folder_scanner = LocalCampaignFolderScanner(
        artifact_storage,
        audio_extensions=resolved_settings.audio_extensions,
    )
    metadata_reader = LocalAudioMetadataReader(
        artifact_storage,
        ffprobe_path=resolved_settings.ffprobe_path,
    )
    source_metadata_reader = LocalSourceAudioMetadataReader(
        ffprobe_path=resolved_settings.ffprobe_path,
    )
    audio_normalizer = FfmpegRecordingNormalizer(
        artifact_storage,
        ffmpeg_path=resolved_settings.ffmpeg_path,
        ffprobe_path=resolved_settings.ffprobe_path,
        sample_rate_hz=resolved_settings.normalized_audio_sample_rate_hz,
        channels=resolved_settings.normalized_audio_channels,
        codec=resolved_settings.normalized_audio_codec,
        container=resolved_settings.normalized_audio_container,
    )
    prepared_audio_manifest_store = LocalPreparedAudioManifestStore(artifact_storage)
    clock = SystemClock()
    id_generator = UuidGenerator()
    audio_processor = FfmpegAudioProcessor(
        artifact_storage,
        prepared_audio_manifest_store,
        ffmpeg_path=resolved_settings.ffmpeg_path,
        processing_work_root=resolved_settings.processing_work_root,
        sample_rate_hz=resolved_settings.normalized_audio_sample_rate_hz,
        channels=resolved_settings.normalized_audio_channels,
        codec=resolved_settings.normalized_audio_codec,
        container=resolved_settings.normalized_audio_container,
        now=clock.now,
    )
    transient_audio_cleaner = LocalTransientAudioCleaner(
        artifact_storage,
        resolved_settings.processing_work_root,
    )
    transcriber = WhisperXTranscriber(
        artifact_storage,
        LocalWhisperXPayloadStore(artifact_storage),
        model_name=resolved_settings.whisperx_model_name,
        device=resolved_settings.whisperx_device,
        compute_type=resolved_settings.whisperx_compute_type,
        batch_size=resolved_settings.whisperx_batch_size,
        language=resolved_settings.whisperx_language,
        vad_method=resolved_settings.whisperx_vad_method,
        alignment_enabled=resolved_settings.whisperx_alignment_enabled,
        alignment_model_name=resolved_settings.whisperx_alignment_model_name,
        alignment_model_dir=resolved_settings.whisperx_alignment_model_dir,
        alignment_model_cache_only=(
            resolved_settings.whisperx_alignment_model_cache_only
        ),
        diarization_enabled=resolved_settings.whisperx_diarization_enabled,
        diarization_model_name=resolved_settings.whisperx_diarization_model_name,
        diarization_cache_dir=resolved_settings.whisperx_diarization_cache_dir,
        hf_token=resolved_settings.whisperx_hf_token,
        fill_nearest=resolved_settings.whisperx_speaker_assignment_fill_nearest,
        unknown_speaker_label=resolved_settings.whisperx_unknown_speaker_label,
        on_gpu_phase_completed=on_gpu_phase_completed,
        now=clock.now,
    )
    speaker_identifier = SampleBasedSpeakerIdentifier(
        min_overlap_seconds=resolved_settings.speaker_mapping_min_overlap_seconds,
        min_dominance_ratio=resolved_settings.speaker_mapping_min_dominance_ratio,
    )
    tokenizer = TiktokenTranscriptTokenizer(
        encoding_name=resolved_settings.tokenizer_encoding_name,
        max_token_count=resolved_settings.tokenizer_max_token_count,
    )
    recap_guidances = JsonCampaignRecapGuidances(
        artifact_storage,
        resolved_settings.recap_prompts_template_path,
    )
    deepseek_request_logger = (
        LocalDeepSeekRequestLogger(
            artifact_storage,
            include_payloads=resolved_settings.deepseek_log_full_payloads,
            now=clock.now,
        )
        if resolved_settings.deepseek_request_logging_enabled
        else NoOpDeepSeekRequestLogger()
    )
    recap_generator = DeepSeekRecapGenerator(
        api_key=resolved_settings.deepseek_api_key,
        base_url=resolved_settings.deepseek_base_url,
        model_name=resolved_settings.deepseek_model_name,
        temperature=resolved_settings.deepseek_temperature,
        timeout_seconds=resolved_settings.deepseek_timeout_seconds,
        retry_count=resolved_settings.deepseek_retry_count,
        retry_backoff_seconds=resolved_settings.deepseek_retry_backoff_seconds,
        request_logger=deepseek_request_logger,
    )

    repositories = SystemRepositories(
        campaign_repository=SQLiteCampaignRepository(database, SYSTEM_SCOPE),
        participant_repository=SQLiteParticipantRepository(database, SYSTEM_SCOPE),
        voice_sample_repository=SQLiteVoiceSampleRepository(database, SYSTEM_SCOPE),
        audio_track_repository=SQLiteAudioTrackRepository(database, SYSTEM_SCOPE),
        transcript_repository=SQLiteTranscriptRepository(
            database, artifact_storage, SYSTEM_SCOPE
        ),
        recap_repository=SQLiteRecapRepository(
            database, artifact_storage, SYSTEM_SCOPE
        ),
        job_repository=SQLiteJobRepository(database, SYSTEM_SCOPE),
        speaker_mapping_repository=SQLiteSpeakerMappingRepository(
            database, SYSTEM_SCOPE
        ),
        speaker_review_submission_repository=(
            SQLiteSpeakerReviewSubmissionRepository(database, SYSTEM_SCOPE)
        ),
    )
    return LocalServices(
        settings=resolved_settings,
        database=database,
        repositories=repositories,
        artifact_storage=artifact_storage,
        folder_scanner=folder_scanner,
        metadata_reader=metadata_reader,
        source_metadata_reader=source_metadata_reader,
        audio_normalizer=audio_normalizer,
        prepared_audio_manifest_store=prepared_audio_manifest_store,
        progress_event_snapshot_store=SQLiteProgressEventSnapshotStore(database),
        audio_processor=audio_processor,
        transcriber=transcriber,
        speaker_identifier=speaker_identifier,
        tokenizer=tokenizer,
        recap_guidances=recap_guidances,
        recap_generator=recap_generator,
        job_cleaner=LocalJobCleaner(
            database,
            artifact_storage,
            resolved_settings.processing_work_root,
        ),
        transient_audio_cleaner=transient_audio_cleaner,
        clock=clock,
        id_generator=id_generator,
        workspace_repository=SQLiteWorkspaceRepository(database),
        workspace_settings_repository=SQLiteWorkspaceSettingsRepository(database),
        user_preferences_repository=SQLiteUserPreferencesRepository(database),
    )


__all__ = ["LocalServices", "build_local_services"]


def _configure_ffmpeg_dll_directory(settings: NoteKeeperSettings) -> None:
    if settings.ffmpeg_bin is None or os.name != "nt":
        return

    ffmpeg_bin = str(settings.ffmpeg_bin.resolve(strict=False))
    if ffmpeg_bin in _CONFIGURED_FFMPEG_DLL_DIRECTORIES:
        return

    handle = os.add_dll_directory(ffmpeg_bin)
    _FFMPEG_DLL_DIRECTORY_HANDLES.append(handle)
    _CONFIGURED_FFMPEG_DLL_DIRECTORIES.add(ffmpeg_bin)
