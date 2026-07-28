"""Build audio metadata from a local filesystem path."""

from pathlib import Path

from notekeeper.domain import AudioMetadata
from notekeeper.infrastructure.errors import InfrastructureError

from .audio_probe import read_ffprobe, read_wave
from .checksum import sha256


def read_audio_metadata(path: Path, ffprobe_path: str) -> AudioMetadata:
    if not path.is_file():
        raise InfrastructureError(f"audio file does not exist: {path}")

    file_size = path.stat().st_size
    checksum = sha256(path)
    ffprobe = read_ffprobe(path, ffprobe_path)
    if ffprobe is None and path.suffix.casefold() == ".wav":
        ffprobe = read_wave(path)

    if ffprobe is None:
        raise InfrastructureError(f"could not read audio metadata: {path}")

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
