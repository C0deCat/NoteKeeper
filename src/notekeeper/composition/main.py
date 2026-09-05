"""Application entrypoint."""

from __future__ import annotations

from collections.abc import Sequence

from notekeeper.interfaces.cli import build_app
from notekeeper.interfaces.tui import run_tui

from .runtime import build_local_host
from .web import run_local_api


def main(args: Sequence[str] | None = None) -> None:
    app = build_app(
        lambda: build_local_host().interactive_runtime(),
        run_tui,
        run_local_api,
    )
    app(args=list(args) if args is not None else None)
