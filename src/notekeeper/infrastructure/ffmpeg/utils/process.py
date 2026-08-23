"""FFmpeg subprocess execution with machine-readable progress."""

import subprocess
from collections.abc import Callable

from notekeeper.infrastructure.errors import InfrastructureError


def run_ffmpeg_with_progress(
    command: list[str],
    stage: str,
    *,
    executable: str,
    duration_seconds: float,
    progress_callback: Callable[[float], None] | None,
) -> int:
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise InfrastructureError(
            f"ffmpeg executable not found during {stage}: {executable}"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise InfrastructureError(
            f"ffmpeg command could not run during {stage}: {exc}"
        ) from exc

    if process.stdout is None:
        raise InfrastructureError(
            f"ffmpeg progress stream is unavailable during {stage}"
        )

    for line in process.stdout:
        key, separator, value = line.strip().partition("=")
        if not separator:
            continue
        if key == "progress" and value == "end":
            if progress_callback is not None:
                progress_callback(1.0)
            continue
        if key not in {"out_time_us", "out_time_ms"}:
            continue
        try:
            output_seconds = int(value) / 1_000_000
        except ValueError:
            continue
        if progress_callback is not None and duration_seconds > 0:
            progress_callback(min(output_seconds / duration_seconds, 1.0))

    stderr = process.stderr.read() if process.stderr is not None else ""
    returncode = process.wait()
    if returncode != 0:
        detail = stderr.strip()
        message = f"ffmpeg command failed during {stage}"
        if detail:
            message = f"{message}: {detail}"
        raise InfrastructureError(message)
    return returncode


__all__ = ["run_ffmpeg_with_progress"]
