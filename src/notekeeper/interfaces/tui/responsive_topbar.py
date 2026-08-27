"""Responsive layout container for the dashboard top bar."""

from textual import events
from textual.containers import Container


class ResponsiveTopbar(Container):
    """Switch the top bar between compact, stacked layout modes."""

    _LAYOUT_CLASSES = {
        "topbar-wide",
        "topbar-account-row",
        "topbar-action-row",
        "topbar-selector-rows",
    }

    def on_mount(self) -> None:
        self._update_layout(self.size.width)

    def on_resize(self, event: events.Resize) -> None:
        self._update_layout(event.size.width)

    def _update_layout(self, width: int) -> None:
        if width >= 103:
            layout_class = "topbar-wide"
        elif width >= 80:
            layout_class = "topbar-account-row"
        elif width >= 59:
            layout_class = "topbar-action-row"
        else:
            layout_class = "topbar-selector-rows"

        for class_name in self._LAYOUT_CLASSES:
            self.set_class(class_name == layout_class, class_name)


__all__ = ["ResponsiveTopbar"]
