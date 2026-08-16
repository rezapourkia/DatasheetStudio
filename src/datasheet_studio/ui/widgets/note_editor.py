"""Note editor dialog for PDF annotations."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QDoubleSpinBox, QComboBox, QPushButton, QColorDialog, QGroupBox, QFormLayout,
)
from PySide6.QtGui import QColor
from datasheet_studio.models.pdf_document import PdfNote


class NoteEditorDialog(QDialog):
    """Dialog for creating and editing PDF notes."""

    def __init__(self, note: PdfNote | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Note" if note else "Add Note")
        self.setMinimumWidth(400)
        self._note = note or PdfNote(page_number=1, text="", x=0.5, y=0.5)
        self._setup_ui()
        self._load_note_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        text_group = QGroupBox("Note Content")
        text_layout = QVBoxLayout(text_group)
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Enter your note here...")
        self._text_edit.setMinimumHeight(100)
        text_layout.addWidget(self._text_edit)
        layout.addWidget(text_group)
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        self._bg_color_button = QPushButton()
        self._bg_color_button.setFixedHeight(30)
        self._bg_color_button.clicked.connect(self._choose_bg_color)
        appearance_layout.addRow("Background Color:", self._bg_color_button)
        self._text_color_button = QPushButton()
        self._text_color_button.setFixedHeight(30)
        self._text_color_button.clicked.connect(self._choose_text_color)
        appearance_layout.addRow("Text Color:", self._text_color_button)
        self._border_color_button = QPushButton()
        self._border_color_button.setFixedHeight(30)
        self._border_color_button.clicked.connect(self._choose_border_color)
        appearance_layout.addRow("Border Color:", self._border_color_button)
        self._font_combo = QComboBox()
        self._font_combo.addItems(["Segoe UI", "Arial", "Times New Roman", "Courier New", "Verdana", "Georgia"])
        self._font_combo.setEditable(True)
        appearance_layout.addRow("Font Family:", self._font_combo)
        self._font_size_spin = QDoubleSpinBox()
        self._font_size_spin.setRange(8, 72)
        self._font_size_spin.setValue(11)
        appearance_layout.addRow("Font Size:", self._font_size_spin)
        self._border_width_spin = QDoubleSpinBox()
        self._border_width_spin.setRange(0, 5)
        self._border_width_spin.setValue(0)
        appearance_layout.addRow("Border Width:", self._border_width_spin)
        size_layout = QHBoxLayout()
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(0.05, 0.5)
        self._width_spin.setValue(0.15)
        self._width_spin.setSingleStep(0.01)
        self._width_spin.setDecimals(2)
        self._width_spin.setSuffix(" (relative)")
        size_layout.addWidget(QLabel("Width:"))
        size_layout.addWidget(self._width_spin)
        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.03, 0.3)
        self._height_spin.setValue(0.08)
        self._height_spin.setSingleStep(0.01)
        self._height_spin.setDecimals(2)
        self._height_spin.setSuffix(" (relative)")
        size_layout.addWidget(QLabel("Height:"))
        size_layout.addWidget(self._height_spin)
        appearance_layout.addRow("Size:", size_layout)
        layout.addWidget(appearance_group)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def _load_note_data(self) -> None:
        self._text_edit.setPlainText(self._note.text)
        self._font_combo.setCurrentText(self._note.font_family)
        self._font_size_spin.setValue(self._note.font_size)
        self._border_width_spin.setValue(self._note.border_width)
        self._width_spin.setValue(self._note.width)
        self._height_spin.setValue(self._note.height)
        self._update_color_button(self._bg_color_button, self._note.background_color)
        self._update_color_button(self._text_color_button, self._note.text_color)
        self._update_color_button(self._border_color_button, self._note.border_color)

    def _update_color_button(self, button: QPushButton, color_hex: str) -> None:
        button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black;")
        button.setText(color_hex)

    def _choose_bg_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._note.background_color), self)
        if color.isValid():
            self._note.background_color = color.name()
            self._update_color_button(self._bg_color_button, color.name())

    def _choose_text_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._note.text_color), self)
        if color.isValid():
            self._note.text_color = color.name()
            self._update_color_button(self._text_color_button, color.name())

    def _choose_border_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._note.border_color), self)
        if color.isValid():
            self._note.border_color = color.name()
            self._update_color_button(self._border_color_button, color.name())

    def get_note(self) -> PdfNote:
        self._note.text = self._text_edit.toPlainText()
        self._note.font_family = self._font_combo.currentText()
        self._note.font_size = int(self._font_size_spin.value())
        self._note.border_width = int(self._border_width_spin.value())
        self._note.width = self._width_spin.value()
        self._note.height = self._height_spin.value()
        return self._note
