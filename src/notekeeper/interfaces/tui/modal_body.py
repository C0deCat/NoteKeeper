from textual import events
from textual.containers import VerticalScroll
from textual.geometry import Size
from textual.widget import Widget


class ModalBody(VerticalScroll):
    """Scrollable modal body that fills the modal only when content overflows."""

    _screen_size: Size | None = None

    def on_mount(self) -> None:
        self._screen_size = self.screen.size
        self.set_timer(0.001, self._sync_modal_height)

    def on_resize(self, _event: events.Resize) -> None:
        screen_size = self.screen.size
        modal = self.parent
        screen_resized = screen_size != self._screen_size
        if screen_resized:
            self._screen_size = screen_size
        if (
            isinstance(modal, Widget)
            and modal.has_class("modal-constrained")
            and screen_resized
        ):
            modal.remove_class("modal-constrained")
        self.set_timer(0.001, self._sync_modal_height)

    def _sync_modal_height(self) -> None:
        modal = self.parent
        if (
            not isinstance(modal, Widget)
            or not modal.has_class("modal")
            or modal.has_class("modal-constrained")
        ):
            return
        if self.region.bottom != modal.region.bottom:
            modal.add_class("modal-constrained")


__all__ = ["ModalBody"]
