"""Widget for displaying and editing a colored annotation on a PDF page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.models.page_annotation import AnnotationColor, PageAnnotation


class AnnotationLabel(QWidget):
    """A colored note widget that can be placed on a PDF page view."""

    text_changed = Signal(int, str)  # annotation_id, new_text
    color_changed = Signal(int, AnnotationColor)  # annotation_id, new_color
    delete_requested = Signal(int)  # annotation_id

    def __init__(self, annotation: PageAnnotation, annotation_id: int, parent=None) -> None:
        super().__init__(parent)
        self._annotation = annotation
        self._annotation_id = annotation_id
        self._editing = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the annotation widget layout."""
        self.setFixedWidth(200)
        self.setMinimumHeight(60)
        self.setMaximumHeight(150)

        # Apply color styling
        self.setStyleSheet(self._annotation.color_stylesheet)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header with color indicator and delete button
        header = QHBoxLayout()

        self._color_indicator = QLabel("●")
        self._color_indicator.setStyleSheet(f"color: {self._get_color_hex()}; font-size: 16px;")
        header.addWidget(self._color_indicator)

        header.addStretch()

        # Change color button
        self._color_btn = QPushButton("🎨")
        self._color_btn.setFixedSize(24, 24)
        self._color_btn.setToolTip("Change color")
        self._color_btn.clicked.connect(self._show_color_menu)
        header.addWidget(self._color_btn)

        # Delete button
        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedSize(24, 24)
        self._delete_btn.setToolTip("Delete annotation")
        self._delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._annotation_id))
        header.addWidget(self._delete_btn)

        layout.addLayout(header)

        # Text area (editable on double-click)
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(self._annotation.text)
        self._text_edit.setPlaceholderText("Click to edit...")
        self._text_edit.setMaximumHeight(80)
        self._text_edit.setReadOnly(True)
        self._text_edit.setStyleSheet("background-color: transparent; border: none;")
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

        # Make the whole widget editable on double-click
        self.mouseDoubleClickEvent = self._on_double_click

    def _get_color_hex(self) -> str:
        """Get the hex color code for the current annotation color."""
        color_map = {
            AnnotationColor.YELLOW: "#FFEB3B",
            AnnotationColor.GREEN: "#8BC34A",
            AnnotationColor.BLUE: "#64B5F6",
            AnnotationColor.PINK: "#F48FB1",
            AnnotationColor.ORANGE: "#FFB74D",
            AnnotationColor.PURPLE: "#CE93D8",
        }
        return color_map.get(self._annotation.color, "#FFEB3B")

    def _on_double_click(self, event) -> None:
        """Toggle edit mode on double-click."""
        self._editing = not self._editing
        self._text_edit.setReadOnly(not self._editing)
        if self._editing:
            self._text_edit.setFocus()
            self.setStyleSheet(
                self._annotation.color_stylesheet + " border: 3px solid #1976D2;"
            )
        else:
            self.setStyleSheet(self._annotation.color_stylesheet)

    def _on_text_changed(self) -> None:
        """Handle text changes."""
        new_text = self._text_edit.toPlainText()
        self._annotation.text = new_text
        self.text_changed.emit(self._annotation_id, new_text)

    def _show_color_menu(self) -> None:
        """Show color selection menu."""
        menu = QMenu(self)

        for color in AnnotationColor:
            action = menu.addAction(f"● {color.value.title()}")
            action.triggered.connect(lambda c=color: self._change_color(c))

        menu.exec(self._color_btn.mapToGlobal(self._color_btn.rect().bottomLeft()))

    def _change_color(self, color: AnnotationColor) -> None:
        """Change the annotation color."""
        self._annotation.color = color
        self.setStyleSheet(self._annotation.color_stylesheet)
        self._color_indicator.setStyleSheet(f"color: {self._get_color_hex()}; font-size: 16px;")
        self.color_changed.emit(self._annotation_id, color)

    def get_annotation(self) -> PageAnnotation:
        """Return the annotation data."""
        return self._annotation

    def get_id(self) -> int:
        """Return the annotation ID."""
        return self._annotation_id