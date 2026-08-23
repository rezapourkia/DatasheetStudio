"""Dialog for adding a datasheet to the library with a manufacturer folder.

The manufacturer combo is editable: it is pre-filled with the detected
vendor but the user can pick an existing folder or type a brand-new one.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from datasheet_studio.models.library_item import LibraryItemKind


class AddToLibraryDialog(QDialog):
    """Ask for kind, manufacturer folder (editable) and tags."""

    def __init__(
        self,
        parent=None,
        *,
        source_name: str = "",
        detected_manufacturer: str = "",
        existing_folders: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add to Library")
        self.setMinimumWidth(380)

        layout = QFormLayout(self)
        layout.setSpacing(10)

        source_label = QLabel(source_name or "(unknown file)")
        source_label.setWordWrap(True)
        layout.addRow("File:", source_label)

        self._kind_combo = QComboBox()
        for kind in (
            LibraryItemKind.DATASHEET,
            LibraryItemKind.SOFTWARE,
            LibraryItemKind.APPLICATION_NOTE,
        ):
            self._kind_combo.addItem(self._kind_label(kind), kind.value)
        layout.addRow("Kind:", self._kind_combo)

        self._folder_combo = QComboBox()
        self._folder_combo.setEditable(True)
        self._folder_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        folders = list(dict.fromkeys([detected_manufacturer] + list(existing_folders or [])))
        for folder in folders:
            if folder:
                self._folder_combo.addItem(folder)
        if not folders:
            self._folder_combo.setCurrentText("Unsorted")
        self._folder_combo.setToolTip(
            "Pick an existing manufacturer folder or type a new name."
        )
        layout.addRow("Manufacturer / folder:", self._folder_combo)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("comma separated, e.g. MCU, ARM, 48-pin")
        layout.addRow("Tags:", self._tags_edit)

        hint = QLabel(
            "The PDF is copied into the library folder. The original file "
            "stays where it is."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @staticmethod
    def _kind_label(kind: LibraryItemKind) -> str:
        return {
            LibraryItemKind.DATASHEET: "Datasheet",
            LibraryItemKind.SOFTWARE: "Software",
            LibraryItemKind.APPLICATION_NOTE: "Application Note",
        }[kind]

    def selected_kind(self) -> LibraryItemKind:
        return LibraryItemKind(self._kind_combo.currentData())

    def selected_folder(self) -> str:
        return self._folder_combo.currentText().strip()

    def selected_tags(self) -> list[str]:
        text = self._tags_edit.text().strip()
        if not text:
            return []
        return [tag.strip() for tag in text.split(",") if tag.strip()]

    def accept(self) -> None:
        if not self.selected_folder():
            self._folder_combo.setFocus()
            self._folder_combo.setStyleSheet("border: 1px solid #c0392b;")
            return
        super().accept()
