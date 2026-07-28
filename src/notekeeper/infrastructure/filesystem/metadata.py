"""Local audio metadata reader."""

from notekeeper.application.ports import AudioMetadataReader
from notekeeper.domain import ArtifactRef, AudioMetadata

from .storage import LocalCampaignArtifactStorage
from .utils import read_audio_metadata


class LocalAudioMetadataReader(AudioMetadataReader):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        *,
        ffprobe_path: str = "ffprobe",
    ) -> None:
        self._storage = storage
        self._ffprobe_path = ffprobe_path

    def read(self, artifact: ArtifactRef) -> AudioMetadata:
        path = self._storage.artifact_path(artifact)
        return read_audio_metadata(path, self._ffprobe_path)
