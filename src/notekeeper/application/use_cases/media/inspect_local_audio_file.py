"""Inspect a local source audio file before it is imported."""

from pathlib import Path

from notekeeper.application.commands import InspectLocalAudioFileCommand
from notekeeper.application.ports import SourceAudioMetadataReader
from notekeeper.application.results import InspectLocalAudioFileResult


class InspectLocalAudioFile:
    def __init__(self, metadata_reader: SourceAudioMetadataReader) -> None:
        self._metadata_reader = metadata_reader

    def execute(
        self,
        command: InspectLocalAudioFileCommand,
    ) -> InspectLocalAudioFileResult:
        source_path = Path(command.source_path).expanduser().resolve(strict=False)
        return InspectLocalAudioFileResult(
            source_path=str(source_path),
            metadata=self._metadata_reader.read(source_path),
        )
