"""Custom scroll area for PDF document viewing with mouse wheel support."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea


class PdfScrollArea(QScrollArea):
    """Scroll area that handles mouse wheel for scrolling and Ctrl+wheel for zoom."""

    zoom_requested = Signal(float)  # Emits zoom delta (positive = zoom in, negative = zoom out)
    page_navigation_requested = Signal(int)  # Emits page delta (+1 = next, -1 = previous)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_enabled = True
        self._at_top = True
        self._at_bottom = True

    def set_zoom_enabled(self, enabled: bool) -> None:
        """Enable or disable zoom with Ctrl+wheel."""
        self._zoom_enabled = enabled

    def set_at_boundaries(self, at_top: bool, at_bottom: bool) -> None:
        """Inform the scroll area about its position in the document."""
        self._at_top = at_top
        self._at_bottom = at_bottom

    def setWidget(self, widget) -> None:
        """Override setWidget to install event filter on the child widget."""
        super().setWidget(widget)
        if widget is not None:
            widget.installEventFilter(self)

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Filter events from child widget to handle wheel events."""
        if event.type() == QEvent.Type.Wheel:
            return self._handle_wheel_event(event)
        return super().eventFilter(obj, event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events for scrolling and zooming."""
        if self._handle_wheel_event(event):
            return
        super().wheelEvent(event)

    def _handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Process wheel events for scrolling and zooming. Returns True if handled."""
        modifiers = event.modifiers()
        delta = event.angleDelta().y()

        # Ctrl+wheel = zoom
        if modifiers == Qt.KeyboardModifier.ControlModifier and self._zoom_enabled:
            if delta > 0:
                self.zoom_requested.emit(1.0)  # zoom in
            elif delta < 0:
                self.zoom_requested.emit(-1.0)  # zoom out
            event.accept()
            return True

        # Normal wheel = scroll
        # Check if we're at boundaries and trying to scroll further
        vertical_bar = self.verticalScrollBar()
        if vertical_bar and delta != 0:
            at_top = vertical_bar.value() == vertical_bar.minimum()
            at_bottom = vertical_bar.value() == vertical_bar.maximum()

            # Scrolling up at top -> go to previous page
            if delta > 0 and at_top and self._at_top:
                self.page_navigation_requested.emit(-1)
                event.accept()
                return True

            # Scrolling down at bottom -> go to next page
            if delta < 0 and at_bottom and self._at_bottom:
                self.page_navigation_requested.emit(1)
                event.accept()
                return True

        # Let the scroll area handle normal scrolling
        return False