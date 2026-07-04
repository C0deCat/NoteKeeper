"""Infrastructure composition factory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from notekeeper.application.ports import (
    AudioMetadataReader,
    AudioProcessor,
    AudioTrackRepository,
    CampaignArtifactStorage,
    CampaignFolderScanner,
    CampaignRepository,
    Clock,
    IdGenerator,
    JobRepository,
    ParticipantRepository,
    PreparedAudioManifestStore,
    RecapGenerator,
    RecapRepository,
    SpeakerIdentifier,
    SpeakerMappingRepository,
    Tokenizer,
    Transcriber,
    TranscriptRepository,
    VoiceSampleRepository,
)
from notekeeper.infrastructure.deepseek import DeepSeekRecapGenerator
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalCampaignFolderScanner,
    LocalPreparedAudioManifestStore,
)
from notekeeper.infrastructure.runtime import SystemClock, UuidGenerator
from notekeeper.infrastructure.speaker_mapping import SampleBasedSpeakerIdentifier
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteParticipantRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteTranscriptRepository,
    SQLiteVoiceSampleRepository,
)
from notekeeper.infrastructure.whisperx import (
    LocalWhisperXPayloadStore,
    WhisperXTranscriber,
)
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer

from .settings import NoteKeeperSettings

CHUNK_RECAP_PROMPT_KEY = "chunk_recap_prompt"
COMBINE_CHUNKS_PROMPT_KEY = "combine_chunks_prompt"


@dataclass(frozen=True, slots=True)
class InfrastructureBundle:
    settings: NoteKeeperSettings
    artifact_storage: CampaignArtifactStorage
    folder_scanner: CampaignFolderScanner
    metadata_reader: AudioMetadataReader
    prepared_audio_manifest_store: PreparedAudioManifestStore
    audio_processor: AudioProcessor
    transcriber: Transcriber
    speaker_identifier: SpeakerIdentifier
    tokenizer: Tokenizer
    recap_generator: RecapGenerator
    campaign_repository: CampaignRepository
    participant_repository: ParticipantRepository
    voice_sample_repository: VoiceSampleRepository
    audio_track_repository: AudioTrackRepository
    transcript_repository: TranscriptRepository
    recap_repository: RecapRepository
    job_repository: JobRepository
    speaker_mapping_repository: SpeakerMappingRepository
    clock: Clock
    id_generator: IdGenerator


def build_infrastructure(
    settings: NoteKeeperSettings | None = None,
) -> InfrastructureBundle:
    resolved_settings = settings or NoteKeeperSettings()
    recap_prompts = _load_recap_prompts(resolved_settings.recap_prompts_file)
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
    prepared_audio_manifest_store = LocalPreparedAudioManifestStore(artifact_storage)
    clock = SystemClock()
    id_generator = UuidGenerator()
    audio_processor = FfmpegAudioProcessor(
        artifact_storage,
        prepared_audio_manifest_store,
        ffmpeg_path=resolved_settings.ffmpeg_path,
        processing_work_root=resolved_settings.processing_work_root,
        sample_rate_hz=resolved_settings.prepared_audio_sample_rate_hz,
        channels=resolved_settings.prepared_audio_channels,
        codec=resolved_settings.prepared_audio_codec,
        container=resolved_settings.prepared_audio_container,
        now=clock.now,
    )
    transcriber = WhisperXTranscriber(
        artifact_storage,
        LocalWhisperXPayloadStore(artifact_storage),
        model_name=resolved_settings.whisperx_model_name,
        device=resolved_settings.whisperx_device,
        compute_type=resolved_settings.whisperx_compute_type,
        batch_size=resolved_settings.whisperx_batch_size,
        language=resolved_settings.whisperx_language,
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
    recap_generator = DeepSeekRecapGenerator(
        chunk_recap_prompt=recap_prompts[CHUNK_RECAP_PROMPT_KEY],
        combine_chunks_prompt=recap_prompts[COMBINE_CHUNKS_PROMPT_KEY],
        api_key=resolved_settings.deepseek_api_key,
        base_url=resolved_settings.deepseek_base_url,
        model_name=resolved_settings.deepseek_model_name,
        temperature=resolved_settings.deepseek_temperature,
        timeout_seconds=resolved_settings.deepseek_timeout_seconds,
        retry_count=resolved_settings.deepseek_retry_count,
        retry_backoff_seconds=resolved_settings.deepseek_retry_backoff_seconds,
    )

    return InfrastructureBundle(
        settings=resolved_settings,
        artifact_storage=artifact_storage,
        folder_scanner=folder_scanner,
        metadata_reader=metadata_reader,
        prepared_audio_manifest_store=prepared_audio_manifest_store,
        audio_processor=audio_processor,
        transcriber=transcriber,
        speaker_identifier=speaker_identifier,
        tokenizer=tokenizer,
        recap_generator=recap_generator,
        campaign_repository=SQLiteCampaignRepository(database),
        participant_repository=SQLiteParticipantRepository(database),
        voice_sample_repository=SQLiteVoiceSampleRepository(database),
        audio_track_repository=SQLiteAudioTrackRepository(database),
        transcript_repository=SQLiteTranscriptRepository(database, artifact_storage),
        recap_repository=SQLiteRecapRepository(database, artifact_storage),
        job_repository=SQLiteJobRepository(database),
        speaker_mapping_repository=SQLiteSpeakerMappingRepository(database),
        clock=clock,
        id_generator=id_generator,
    )


def _load_recap_prompts(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise InfrastructureError(f"recap prompts file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InfrastructureError(f"could not read recap prompts file: {path}") from exc

    if not isinstance(payload, dict):
        raise InfrastructureError("recap prompts file must contain a JSON object")

    return {
        CHUNK_RECAP_PROMPT_KEY: _required_prompt(
            payload,
            CHUNK_RECAP_PROMPT_KEY,
        ),
        COMBINE_CHUNKS_PROMPT_KEY: _required_prompt(
            payload,
            COMBINE_CHUNKS_PROMPT_KEY,
        ),
    }


def _required_prompt(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InfrastructureError(f"recap prompts file is missing prompt: {key}")
    return value.strip()
