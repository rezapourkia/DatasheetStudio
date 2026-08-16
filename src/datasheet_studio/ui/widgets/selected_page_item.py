"""Widget for displaying a selected PDF page with note editing capability."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.models.selected_page import SelectedPage


class SelectedPageItem(QWidget):
    """Widget representing a selected page with its note."""

    remove_requested = Signal(int)  # Emits page number to remove
    note_changed = Signal(int, str)  # Emits page number and new note text
    navigate_requested = Signal(int)  # Emits page number to navigate to

    def __init__(self, selected_page: SelectedPage, parent=None) -> None:
        super().__init__(parent)
        self._page = selected_page
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header row: page number + buttons
        header = QHBoxLayout()

        self._page_label = QLabel(self._page.display_title)
        self._page_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(self._page_label)

        header.addStretch()

        # Navigate button
        self._navigate_btn = QPushButton("Go to")
        self._navigate_btn.setToolTip("Navigate to this page in the viewer")
        self._navigate_btn.setFixedWidth(60)
        self._navigate_btn.clicked.connect(
            lambda: self.navigate_requested.emit(self._page.page_number)
        )
        header.addWidget(self._navigate_btn)

        # Remove button
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Remove this page from selected pages")
        self._remove_btn.setFixedWidth(60)
        self._remove_btn.clicked.connect(
            lambda: self.remove_requested.emit(self._page.page_number)
        )
        header.addWidget(self._remove_btn)

        layout.addLayout(header)

        # Note text area
        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("Add a note for this page...")
        self._note_edit.setMaximumHeight(80)
        self._note_edit.setPlainText(self._page.note)
        self._note_edit.textChanged.connect(self._on_note_changed)
        layout.addWidget(self._note_edit)

        # Timestamp
        self._timestamp_label = QLabel(
            f"Selected: {self._page.selected_at.strftime('%Y-%m-%d %H:%M')}"
        )
        self._timestamp_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._timestamp_label)

    def _on_note_changed(self) -> None:
        """Handle note text changes."""
        new_note = self._note_edit.toPlainText()
        self._page.note = new_note
        self.note_changed.emit(self._page.page_number, new_note)

    def get_page_number(self) -> int:
        """Return the page number."""
        return self._page.page_number

    def get_note(self) -> str:
        """Return the current note text."""
        return self._note_edit.toPlainText()

    def update_page(self, selected_page: SelectedPage) -> None:
        """Update the widget with new page data."""
        self._page = selected_page
        self._page_label.setText(self._page.display_title)
        self._note_edit.setPlainText(self._page.note)
        self._timestamp_label.setText(
            f"Selected: {self._page.selected_at.strftime('%Y-%m-%d %H:%M')}"
        )