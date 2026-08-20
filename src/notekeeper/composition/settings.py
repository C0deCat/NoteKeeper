"""Application settings."""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from notekeeper.infrastructure.filesystem.scanner import DEFAULT_AUDIO_EXTENSIONS


class NoteKeeperSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTEKEEPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    storage_root: Path = Field(default=Path("data") / "artifacts")
    sqlite_path: Path = Field(default=Path("data") / "notekeeper.sqlite3")
    auth_enabled: bool = False
    auth_provider: str = "local"
    local_auth_users_path: Path = Field(default=Path("data") / "users.json")
    cli_auth_session_path: Path = Field(default=Path("data") / "auth-session.json")
    audio_extensions: tuple[str, ...] = DEFAULT_AUDIO_EXTENSIONS
    ffmpeg_bin: Path | None = None
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    processing_work_root: Path = Field(default=Path("data") / "processing-work")
    max_concurrent_jobs: int = Field(default=4, ge=1)
    max_concurrent_gpu_jobs: int = Field(default=1, ge=1)
    normalized_audio_sample_rate_hz: int = 16000
    normalized_audio_channels: int = 1
    normalized_audio_codec: str = "pcm_s16le"
    normalized_audio_container: str = "wav"
    whisperx_model_name: str = "large-v3-turbo"
    whisperx_available_model_names: tuple[str, ...] = (
        "tiny",
        "base",
        "small",
        "medium",
        "large-v2",
        "large-v3",
        "large-v3-turbo",
    )
    whisperx_device: str = "cuda"
    whisperx_compute_type: str = "float16"
    whisperx_batch_size: int = 8
    whisperx_language: str | None = None
    whisperx_available_languages: tuple[str, ...] = (
        "auto",
        "af",
        "am",
        "ar",
        "as",
        "az",
        "ba",
        "be",
        "bg",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "cs",
        "cy",
        "da",
        "de",
        "el",
        "en",
        "es",
        "et",
        "eu",
        "fa",
        "fi",
        "fo",
        "fr",
        "gl",
        "gu",
        "ha",
        "haw",
        "he",
        "hi",
        "hr",
        "ht",
        "hu",
        "hy",
        "id",
        "is",
        "it",
        "ja",
        "jw",
        "ka",
        "kk",
        "km",
        "kn",
        "ko",
        "la",
        "lb",
        "ln",
        "lo",
        "lt",
        "lv",
        "mg",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "ne",
        "nl",
        "nn",
        "no",
        "oc",
        "pa",
        "pl",
        "ps",
        "pt",
        "ro",
        "ru",
        "sa",
        "sd",
        "si",
        "sk",
        "sl",
        "sn",
        "so",
        "sq",
        "sr",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "tk",
        "tl",
        "tr",
        "tt",
        "uk",
        "ur",
        "uz",
        "vi",
        "yi",
        "yo",
        "zh",
        "yue",
    )
    whisperx_vad_method: str = "pyannote"
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
    recap_chunk_token_target: int = Field(default=30_000, ge=1)
    recap_prompts_template_path: Path = Field(
        default=Path("data") / "recap_prompts.json"
    )
    deepseek_api_key: str | None = Field(default=None, repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_name: str = "deepseek-v4-pro"
    deepseek_available_model_names: tuple[str, ...] = (
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    )
    deepseek_temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    deepseek_timeout_seconds: float = 120.0
    deepseek_retry_count: int = 2
    deepseek_retry_backoff_seconds: float = 1.0
    deepseek_request_logging_enabled: bool = False
    deepseek_log_full_payloads: bool = False

    @model_validator(mode="after")
    def validate_job_capacity(self) -> "NoteKeeperSettings":
        if self.max_concurrent_gpu_jobs > self.max_concurrent_jobs:
            raise ValueError(
                "max_concurrent_gpu_jobs must not exceed max_concurrent_jobs"
            )
        self._validate_catalog(
            self.whisperx_available_model_names,
            self.whisperx_model_name,
            "whisperx_available_model_names",
        )
        self._validate_catalog(
            self.deepseek_available_model_names,
            self.deepseek_model_name,
            "deepseek_available_model_names",
        )
        language = self.whisperx_language or "auto"
        self._validate_catalog(
            self.whisperx_available_languages,
            language,
            "whisperx_available_languages",
        )
        if (
            abs(
                self.deepseek_temperature * 10
                - round(self.deepseek_temperature * 10)
            )
            > 1e-9
        ):
            raise ValueError("deepseek_temperature must use increments of 0.1")
        return self

    @staticmethod
    def _validate_catalog(values: tuple[str, ...], selected: str, field: str) -> None:
        if not values or any(not value.strip() for value in values):
            raise ValueError(f"{field} must contain non-empty values")
        if len(set(values)) != len(values):
            raise ValueError(f"{field} must contain unique values")
        if selected not in values:
            raise ValueError(f"selected value {selected!r} is not in {field}")
