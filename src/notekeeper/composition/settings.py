"""Application settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from notekeeper.infrastructure.filesystem.scanner import DEFAULT_AUDIO_EXTENSIONS


class NoteKeeperSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTEKEEPER_",
        arbitrary_types_allowed=True,
    )

    storage_root: Path = Field(default=Path("data") / "artifacts")
    sqlite_path: Path = Field(default=Path("data") / "notekeeper.sqlite3")
    audio_extensions: tuple[str, ...] = DEFAULT_AUDIO_EXTENSIONS
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    processing_work_root: Path = Field(default=Path("data") / "processing-work")
    prepared_audio_sample_rate_hz: int = 16000
    prepared_audio_channels: int = 1
    prepared_audio_codec: str = "pcm_s16le"
    prepared_audio_container: str = "wav"
    whisperx_model_name: str = "small"
    whisperx_device: str = "cpu"
    whisperx_compute_type: str = "int8"
    whisperx_batch_size: int = 16
    whisperx_language: str | None = None
    whisperx_alignment_enabled: bool = True
    whisperx_alignment_model_name: str | None = None
    whisperx_alignment_model_dir: Path | None = None
    whisperx_alignment_model_cache_only: bool = False
    whisperx_diarization_enabled: bool = True
    whisperx_diarization_model_name: str | None = None
    whisperx_diarization_cache_dir: Path | None = None
    whisperx_hf_token: str | None = Field(default=None, repr=False)
    whisperx_speaker_assignment_fill_nearest: bool = False
    whisperx_unknown_speaker_label: str = "SPEAKER_UNKNOWN"
    speaker_mapping_min_overlap_seconds: float = 0.25
    speaker_mapping_min_dominance_ratio: float = 0.8
    tokenizer_encoding_name: str = "cl100k_base"
    tokenizer_max_token_count: int = 35_000
    deepseek_api_key: str | None = Field(default=None, repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_name: str = "deepseek-v4-pro"
    deepseek_temperature: float = 0.2
    deepseek_timeout_seconds: float = 120.0
    deepseek_retry_count: int = 2
    deepseek_retry_backoff_seconds: float = 1.0
    deepseek_request_logging_enabled: bool = False
    deepseek_log_full_payloads: bool = False
    recap_prompts_file: Path = Field(default=Path("data") / "recap_prompts.json")
