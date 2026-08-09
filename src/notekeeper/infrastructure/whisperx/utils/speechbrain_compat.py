"""Compatibility helpers for SpeechBrain lazy imports."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def patch_speechbrain_inspect_lazy_imports() -> None:
    """Prevent Python inspection from importing SpeechBrain optional modules.

    SpeechBrain's lazy module guard checks for "/inspect.py", which misses
    Windows paths. Lightning and PyTorch inspect loaded modules while pyannote
    loads checkpoints, and that can accidentally import optional SpeechBrain
    integrations such as k2_fsa.
    """

    try:
        importutils = importlib.import_module("speechbrain.utils.importutils")
    except ImportError:
        return

    lazy_module = importutils.LazyModule
    original = lazy_module.ensure_module
    if getattr(original, "_notekeeper_inspect_patch", False):
        return

    def ensure_module(self: Any, stacklevel: int):
        if _caller_is_inspect(stacklevel + 1):
            raise AttributeError()
        return original(self, stacklevel)

    setattr(ensure_module, "_notekeeper_inspect_patch", True)
    setattr(lazy_module, "ensure_module", ensure_module)


def _caller_is_inspect(stacklevel: int) -> bool:
    try:
        filename = sys._getframe(stacklevel + 1).f_code.co_filename
    except (AttributeError, ValueError):
        return False
    return Path(filename).name == "inspect.py"


__all__ = ["patch_speechbrain_inspect_lazy_imports"]
