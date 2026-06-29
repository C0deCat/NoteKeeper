"""Audio metadata value object."""

from dataclasses import dataclass

from ..validation import (
    optional_non_empty_str,
    optional_non_negative_int,
    optional_positive_int,
    positive_float,
)


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    duration_seconds: float
    sample_rate_hz: int | None = None
    channels: int | None = None
    codec: str | None = None
    format: str | None = None
    bitrate_bps: int | None = None
    file_size_bytes: int | None = None
    checksum: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "duration_seconds",
            positive_float(self.duration_seconds, "duration_seconds"),
        )
        object.__setattr__(
            self,
            "sample_rate_hz",
            optional_positive_int(self.sample_rate_hz, "sample_rate_hz"),
        )
        object.__setattr__(
            self,
            "channels",
            optional_positive_int(self.channels, "channels"),
        )
        object.__setattr__(
            self,
            "bitrate_bps",
            optional_non_negative_int(self.bitrate_bps, "bitrate_bps"),
        )
        object.__setattr__(
            self,
            "file_size_bytes",
            optional_non_negative_int(self.file_size_bytes, "file_size_bytes"),
        )
        object.__setattr__(self, "codec", optional_non_empty_str(self.codec, "codec"))
        object.__setattr__(self, "format", optional_non_empty_str(self.format, "format"))
        object.__setattr__(
            self,
            "checksum",
            optional_non_empty_str(self.checksum, "checksum"),
        )
