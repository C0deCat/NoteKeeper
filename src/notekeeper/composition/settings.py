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
    ffprobe_path: str = "ffprobe"
