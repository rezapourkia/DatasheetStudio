"""Overlay widget for displaying annotations on a PDF page."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QWidget

from datasheet_studio.models.page_annotation import AnnotationColor, PageAnnotation
from datasheet_studio.ui.widgets.annotation_label import AnnotationLabel


class AnnotationOverlay(QWidget):
    """Transparent overlay that displays annotation labels on top of a PDF page."""

    annotation_created = Signal(PageAnnotation)  # Emitted when user creates annotation
    annotation_deleted = Signal(int)  # Emitted when user deletes annotation (by id)
    annotation_text_changed = Signal(int, str)  # id, new_text
    annotation_color_changed = Signal(int, AnnotationColor)  # id, new_color

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self._annotations: list[tuple[int, PageAnnotation, AnnotationLabel]] = []
        self._next_id = 1
        self._annotation_mode = False
        self._current_page = 1
        self._page_width = 0
        self._page_height = 0

    def set_annotation_mode(self, enabled: bool) -> None:
        """Enable or disable annotation creation mode."""
        self._annotation_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def is_annotation_mode(self) -> bool:
        """Return whether annotation mode is active."""
        return self._annotation_mode

    def set_page_info(self, page_number: int, image_width: int, image_height: int) -> None:
        """Update the current page info for positioning annotations."""
        self._current_page = page_number
        self._page_width = image_width
        self._page_height = image_height
        self._refresh_annotations()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press to create annotation in annotation mode."""
        if not self._annotation_mode:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._create_annotation_at(pos)

    def _create_annotation_at(self, pos: QPoint) -> None:
        """Create a new annotation at the given position."""
        if self._page_width == 0 or self._page_height == 0:
            return

        # Calculate relative position (0.0 to 1.0)
        x_percent = pos.x() / self._page_width
        y_percent = pos.y() / self._page_height

        # Clamp to valid range
        x_percent = max(0.0, min(1.0, x_percent))
        y_percent = max(0.0, min(1.0, y_percent))

        annotation = PageAnnotation(
            page_number=self._current_page,
            x_percent=x_percent,
            y_percent=y_percent,
            text="",
            color=AnnotationColor.YELLOW,
        )

        annotation_id = self._next_id
        self._next_id += 1

        # Create the label widget
        label = AnnotationLabel(annotation, annotation_id, self)
        
        # Position the label at the click position
        label.move(pos.x() - 100, pos.y() - 30)  # Offset so it appears near click
        
        # Connect signals
        label.text_changed.connect(self._on_annotation_text_changed)
        label.color_changed.connect(self._on_annotation_color_changed)
        label.delete_requested.connect(self._on_annotation_deleted)

        label.show()

        self._annotations.append((annotation_id, annotation, label))
        self.annotation_created.emit(annotation)

    def _on_annotation_text_changed(self, annotation_id: int, text: str) -> None:
        """Handle annotation text change."""
        self.annotation_text_changed.emit(annotation_id, text)

    def _on_annotation_color_changed(self, annotation_id: int, color: AnnotationColor) -> None:
        """Handle annotation color change."""
        self.annotation_color_changed.emit(annotation_id, color)

    def _on_annotation_deleted(self, annotation_id: int) -> None:
        """Handle annotation deletion."""
        for i, (aid, _, label) in enumerate(self._annotations):
            if aid == annotation_id:
                label.hide()
                label.deleteLater()
                self._annotations.pop(i)
                self.annotation_deleted.emit(annotation_id)
                break

    def _refresh_annotations(self) -> None:
        """Reposition all annotations for the current page."""
        for annotation_id, annotation, label in self._annotations:
            if annotation.page_number == self._current_page:
                # Calculate absolute position
                x = int(annotation.x_percent * self._page_width)
                y = int(annotation.y_percent * self._page_height)
                label.move(x - 100, y - 30)
                label.show()
            else:
                label.hide()

    def clear_annotations_for_page(self, page_number: int) -> None:
        """Remove all annotations for a specific page."""
        to_remove = []
        for i, (aid, annotation, label) in enumerate(self._annotations):
            if annotation.page_number == page_number:
                label.hide()
                label.deleteLater()
                to_remove.append(i)

        for i in reversed(to_remove):
            self._annotations.pop(i)

    def get_annotations_for_page(self, page_number: int) -> list[PageAnnotation]:
        """Get all annotations for a specific page."""
        return [ann for _, ann, _ in self._annotations if ann.page_number == page_number]

    def resizeEvent(self, event) -> None:
        """Handle resize to reposition annotations."""
        super().resizeEvent(event)
        self._refresh_annotations()