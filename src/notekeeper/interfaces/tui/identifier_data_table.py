"""Data table support for compact identifier cells and their tooltips."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable


class IdentifierDataTable(DataTable):
    """Display compact identifiers while exposing their full value on hover."""

    def __init__(self, **kwargs) -> None:
        self._full_identifiers: dict[tuple[object, object], str] = {}
        super().__init__(**kwargs)

    def clear(self, columns: bool = False) -> Self:
        self._full_identifiers.clear()
        return super().clear(columns=columns)

    def on_focus(self, event: events.Focus) -> None:
        """Make a focused table eligible to become the dashboard selection."""
        self.show_cursor = True

    def add_identifier_row(
        self,
        *cells: object,
        identifier_indices: Iterable[int],
        key: str,
    ) -> object:
        """Add a row, compacting and remembering the supplied ID cells."""
        displayed_cells = list(cells)
        identifiers = {
            index: str(cells[index])
            for index in identifier_indices
            if cells[index]
        }
        for index, identifier in identifiers.items():
            displayed_cells[index] = compact_identifier(identifier)

        row_key = super().add_row(*displayed_cells, key=key)
        columns = self.ordered_columns
        for index, identifier in identifiers.items():
            self._full_identifiers[(row_key, columns[index].key)] = identifier
        return row_key

    def watch_hover_coordinate(self, old: Coordinate, value: Coordinate) -> None:
        super().watch_hover_coordinate(old, value)
        if not self.is_valid_coordinate(value):
            self.tooltip = None
            return
        self.tooltip = self._full_identifiers.get(
            tuple(self.coordinate_to_cell_key(value)),
        )


def compact_identifier(identifier: str) -> str:
    """Return the consistently shortened dashboard representation of an ID."""
    return f"…{identifier[-8:]}"
