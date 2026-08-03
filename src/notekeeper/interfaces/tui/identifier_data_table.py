"""Data table support for compact identifier cells and their tooltips."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal, Self

from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from textual.widgets._data_table import (
    CellKey,
    CursorType,
    RowKey,
)


class IdentifierDataTable(DataTable[object]):
    """Display compact identifiers while exposing their full value on hover."""

    def __init__(
        self,
        *,
        show_header: bool = True,
        show_row_labels: bool = True,
        fixed_rows: int = 0,
        fixed_columns: int = 0,
        zebra_stripes: bool = False,
        header_height: int = 1,
        show_cursor: bool = True,
        cursor_foreground_priority: Literal["renderable", "css"] = "css",
        cursor_background_priority: Literal["renderable", "css"] = "renderable",
        cursor_type: CursorType = "cell",
        cell_padding: int = 1,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        self._full_identifiers: dict[CellKey, str] = {}
        super().__init__(
            show_header=show_header,
            show_row_labels=show_row_labels,
            fixed_rows=fixed_rows,
            fixed_columns=fixed_columns,
            zebra_stripes=zebra_stripes,
            header_height=header_height,
            show_cursor=show_cursor,
            cursor_foreground_priority=cursor_foreground_priority,
            cursor_background_priority=cursor_background_priority,
            cursor_type=cursor_type,
            cell_padding=cell_padding,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

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
    ) -> RowKey:
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
            self._full_identifiers[
                CellKey(row_key, columns[index].key)
            ] = identifier
        return row_key

    def watch_hover_coordinate(self, old: Coordinate, value: Coordinate) -> None:
        super().watch_hover_coordinate(old, value)
        if not self.is_valid_coordinate(value):
            self.tooltip = None
            return
        self.tooltip = self._full_identifiers.get(
            self.coordinate_to_cell_key(value),
        )


def compact_identifier(identifier: str) -> str:
    """Return the consistently shortened dashboard representation of an ID."""
    return f"…{identifier[-8:]}"
