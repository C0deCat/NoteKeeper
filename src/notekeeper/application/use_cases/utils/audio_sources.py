"""Validation and normalization for audio source inputs."""

from pathlib import Path

from notekeeper.application.errors import InvalidOperationError


def resolve_audio_source(
    artifact_uri: str | None,
    source_path: str | None,
) -> tuple[str | None, Path | None]:
    normalized_uri = artifact_uri.strip() if artifact_uri is not None else ""
    normalized_source = source_path.strip() if source_path is not None else ""

    if bool(normalized_uri) == bool(normalized_source):
        raise InvalidOperationError(
            "exactly one of artifact_uri or source_path must be provided",
        )

    if normalized_source:
        return None, Path(normalized_source).expanduser().resolve(strict=False)
    return normalized_uri, None
