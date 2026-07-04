"""JSON-safe payload conversion helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, Mapping):
        return {str(key): to_json_safe(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [to_json_safe(item) for item in value]

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_json_safe(item())
        except (TypeError, ValueError):
            pass

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return to_json_safe(tolist())
        except (TypeError, ValueError):
            pass

    return repr(value)


__all__ = ["to_json_safe"]
