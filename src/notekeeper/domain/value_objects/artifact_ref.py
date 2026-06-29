"""Artifact reference value object."""

from dataclasses import dataclass

from ..validation import non_empty_str, optional_non_empty_str


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    uri: str
    kind: str = "file"
    checksum: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", non_empty_str(self.uri, "uri"))
        object.__setattr__(self, "kind", non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self,
            "checksum",
            optional_non_empty_str(self.checksum, "checksum"),
        )
