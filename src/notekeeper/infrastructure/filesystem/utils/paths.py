"""Filesystem path safety helpers."""

from pathlib import Path, PurePosixPath

from notekeeper.infrastructure.errors import InfrastructureError


def safe_uri_parts(uri: str) -> tuple[str, ...]:
    if "://" in uri:
        raise InfrastructureError("artifact uri must be relative to storage root")

    path = PurePosixPath(uri)
    if path.is_absolute():
        raise InfrastructureError("artifact uri must not be absolute")

    parts = path.parts
    if not parts:
        raise InfrastructureError("artifact uri must not be empty")

    for part in parts:
        if part in {"", ".", ".."} or ":" in part or "\\" in part:
            raise InfrastructureError("artifact uri contains an unsafe path segment")

    return tuple(parts)


def safe_relative_name(name: str) -> Path:
    parts = safe_uri_parts(name.replace("\\", "/"))
    return Path(*parts)


def safe_name(name: str, field: str) -> str:
    value = name.strip()
    if not value:
        raise InfrastructureError(f"{field} must not be empty")
    if "/" in value or "\\" in value or ":" in value:
        raise InfrastructureError(f"{field} contains an unsafe path segment")
    if value in {".", ".."}:
        raise InfrastructureError(f"{field} contains an unsafe path segment")
    return value


def ensure_within_root(path: Path, root: Path) -> Path:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise InfrastructureError("path is outside storage root") from exc
    return path


def available_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
