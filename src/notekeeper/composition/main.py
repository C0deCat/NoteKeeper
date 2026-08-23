"""Application entrypoint."""

from __future__ import annotations

from collections.abc import Sequence

from notekeeper.interfaces.cli import build_app
from notekeeper.interfaces.tui import run_tui

from .runtime import build_local_host


def main(args: Sequence[str] | None = None) -> None:
    app = build_app(lambda: build_local_host().interactive_runtime(), run_tui)
    app(args=list(args) if args is not None else None)
