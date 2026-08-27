"""Select control with a compact current label and a full-value tooltip."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rich.cells import cell_len, set_cell_size
from rich.console import RenderableType
from rich.text import Text
from textual import events
from textual.css.query import NoMatches
from textual.widgets import Select, Static
from textual.widgets._select import NoSelection, SelectCurrent


class EllipsisSelect(Select[str]):
    def __init__(
        self,
        options: Iterable[tuple[RenderableType, str]],
        *,
        prompt: str = "Select",
        allow_blank: bool = True,
        value: Any = Select.NULL,
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        materialized = tuple(options)
        self._full_labels = {
            option_value: self._label_text(label)
            for label, option_value in materialized
        }
        super().__init__(
            materialized,
            prompt=prompt,
            allow_blank=allow_blank,
            value=value,
            id=id,
            disabled=disabled,
        )

    def set_options(
        self,
        options: Iterable[tuple[RenderableType, str]],
    ) -> None:
        materialized = tuple(options)
        self._full_labels = {
            option_value: self._label_text(label)
            for label, option_value in materialized
        }
        super().set_options(materialized)

    def _watch_value(self, value: str | NoSelection) -> None:
        super()._watch_value(value)
        label = self._full_labels.get(value) if isinstance(value, str) else None
        self.tooltip = label
        self._render_current_label(label)

    def on_mount(self) -> None:
        self.call_after_refresh(self._render_selected_label)

    def on_resize(self, _event: events.Resize) -> None:
        self._render_selected_label()

    def _render_selected_label(self) -> None:
        value = self.value
        label = self._full_labels.get(value) if isinstance(value, str) else None
        self._render_current_label(label)

    def _render_current_label(self, label: str | None) -> None:
        if label is None:
            return
        try:
            current = self.query_one(SelectCurrent)
        except NoMatches:
            return
        label_widget = current.query_one("#label", Static)
        width = label_widget.size.width
        if width <= 0 or cell_len(label) <= width:
            label_widget.update(label)
            return
        if width <= 3:
            label_widget.update("." * width)
            return
        label_widget.update(f"{set_cell_size(label, width - 3).rstrip()}...")

    @staticmethod
    def _label_text(label: RenderableType) -> str:
        return label.plain if isinstance(label, Text) else str(label)


__all__ = ["EllipsisSelect"]
