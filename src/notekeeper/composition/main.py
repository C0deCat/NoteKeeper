"""Application entrypoint."""

from __future__ import annotations

from collections.abc import Sequence

from notekeeper.interfaces.cli import build_app
from notekeeper.interfaces.tui import run_tui

from .runtime import build_runtime


def main(args: Sequence[str] | None = None) -> None:
    app = build_app(build_runtime, run_tui)
    app(args=list(args) if args is not None else None)
