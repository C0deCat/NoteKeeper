"""Audio metadata serialization."""

from typing import Any

from notekeeper.domain import AudioMetadata


def metadata_to_dict(metadata: AudioMetadata) -> dict[str, Any]:
    return {
        "duration_seconds": metadata.duration_seconds,
        "sample_rate_hz": metadata.sample_rate_hz,
        "channels": metadata.channels,
        "codec": metadata.codec,
        "format": metadata.format,
        "bitrate_bps": metadata.bitrate_bps,
        "file_size_bytes": metadata.file_size_bytes,
        "checksum": metadata.checksum,
    }


def metadata_from_dict(payload: dict[str, Any]) -> AudioMetadata:
    return AudioMetadata(
        duration_seconds=payload["duration_seconds"],
        sample_rate_hz=payload.get("sample_rate_hz"),
        channels=payload.get("channels"),
        codec=payload.get("codec"),
        format=payload.get("format"),
        bitrate_bps=payload.get("bitrate_bps"),
        file_size_bytes=payload.get("file_size_bytes"),
        checksum=payload.get("checksum"),
    )


__all__ = ["metadata_from_dict", "metadata_to_dict"]
