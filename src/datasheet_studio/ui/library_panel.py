"""Left-panel widget for browsing, grouping and searching the local library.

The library is grouped by document kind (datasheet today; software and
application notes are supported by the data model for later) and then by
manufacturer folder, exactly mirroring the folder layout on disk.
"""

import logging
import os
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.infrastructure.storage.library_store import (
    InvalidLibraryError,
    LibraryError,
)
from datasheet_studio.models.library_item import LibraryItem, LibraryItemKind
from datasheet_studio.services.library_service import LibraryService

LOG = logging.getLogger("datasheet_studio.ui.library")

_KIND_LABELS = {
    LibraryItemKind.DATASHEET: "Datasheets",
    LibraryItemKind.SOFTWARE: "Software",
    LibraryItemKind.APPLICATION_NOTE: "Application Notes",
}


class LibraryPanel(QWidget):
    """Browse and search the local datasheet library."""

    open_pdf_requested = Signal(str)          # absolute PDF path
    open_summary_requested = Signal(str)      # absolute summary path
    add_current_pdf_requested = Signal()
    status_message = Signal(str)

    def __init__(self, service: LibraryService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        self._open_button = QPushButton("📂 Open Library…")
        self._open_button.setToolTip("Open an existing library folder")
        self._open_button.clicked.connect(self._open_library_folder)
        self._create_button = QPushButton("＋ New Library…")
        self._create_button.clicked.connect(self._create_library)
        toolbar.addWidget(self._open_button)
        toolbar.addWidget(self._create_button)
        layout.addLayout(toolbar)

        add_row = QHBoxLayout()
        self._add_button = QPushButton("＋ Add Current PDF")
        self._add_button.setToolTip("Copy the currently open PDF into the library")
        self._add_button.clicked.connect(self.add_current_pdf_requested.emit)
        self._reindex_button = QPushButton("🔄 Reindex")
        self._reindex_button.clicked.connect(self._reindex)
        add_row.addWidget(self._add_button, 1)
        add_row.addWidget(self._reindex_button)
        layout.addLayout(add_row)


        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 Search datasheets… (fast)")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_edit)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(2)
        self._tree.setColumnWidth(0, 150)
        self._tree.itemActivated.connect(self._on_item_activated)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree, 1)

        self._status_label = QLabel("No library opened.")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_add_enabled(self, enabled: bool) -> None:
        """Enable/disable the 'Add current PDF' button."""
        self._add_button.setEnabled(enabled)

    def refresh(self) -> None:
        """Rebuild the tree from the currently open library (or a hint)."""
        if self._service.store is None:
            self._tree.clear()
            self._status_label.setText("No library opened.\nUse 'Open Library…' "
                                       "or 'New Library…' above.")
            return
        self._rebuild_tree(items=self._service.store.items)
        self._status_label.setText(
            f"{self._service.store.name} — {self._service.store.item_count} items"
        )


    # ------------------------------------------------------------------
    # Tree rendering
    # ------------------------------------------------------------------

    def _rebuild_tree(self, items: list[LibraryItem], query: str = "") -> None:
        self._tree.clear()
        if not items:
            if query:
                empty = QTreeWidgetItem([f"No matches for “{query}”"])
            else:
                empty = QTreeWidgetItem(["Library is empty.\nAdd the currently open "
                                         "PDF with '＋ Add Current PDF'."])
            empty.setDisabled(True)
            self._tree.addTopLevelItem(empty)
            return

        store = self._service.store
        grouped: dict[LibraryItemKind, dict[str, list[LibraryItem]]] = {}
        for item in items:
            grouped.setdefault(item.kind, {}).setdefault(
                item.manufacturer_folder or "Unsorted", []
            ).append(item)

        for kind in sorted(grouped, key=lambda k: _KIND_LABELS.get(k, k.value)):
            kind_node = QTreeWidgetItem([_KIND_LABELS.get(kind, kind.value)])
            kind_node.setFlags(kind_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            kind_font = kind_node.font(0)
            kind_font.setBold(True)
            kind_node.setFont(0, kind_font)
            self._tree.addTopLevelItem(kind_node)

            for folder_name in sorted(grouped[kind]):
                folder_node = QTreeWidgetItem([folder_name])
                folder_node.setFlags(folder_node.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                kind_node.addChild(folder_node)
                for item in sorted(
                    grouped[kind][folder_name], key=lambda i: i.title.lower()
                ):
                    title = item.title
                    if item.summary_file:
                        title = f"📄 {title}"
                    file_node = QTreeWidgetItem([title, item.part_number])
                    file_node.setData(0, Qt.ItemDataRole.UserRole, item.item_id)
                    if not store.item_exists(item):
                        file_node.setForeground(0, Qt.GlobalColor.gray)
                    file_node.setToolTip(0, self._item_tooltip(item, store))
                    folder_node.addChild(file_node)
            kind_node.setExpanded(True)

    @staticmethod
    def _item_tooltip(item: LibraryItem, store) -> str:
        lines = [
            f"Title: {item.title}",
            f"Part: {item.part_number or '—'}",
            f"Manufacturer: {item.manufacturer or '—'}",
            f"Pages: {item.page_count or '—'}",
            f"Added: {item.added_at or '—'}",
            f"Tags: {', '.join(item.tags) or '—'}",
            f"File: {store.item_path(item)}",
        ]
        if not store.item_exists(item):
            lines.append("⚠ Stored file is missing")
        if item.summary_file:
            lines.append(f"Summary: {item.summary_file}")
        return "\n".join(lines)


    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_search(self) -> None:
        query = self._search_edit.text().strip()
        if self._service.store is None:
            return
        if not query:
            self._rebuild_tree(items=self._service.store.items)
            return
        self._rebuild_tree(items=self._service.search(query), query=query)

    # ------------------------------------------------------------------
    # Item actions
    # ------------------------------------------------------------------

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.parent() is None:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        self._open_item(item_id)

    def _open_item(self, item_id: str) -> None:
        store = self._service.store
        if store is None:
            return
        lib_item = store.get_item(item_id)
        if lib_item is None:
            return
        path = store.item_path(lib_item)
        if not path.is_file():
            QMessageBox.warning(
                self, "File Missing",
                f"The stored file is missing:\n{path}\n\n"
                "It may have been moved or deleted outside the library.",
            )
            return
        self.open_pdf_requested.emit(str(path))

    def _selected_item_id(self) -> str | None:
        selected = self._tree.selectedItems()
        for item in selected:
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            if item_id:
                return item_id
        return None

    def _show_context_menu(self, pos) -> None:
        item_id = self._selected_item_id()
        store = self._service.store
        if store is None:
            return
        menu = QMenu(self)
        if item_id:
            lib_item = store.get_item(item_id)
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self._open_item(item_id))
            if lib_item is not None and lib_item.summary_file:
                summary_action = menu.addAction("Open Summary")
                summary_action.triggered.connect(
                    lambda: self.open_summary_requested.emit(
                        str(store.root / lib_item.summary_file)
                    )
                )
            move_action = menu.addAction("Move to Folder…")
            move_action.triggered.connect(lambda: self._move_item(item_id))
            reveal_action = menu.addAction("Reveal in Explorer")
            reveal_action.triggered.connect(lambda: self._reveal_item(item_id))
            menu.addSeparator()
            remove_action = menu.addAction("Remove from Library")
            remove_action.triggered.connect(lambda: self._remove_item(item_id))
        else:
            add_action = menu.addAction("Add Current PDF…")
            add_action.triggered.connect(self.add_current_pdf_requested.emit)
        menu.exec(self._tree.viewport().mapToGlobal(pos))


    def _move_item(self, item_id: str) -> None:
        store = self._service.store
        if store is None:
            return
        lib_item = store.get_item(item_id)
        if lib_item is None:
            return
        folders = store.manufacturer_folders(lib_item.kind)
        new_folder, ok = QInputDialog.getItem(
            self,
            "Move to Folder",
            "Choose an existing manufacturer folder or type a new name:",
            folders,
            editable=True,
        )
        if not ok or not new_folder.strip():
            return
        try:
            self._service.move_item(item_id, new_folder.strip())
        except LibraryError as exc:
            QMessageBox.warning(self, "Move Failed", str(exc))
            return
        self.status_message.emit(f"Moved to {new_folder.strip()}")
        self._apply_search()

    def _remove_item(self, item_id: str) -> None:
        store = self._service.store
        if store is None:
            return
        lib_item = store.get_item(item_id)
        if lib_item is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove from Library",
            f"Remove '{lib_item.title}' from the library?\n"
            "The stored file and its summary will be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.remove_item(item_id)
        except LibraryError as exc:
            QMessageBox.warning(self, "Remove Failed", str(exc))
            return
        self.status_message.emit("Removed from library")
        self._apply_search()

    def _reveal_item(self, item_id: str) -> None:
        store = self._service.store
        if store is None:
            return
        lib_item = store.get_item(item_id)
        if lib_item is None:
            return
        path = store.item_path(lib_item)
        target = path.parent if path.exists() else store.root
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


    # ------------------------------------------------------------------
    # Library lifecycle
    # ------------------------------------------------------------------

    def _open_library_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self, "Open Library Folder", str(self._service.store.root if self._service.store else os.path.expanduser("~"))
        )
        if not folder:
            return
        try:
            self._service.open_library(folder)
        except (InvalidLibraryError, LibraryError) as exc:
            QMessageBox.warning(
                self, "Not a Library",
                f"{folder}\n\nis not a valid Datasheet Studio library.\n\n"
                f"({exc})",
            )
            return
        self.status_message.emit(f"Opened library: {folder}")
        self.refresh()

    def _create_library(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self, "Create Library (choose a new empty folder)",
            str(self._service.store.root if self._service.store else os.path.expanduser("~")),
        )
        if not folder:
            return
        try:
            self._service.create_library(folder)
        except LibraryError as exc:
            QMessageBox.warning(self, "Create Library Failed", str(exc))
            return
        self.status_message.emit(f"Created library: {folder}")
        self.refresh()

    def _reindex(self) -> None:
        store = self._service.store
        if store is None:
            self.status_message.emit("Open a library first")
            return
        added, new_items = store.reindex()
        self._apply_search()
        if added:
            self.status_message.emit(f"Reindexed: {added} new item(s) found")
        else:
            self.status_message.emit("Reindexed: nothing new")

