"""Metadata reader for local source audio files."""

from pathlib import Path

from notekeeper.application.ports import SourceAudioMetadataReader
from notekeeper.domain import AudioMetadata

from .utils import read_audio_metadata


class LocalSourceAudioMetadataReader(SourceAudioMetadataReader):
    def __init__(self, *, ffprobe_path: str = "ffprobe") -> None:
        self._ffprobe_path = ffprobe_path

    def read(self, source_path: Path) -> AudioMetadata:
        return read_audio_metadata(
            source_path.expanduser().resolve(strict=False),
            self._ffprobe_path,
        )
