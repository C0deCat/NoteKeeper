"""Safe server-owned temporary storage for multipart audio uploads."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import UploadFile

from ..errors import ApiError

_CHUNK_SIZE = 1024 * 1024


def save_audio_upload(
    upload: UploadFile,
    *,
    directory: Path,
    allowed_extensions: tuple[str, ...],
    max_bytes: int,
) -> Path:
    filename = upload.filename or ""
    suffix = Path(filename).suffix.casefold()
    allowed = {value.casefold() for value in allowed_extensions}
    if not suffix or suffix not in allowed:
        raise ApiError(
            415,
            "unsupported_media_type",
            "Uploaded file extension is not supported",
        )
    if upload.size is not None and upload.size > max_bytes:
        raise ApiError(
            413,
            "payload_too_large",
            "Uploaded audio exceeds the configured size limit",
        )
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(
        prefix="notekeeper-api-",
        suffix=suffix,
        dir=directory,
    )
    path = Path(raw_path)
    written = 0
    try:
        with os.fdopen(descriptor, "wb") as target:
            while True:
                chunk = upload.file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ApiError(
                        413,
                        "payload_too_large",
                        "Uploaded audio exceeds the configured size limit",
                    )
                target.write(chunk)
        if written == 0:
            raise ApiError(422, "validation_error", "Uploaded audio is empty")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def remove_temporary_upload(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


__all__ = ["remove_temporary_upload", "save_audio_upload"]
