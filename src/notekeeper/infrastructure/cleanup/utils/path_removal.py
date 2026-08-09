"""Safe removal of cleanup-owned filesystem paths."""

import shutil
from pathlib import Path

from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.utils import ensure_within_root


def remove_owned_path(path: Path, root: Path, *, label: str) -> None:
    ensure_within_root(path, root)
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise InfrastructureError(f"{label} path must not be a symbolic link")
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as exc:
        raise InfrastructureError(f"could not delete {label} path: {path}") from exc


__all__ = ["remove_owned_path"]

