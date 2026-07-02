"""Audio probing helpers."""

from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path
from typing import Any


def read_ffprobe(path: Path, ffprobe_path: str) -> dict[str, Any] | None:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name,bit_rate:stream=codec_name,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    try:
        payload = json.loads(completed.stdout)
        format_data = payload.get("format") or {}
        streams = payload.get("streams") or []
        stream = streams[0] if streams else {}
        duration = float(format_data["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if duration <= 0:
        return None

    return {
        "duration_seconds": duration,
        "sample_rate_hz": _optional_int(stream.get("sample_rate")),
        "channels": _optional_int(stream.get("channels")),
        "codec": stream.get("codec_name"),
        "format": format_data.get("format_name"),
        "bitrate_bps": _optional_int(format_data.get("bit_rate")),
    }


def read_wave(path: Path) -> dict[str, Any] | None:
    try:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            frame_rate = audio.getframerate()
            channels = audio.getnchannels()
    except (OSError, wave.Error):
        return None

    if frames <= 0 or frame_rate <= 0:
        return None

    return {
        "duration_seconds": frames / frame_rate,
        "sample_rate_hz": frame_rate,
        "channels": channels,
        "codec": "pcm",
        "format": "wav",
    }


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
