"""Local audio metadata reader."""

from notekeeper.application.ports import AudioMetadataReader
from notekeeper.domain import ArtifactRef, AudioMetadata

from ..errors import InfrastructureError
from .storage import LocalCampaignArtifactStorage
from .utils import read_ffprobe, read_wave, sha256


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
        if not path.is_file():
            raise InfrastructureError(f"audio artifact does not exist: {artifact.uri}")

        file_size = path.stat().st_size
        checksum = sha256(path)
        ffprobe = read_ffprobe(path, self._ffprobe_path)
        if ffprobe is None and path.suffix.casefold() == ".wav":
            ffprobe = read_wave(path)

        if ffprobe is None:
            raise InfrastructureError(f"could not read audio metadata: {artifact.uri}")

        return AudioMetadata(
            duration_seconds=ffprobe["duration_seconds"],
            sample_rate_hz=ffprobe.get("sample_rate_hz"),
            channels=ffprobe.get("channels"),
            codec=ffprobe.get("codec"),
            format=ffprobe.get("format"),
            bitrate_bps=ffprobe.get("bitrate_bps"),
            file_size_bytes=file_size,
            checksum=checksum,
        )
