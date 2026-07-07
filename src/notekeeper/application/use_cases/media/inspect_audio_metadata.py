"""Inspect audio metadata use case."""

from notekeeper.application.commands import InspectAudioMetadataCommand
from notekeeper.application.ports import AudioMetadataReader
from notekeeper.application.results import InspectAudioMetadataResult
from notekeeper.domain import ArtifactRef


class InspectAudioMetadata:
    def __init__(self, metadata_reader: AudioMetadataReader) -> None:
        self._metadata_reader = metadata_reader

    def execute(
        self,
        command: InspectAudioMetadataCommand,
    ) -> InspectAudioMetadataResult:
        artifact = ArtifactRef(
            uri=command.artifact_uri,
            kind=command.artifact_kind,
        )
        return InspectAudioMetadataResult(
            artifact=artifact,
            metadata=self._metadata_reader.read(artifact),
        )
