"""Main application window for Datasheet Studio."""

import json
import logging
import os
import threading
import time
from datetime import datetime

from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.core.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_VERSION,
    DEFAULT_PANEL_SIZES,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MAX_RECENT_FILES,
)
from datasheet_studio.infrastructure.pdf.reader import PdfOpenError, PdfReader
from datasheet_studio.models.pdf_document import PdfDocumentInfo
from datasheet_studio.models.selected_page import SelectedPage
from datasheet_studio.services.selection_storage import SelectionStorage, SelectionStorageError
from datasheet_studio.ui.widgets.pdf_scroll_area import PdfScrollArea
from datasheet_studio.ui.markdown_render import html_escape, markdown_to_html
from datasheet_studio.ui.widgets.note_overlay import NoteOverlayWidget
from datasheet_studio.ui.widgets.note_editor import NoteEditorDialog
from datasheet_studio.ui.widgets.search_strip import SearchStrip
from datasheet_studio.services.online_import import OnlineImportService
from datasheet_studio.models.pdf_document import PdfNote
from datasheet_studio.services.ai_service import AIService
from datasheet_studio.services.library_service import LibraryService
from datasheet_studio.ui.library_panel import LibraryPanel
from datasheet_studio.ui.dialogs.add_to_library_dialog import AddToLibraryDialog
from datasheet_studio.core.logging import get_log_text
from datasheet_studio.tools import ToolContext, create_default_tool_registry


class _AutoHeightTextBrowser(QTextBrowser):
    """QTextBrowser that always expands to fit its document height.

    Fixes the classic Qt bug where a QTextBrowser inside a scroll layout
    collapses to a tiny/zero height: when ``setHtml`` runs the document has no
    width yet, so its size is 0x0 and ``AdjustToContents`` never re-computes
    after the widget receives a real width. Implementing ``heightForWidth``
    makes the layout lay the document out with the actual width and return the
    true content height.
    """

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        self.document().setTextWidth(max(10, width - self.frameWidth() * 2))
        return int(self.document().size().height()) + self.frameWidth() * 2

    def resizeEvent(self, event) -> None:
        self.document().setTextWidth(self.viewport().width())
        super().resizeEvent(event)


class _ChatMessageWidget(QWidget):
    """A single chat message bubble (user right / AI left), DeepSeek-style."""

    def __init__(self, role: str, content: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # Column with a small role label above the bubble.
        col = QVBoxLayout()
        col.setSpacing(3)

        role_label = QLabel("You" if role == "user" else "Assistant")
        role_label.setStyleSheet(
            "font-size: 11px; color: #8b8b8b; font-weight: 600;"
            " background: transparent; padding-left: 4px;"
        )
        role_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        bubble = QFrame()
        if role == "user":
            bubble.setStyleSheet(
                "QFrame { background-color: #2f6fed; border-radius: 14px;"
                " border: none; }"
            )
        else:
            bubble.setStyleSheet(
                "QFrame { background-color: #f1f3f5; border-radius: 14px;"
                " border: 1px solid #e3e6ea; }"
            )

        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(12, 9, 12, 9)
        inner.setSpacing(0)

        max_w = 620
        if parent is not None and parent.viewport() is not None:
            max_w = max(240, int(parent.viewport().width() * 0.82))
        bubble.setMaximumWidth(max_w)

        if role == "user":
            label = QLabel(html_escape(content).replace("\n", "<br>"))
            label.setWordWrap(True)
            label.setStyleSheet(
                "color: #ffffff; background: transparent; font-size: 13px;"
            )
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            inner.addWidget(label)
            col.addWidget(role_label, alignment=Qt.AlignmentFlag.AlignRight)
            col.addWidget(bubble)
            outer.addStretch(1)
            outer.addLayout(col)
        else:
            browser = _AutoHeightTextBrowser()
            browser.setHtml(markdown_to_html(content))
            browser.setOpenExternalLinks(True)
            browser.setStyleSheet(
                "QTextBrowser { background: transparent; border: none;"
                " color: #1f2328; font-size: 13px; }"
            )
            browser.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            browser.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            browser.setFrameShape(QFrame.Shape.NoFrame)
            inner.addWidget(browser)
            col.addWidget(role_label, alignment=Qt.AlignmentFlag.AlignLeft)
            col.addWidget(bubble)
            outer.addLayout(col)
            outer.addStretch(1)


class _AiToolBridge(QObject):
    """Run AI tool calls on the GUI thread and return results to the worker."""

    request = Signal(str, str)  # tool name, JSON-encoded arguments

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__()
        self._owner = owner
        self._event: threading.Event | None = None
        self._result_json = "{}"
        self.request.connect(self._handle_request, Qt.ConnectionType.QueuedConnection)

    @Slot(str, str)
    def _handle_request(self, name: str, args_json: str) -> None:
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            result = self._owner._execute_ai_tool(name, args)
        except Exception as exc:  # noqa: BLE001 - never hang the worker thread
            result = {"error": str(exc)}
        self._result_json = json.dumps(result, ensure_ascii=False)
        if self._event is not None:
            self._event.set()

    def execute(self, name: str, args: dict) -> dict:
        """Called from the worker thread; runs the tool on the GUI thread."""
        self._event = threading.Event()
        self._result_json = "{}"
        self.request.emit(name, json.dumps(args))
        if not self._event.wait(timeout=30):
            return {"error": "tool execution timed out"}
        return json.loads(self._result_json)


class MainWindow(QMainWindow):
    """Primary window of the Datasheet Studio application."""

    def __init__(self) -> None:
        super().__init__()

        self._reader = PdfReader()
        self._pdf_info: PdfDocumentInfo | None = None
        self._current_page = 1
        self._zoom = 1.0
        self._selected_pages: dict[int, SelectedPage] = {}  # page_number -> SelectedPage
        self._settings = QSettings()
        
        # Initialize AI service
        self._ai_service = AIService()
        self._log = logging.getLogger("datasheet_studio.ui")

        # Local datasheet library
        self._library_service = LibraryService()

        # Engineering tools are registered independently from menu rendering.
        self._tool_registry = create_default_tool_registry()

        self.setWindowTitle(APP_NAME)
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self._log.info("MainWindow created (version %s)", APP_VERSION)

        self._create_central_area()
        self._create_menu_bar()
        self._create_status_bar()

        self._restore_library_on_startup()

    def _restore_library_on_startup(self) -> None:
        """Reopen the last used library folder if it still exists."""
        folder = self._settings.value("libraryPath", "")
        if not folder:
            return
        from pathlib import Path as FsPath

        if not FsPath(folder).is_dir():
            self.statusBar().showMessage(
                "The last library folder is no longer available.", 5000
            )
            return
        try:
            self._library_service.open_library(folder)
        except Exception as exc:  # noqa: BLE001 - never block startup
            self._log.warning("Could not restore library %s: %s", folder, exc)
            return
        self._library_panel.refresh()
        self._log.info("Restored library on startup: %s", folder)

    def closeEvent(self, event) -> None:
        """Finish bounded local search work before Qt destroys its threads."""

        if hasattr(self, "_search_strip"):
            self._search_strip.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Central layout
    # ------------------------------------------------------------------

    def _create_central_area(self) -> None:
        """Create the four primary resizable workspace panels."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._create_bookmarks_library_panel())
        splitter.addWidget(self._create_document_viewer_panel())
        splitter.addWidget(self._create_selected_pages_panel())
        splitter.addWidget(self._create_ai_panel())

        # Left-to-right: bookmarks/library, viewer, selected pages, AI.
        splitter.setSizes(DEFAULT_PANEL_SIZES)

        self.setCentralWidget(splitter)
        self._workspace_splitter = splitter
        self._create_bottom_search_strip()

    def _create_bottom_search_strip(self) -> None:
        """Dock the Phase-6 search entry point below the workspace splitter."""

        self._online_import_service = OnlineImportService(
            vault_path_getter=lambda: str(
                self._settings.value("knowledgeBasePath", "") or ""
            )
        )
        self._search_strip = SearchStrip(
            vault_path_getter=lambda: str(
                self._settings.value("knowledgeBasePath", "") or ""
            ),
            service_factory=self._build_search_service,
            parent=self,
        )
        self._search_strip.open_requested.connect(self._open_search_result)
        self._search_strip.preview_requested.connect(self._preview_online_result)
        self._search_strip.save_requested.connect(self._save_online_result)
        self._search_strip.web_search_requested.connect(self._open_datasheet_browser)
        self._search_strip.expanded_changed.connect(self._resize_search_dock)

        dock = QDockWidget(self)
        dock.setObjectName("bottomSearchDock")
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setTitleBarWidget(QWidget(dock))
        dock.setWidget(self._search_strip)
        self._search_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self._resize_search_dock(False)

    def _build_search_service(self):
        """Build the Phase-6 provider set from current local settings."""

        from datasheet_studio.infrastructure.web.digikey import DigiKeyCredentials
        from datasheet_studio.services.search_service import create_search_service

        def digikey_credentials():
            enabled = self._settings.value(
                "onlineSources/digikeyEnabled", False, type=bool
            )
            if not enabled:
                return None
            return DigiKeyCredentials(
                client_id=str(
                    self._settings.value("onlineSources/digikeyClientId", "") or ""
                ),
                client_secret=str(
                    self._settings.value("onlineSources/digikeyClientSecret", "") or ""
                ),
            )

        return create_search_service(
            vault_path=str(self._settings.value("knowledgeBasePath", "") or ""),
            digikey_getter=digikey_credentials,
        )

    def _run_online_action(self, label: str, action) -> QThread:
        """Run a bounded online action off the GUI thread."""

        self.statusBar().showMessage(label, 0)

        class _Worker(QThread):
            done = Signal(object)
            failed = Signal(str)

            def run(self_inner) -> None:
                try:
                    self_inner.done.emit(action())
                except Exception as exc:  # noqa: BLE001 - report, never crash
                    self_inner.failed.emit(str(exc))

        worker = _Worker(self)
        self._online_workers = getattr(self, "_online_workers", [])
        self._online_workers.append(worker)

        def _cleanup() -> None:
            if worker in self._online_workers:
                self._online_workers.remove(worker)
            self.statusBar().showMessage("", 2000)

        def _done(result) -> None:
            _cleanup()

        def _failed(message: str) -> None:
            _cleanup()
            QMessageBox.warning(self, "منبع آنلاین", message)

        worker.done.connect(_done)
        worker.failed.connect(_failed)
        worker.start()
        return worker

    def _preview_online_result(self, result) -> None:
        """Download a temp copy and open it in the viewer (no storing)."""

        worker = self._run_online_action(
            f"در حال دانلود پیش‌نمایش: {result.title}…",
            lambda: self._online_import_service.download_pdf(result.url),
        )
        worker.done.connect(
            lambda downloaded: self._open_library_item(str(downloaded.path))
        )

    def _save_online_result(self, result) -> None:
        """Download, validate, and save an online PDF into the v2 vault."""

        def _save():
            downloaded = self._online_import_service.download_pdf(result.url)
            return self._online_import_service.save_to_vault(
                downloaded,
                manufacturer=result.subtitle,
                part_number=result.title,
                title=result.title,
            )

        worker = self._run_online_action(
            f"در حال ذخیره {result.title} در کتابخانه…", _save
        )

        def _saved(outcome) -> None:
            duplicate = (
                " (محتوای تکراری — شیء منبع موجود بود)" if outcome.duplicate else ""
            )
            message = f"ذخیره شد: {result.title}{duplicate}"
            self.statusBar().showMessage(message, 5000)
            self._search_strip.display_message(f"✅ {message}")

        worker.done.connect(_saved)

    def _open_online_sources_settings(self) -> None:
        from datasheet_studio.ui.dialogs.online_sources_dialog import (
            OnlineSourcesDialog,
        )

        OnlineSourcesDialog(self).exec()

    @Slot(bool)
    def _resize_search_dock(self, expanded: bool) -> None:
        self._search_dock.setFixedHeight(270 if expanded else 42)

    # ------------------------------------------------------------------
    # Panel: bookmarks / library (left)
    # ------------------------------------------------------------------

    def _create_bookmarks_library_panel(self) -> QWidget:
        """Create the left panel with Bookmarks and Library views."""
        panel = self._create_panel("Navigation", "bookmarks_library_panel")

        tabs = QTabWidget()
        tabs.addTab(self._create_bookmarks_view(), "Bookmarks")
        tabs.addTab(self._create_library_panel(), "Library")

        panel.layout().addWidget(tabs, 1)
        return panel

    def _create_library_panel(self) -> QWidget:
        """Create the real local datasheet library panel."""
        self._library_panel = LibraryPanel(self._library_service, self)
        self._library_panel.open_pdf_requested.connect(self._open_library_item)
        self._library_panel.open_summary_requested.connect(self._open_summary_file)
        self._library_panel.add_current_pdf_requested.connect(
            self._add_current_pdf_to_library
        )
        self._library_panel.status_message.connect(
            lambda msg: self.statusBar().showMessage(msg, 3000)
        )
        return self._library_panel

    def _create_bookmarks_view(self) -> QWidget:
        """Create the PDF bookmarks tree view with context menu support."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._bookmarks_tree = QTreeWidget()
        self._bookmarks_tree.setHeaderHidden(True)
        self._bookmarks_tree.itemClicked.connect(self._on_bookmark_clicked)
        self._bookmarks_tree.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
        self._bookmarks_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._bookmarks_tree.customContextMenuRequested.connect(self._on_bookmark_context_menu)

        hint = QLabel("Open a datasheet to display its bookmarks.")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(hint)
        layout.addWidget(self._bookmarks_tree, 1)
        return page

    # ------------------------------------------------------------------
    # Panel: document viewer (central)
    # ------------------------------------------------------------------

    def _create_document_viewer_panel(self) -> QWidget:
        """Create the central PDF document viewer with navigation."""
        panel = self._create_panel("Document Viewer", "document_viewer_panel")
        layout = panel.layout()

        # Toolbar row: zoom out, zoom in, page indicator, prev/next buttons.
        toolbar = QHBoxLayout()
        self._zoom_out_button = QPushButton("Zoom Out")
        self._zoom_in_button = QPushButton("Zoom In")
        self._zoom_fit_button = QPushButton("🔍 Fit")
        self._zoom_fit_button.setToolTip("Zoom to fit page in viewer")
        self._zoom_fit_button.setEnabled(False)
        self._zoom_fit_button.clicked.connect(self._zoom_to_fit)
        
        self._page_label = QLabel("No document")
        self._prev_page_button = QPushButton("◀ Prev")
        self._next_page_button = QPushButton("Next ▶")
        
        # Note button - add note for current page
        self._note_button = QPushButton("📝 Add Note")
        self._note_button.setToolTip("Add a note to the current page")
        self._note_button.setEnabled(False)
        self._note_button.clicked.connect(self._add_note_to_current_page)
        
        # Manage notes button
        self._manage_notes_button = QPushButton("📋 Manage Notes")
        self._manage_notes_button.setToolTip("View and edit all notes for this document")
        self._manage_notes_button.setEnabled(False)
        self._manage_notes_button.clicked.connect(self._manage_notes)

        self._zoom_out_button.setEnabled(False)
        self._zoom_in_button.setEnabled(False)
        self._prev_page_button.setEnabled(False)
        self._next_page_button.setEnabled(False)

        self._zoom_out_button.clicked.connect(self._zoom_out)
        self._zoom_in_button.clicked.connect(self._zoom_in)
        self._prev_page_button.clicked.connect(self._go_to_previous_page)
        self._next_page_button.clicked.connect(self._go_to_next_page)

        toolbar.addWidget(self._prev_page_button)
        toolbar.addWidget(self._zoom_out_button)
        toolbar.addWidget(self._zoom_in_button)
        toolbar.addWidget(self._zoom_fit_button)
        toolbar.addWidget(self._next_page_button)
        toolbar.addWidget(self._note_button)
        toolbar.addWidget(self._manage_notes_button)
        toolbar.addStretch()
        toolbar.addWidget(self._page_label)
        layout.addLayout(toolbar)

        # Page range input row
        range_layout = QHBoxLayout()
        range_label = QLabel("Page Range:")
        self._page_range_input = QLineEdit()
        self._page_range_input.setPlaceholderText("e.g., 14-33 or 5,10,15-20")
        self._page_range_input.setToolTip("Enter page range (e.g., 14-33 or 5,10,15-20)")
        self._page_range_input.setEnabled(False)
        self._page_range_input.returnPressed.connect(self._add_page_range_to_selected)
        
        add_range_button = QPushButton("➕ Add to Selected")
        add_range_button.setToolTip("Add page range to selected pages")
        add_range_button.setEnabled(False)
        add_range_button.clicked.connect(self._add_page_range_to_selected)
        self._add_range_button = add_range_button

        range_layout.addWidget(range_label)
        range_layout.addWidget(self._page_range_input, 1)
        range_layout.addWidget(add_range_button)
        layout.addLayout(range_layout)

        # Scrollable viewer label with custom scroll area.
        self._viewer_label = QLabel(
            "Open a datasheet to view its pages.\n\n"
            "Use File > Open Datasheet..., or double-click a page\n"
            "to select it."
        )
        self._viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._viewer_label.setMinimumSize(200, 200)
        self._viewer_label.setMouseTracking(True)

        # Note overlay on top of the viewer label
        self._note_overlay = NoteOverlayWidget(self._viewer_label)
        self._note_overlay.note_double_clicked.connect(self._edit_note)
        self._note_overlay.note_selected.connect(self._on_note_selected)
        self._note_overlay.empty_area_double_clicked.connect(self._on_empty_area_double_clicked)
        self._notes_by_page: dict[int, list[PdfNote]] = {}
        
        # Position the overlay to cover the viewer label
        self._note_overlay.setGeometry(0, 0, self._viewer_label.width(), self._viewer_label.height())

        self._scroll_area = PdfScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._viewer_label)
        self._scroll_area.zoom_requested.connect(self._on_scroll_zoom)
        self._scroll_area.page_navigation_requested.connect(self._on_scroll_page_navigation)

        # Right-click-drag panning: let the note overlay drive the scroll area.
        self._note_overlay.set_scroll_area(self._scroll_area)

        layout.addWidget(self._scroll_area, 1)

        return panel

    # ------------------------------------------------------------------
    # Panel: selected pages
    # ------------------------------------------------------------------

    def _create_selected_pages_panel(self) -> QWidget:
        """Create the panel that holds selected PDF pages (simple list)."""
        panel = self._create_panel("Selected Pages", "selected_pages_panel")

        # Header with count
        self._selected_count_label = QLabel("0 pages selected")
        self._selected_count_label.setStyleSheet("color: gray; font-size: 12px;")
        panel.layout().addWidget(self._selected_count_label)

        # Simple list widget for selected pages
        self._selected_pages_list = QListWidget()
        self._selected_pages_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self._selected_pages_list.itemClicked.connect(self._on_selected_page_clicked)
        self._selected_pages_list.itemDoubleClicked.connect(
            self._on_selected_page_double_clicked
        )

        panel.layout().addWidget(self._selected_pages_list, 1)

        # Clear button
        self._clear_selected_button = QPushButton("Clear All")
        self._clear_selected_button.setEnabled(False)
        self._clear_selected_button.clicked.connect(self._clear_selected_pages)
        panel.layout().addWidget(self._clear_selected_button)

        # Save/Compress buttons with compression level
        from PySide6.QtWidgets import QComboBox

        save_compress_layout = QHBoxLayout()
        save_compress_layout.setSpacing(4)

        # Save button
        self._save_selection_button = QPushButton("💾 Save")
        self._save_selection_button.setToolTip("Save selected pages to file")
        self._save_selection_button.setEnabled(False)
        self._save_selection_button.clicked.connect(self._save_selection)
        save_compress_layout.addWidget(self._save_selection_button)

        # Compress button
        self._compress_selection_button = QPushButton("🗜️ Compress")
        self._compress_selection_button.setToolTip(
            "Compress and save selected pages as a smaller PDF file"
        )
        self._compress_selection_button.setEnabled(False)
        self._compress_selection_button.clicked.connect(self._compress_selection)
        save_compress_layout.addWidget(self._compress_selection_button)

        # Compression level combo box
        self._compression_level_combo = QComboBox()
        self._compression_level_combo.addItems(["Fast", "Normal", "Best"])
        self._compression_level_combo.setCurrentIndex(1)  # Normal
        self._compression_level_combo.setToolTip("Compression level")
        self._compression_level_combo.setEnabled(False)
        self._compression_level_combo.setFixedWidth(70)
        save_compress_layout.addWidget(self._compression_level_combo)

        panel.layout().addLayout(save_compress_layout)

        return panel

    # ------------------------------------------------------------------
    # Panel: AI assistant (right)
    # ------------------------------------------------------------------

    def _create_ai_panel(self) -> QWidget:
        """Create the AI assistant panel with Chat, Summary, Report, and Settings tabs."""
        panel = self._create_panel("AI Assistant", "ai_panel")

        tabs = QTabWidget()
        tabs.addTab(self._create_ai_chat_placeholder(), "Chat")
        tabs.addTab(self._create_ai_summary_placeholder(), "Summary")
        tabs.addTab(self._create_ai_report_placeholder(), "Report")
        tabs.addTab(self._create_ai_settings_tab(), "⚙️ Settings")

        panel.layout().addWidget(tabs, 1)
        return panel

    def _create_ai_settings_tab(self) -> QWidget:
        """Create the AI settings tab for API configuration."""
        from PySide6.QtWidgets import (
            QComboBox,
            QFormLayout,
            QGroupBox,
            QLineEdit,
        )

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # API Configuration Group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(8)

        # Provider selection
        self._ai_provider_combo = QComboBox()
        self._ai_provider_combo.addItems([
            "DeepSeek",
            "OpenAI",
            "Anthropic",
            "Google Gemini",
            "Custom",
        ])
        self._ai_provider_combo.currentTextChanged.connect(self._on_ai_provider_changed)
        api_layout.addRow("Provider:", self._ai_provider_combo)

        # Protocol selection (for Custom provider)
        self._ai_protocol_combo = QComboBox()
        self._ai_protocol_combo.addItems([
            "OpenAI Compatible",
            "Anthropic API",
            "Custom REST",
        ])
        self._ai_protocol_combo.setToolTip("API protocol to use")
        self._ai_protocol_combo.setVisible(False)  # Hidden by default
        api_layout.addRow("Protocol:", self._ai_protocol_combo)

        # Base URL (for Custom provider)
        self._ai_base_url_input = QLineEdit()
        self._ai_base_url_input.setPlaceholderText("https://api.example.com/v1")
        self._ai_base_url_input.setToolTip("Base URL for custom API endpoint")
        self._ai_base_url_input.setVisible(False)  # Hidden by default
        api_layout.addRow("Base URL:", self._ai_base_url_input)

        # Model selection
        self._ai_model_combo = QComboBox()
        self._ai_model_combo.setEditable(True)
        api_layout.addRow("Model:", self._ai_model_combo)

        # Fetch models button (for Custom provider)
        fetch_models_button = QPushButton("🔄 Fetch Models")
        fetch_models_button.setToolTip("Fetch available models from the API")
        fetch_models_button.setVisible(False)
        fetch_models_button.clicked.connect(self._fetch_ai_models)
        self._fetch_models_button = fetch_models_button
        api_layout.addRow("", fetch_models_button)

        # API Key input
        self._ai_api_key_input = QLineEdit()
        self._ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_api_key_input.setPlaceholderText("Enter your API key...")
        api_layout.addRow("API Key:", self._ai_api_key_input)

        # Quality selection
        self._ai_quality_combo = QComboBox()
        self._ai_quality_combo.addItems(["Low", "Medium", "High"])
        self._ai_quality_combo.setCurrentIndex(2)  # High
        api_layout.addRow("Quality:", self._ai_quality_combo)

        layout.addWidget(api_group)

        # Buttons
        button_layout = QHBoxLayout()
        
        test_button = QPushButton("🔌 Test Connection")
        test_button.clicked.connect(self._test_ai_connection)
        button_layout.addWidget(test_button)

        save_button = QPushButton("💾 Save Settings")
        save_button.clicked.connect(self._save_ai_settings)
        button_layout.addWidget(save_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        # Load saved settings
        self._load_ai_settings()
        self._on_ai_provider_changed(self._ai_provider_combo.currentText())
        # Restore the saved model after the provider model list is populated
        saved_model = self._settings.value("ai/model", "")
        if saved_model:
            self._ai_model_combo.setCurrentText(saved_model)

        return page

    def _on_ai_provider_changed(self, provider: str) -> None:
        """Update model list and show/hide custom fields based on selected provider."""
        self._ai_model_combo.clear()
        
        # Show/hide custom provider fields
        is_custom = provider == "Custom"
        self._ai_protocol_combo.setVisible(is_custom)
        self._ai_base_url_input.setVisible(is_custom)
        self._fetch_models_button.setVisible(is_custom)
        
        models = {
            "DeepSeek": ["deepseek-chat", "deepseek-reasoner"],
            "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "Anthropic": [
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ],
            "Google Gemini": [
                "gemini-2.0-flash",
                "gemini-2.0-flash-lite",
                "gemini-1.5-pro",
            ],
            "Custom": [],
        }
        
        self._ai_model_combo.addItems(models.get(provider, []))
        
        # Update AI interface state
        self._update_ai_interface_state()

    def _save_ai_settings(self) -> None:
        """Save AI settings to QSettings."""
        self._settings.setValue("ai/provider", self._ai_provider_combo.currentText())
        self._settings.setValue("ai/protocol", self._ai_protocol_combo.currentText())
        self._settings.setValue("ai/baseURL", self._ai_base_url_input.text())
        self._settings.setValue("ai/model", self._ai_model_combo.currentText())
        self._settings.setValue("ai/apiKey", self._ai_api_key_input.text())
        self._settings.setValue("ai/quality", self._ai_quality_combo.currentText())

        self._configure_ai_service()
        self._log.info(
            "AI settings saved: provider=%s model=%s base_url=%s",
            self._ai_provider_combo.currentText(),
            self._ai_model_combo.currentText(),
            self._ai_base_url_input.text(),
        )
        self.statusBar().showMessage("AI settings saved", 2000)

        # Update AI interface state based on new settings
        self._update_ai_interface_state()

    def _load_ai_settings(self) -> None:
        """Load AI settings from QSettings."""
        provider = self._settings.value("ai/provider", "DeepSeek")
        protocol = self._settings.value("ai/protocol", "OpenAI Compatible")
        base_url = self._settings.value("ai/baseURL", "")
        model = self._settings.value("ai/model", "deepseek-chat")
        api_key = self._settings.value("ai/apiKey", "")
        quality = self._settings.value("ai/quality", "High")

        # Find and set provider
        idx = self._ai_provider_combo.findText(provider)
        if idx >= 0:
            self._ai_provider_combo.setCurrentIndex(idx)

        # Set protocol
        idx = self._ai_protocol_combo.findText(protocol)
        if idx >= 0:
            self._ai_protocol_combo.setCurrentIndex(idx)

        # Set base URL
        self._ai_base_url_input.setText(base_url)

        # Set model (after provider is set so the combo is populated)
        self._ai_model_combo.setCurrentText(model)

        # Set API key
        self._ai_api_key_input.setText(api_key)

        # Set quality
        idx = self._ai_quality_combo.findText(quality)
        if idx >= 0:
            self._ai_quality_combo.setCurrentIndex(idx)

        # Update AI interface state based on loaded settings
        self._update_ai_interface_state()

        self._configure_ai_service()
        self._log.info(
            "AI settings loaded: provider=%s model=%s has_api_key=%s",
            self._ai_provider_combo.currentText(),
            self._ai_model_combo.currentText(),
            bool(api_key),
        )

    def _update_ai_interface_state(self) -> None:
        """Update the AI interface based on whether an API key is configured."""
        api_key = self._ai_api_key_input.text().strip() if hasattr(self, "_ai_api_key_input") else ""
        has_api_key = bool(api_key)

        if hasattr(self, "_ai_chat_input"):
            self._ai_chat_input.setEnabled(has_api_key)
        if hasattr(self, "_ai_send_button"):
            self._ai_send_button.setEnabled(has_api_key)
        if hasattr(self, "_ai_summary_button"):
            self._ai_summary_button.setEnabled(has_api_key)
        if hasattr(self, "_ai_report_button"):
            self._ai_report_button.setEnabled(has_api_key)

    def _ai_tools_schema(self) -> list[dict]:
        """Declare the tools the AI model may call."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_bookmarks",
                    "description": (
                        "Return the document outline (bookmarks) of the currently "
                        "open datasheet: title, 1-based page number, and level."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_pages_to_selection",
                    "description": (
                        "Add one or more 1-based page numbers to the Selected "
                        "Pages list of the application."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "1-based page numbers to add",
                            }
                        },
                        "required": ["page_numbers"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "navigate_to_page",
                    "description": (
                        "Navigate the document viewer to a 1-based page number."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "1-based page number",
                            }
                        },
                        "required": ["page"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_page_text",
                    "description": (
                        "Return the extracted text of a 1-based page of the "
                        "currently open datasheet. Note: for questions about "
                        "pinouts, packages, or alternate functions prefer the "
                        "get_pinout tool, which returns clean structured table "
                        "data."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "1-based page number",
                            }
                        },
                        "required": ["page"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pinout",
                    "description": (
                        "Return the full pinout table of the currently open "
                        "datasheet for a package name (e.g. LQFP48, LQFP64, "
                        "LQFP100, UFQFPN32, UFQFPN48). Each row contains the "
                        "package pin number, pin name, pin type, all alternate "
                        "functions with their AF number when available, and "
                        "additional functions. Use this for questions about "
                        "pin names, pin numbering, or alternate functions "
                        "instead of get_page_text."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "package": {
                                "type": "string",
                                "description": "Package name, e.g. LQFP48",
                            }
                        },
                        "required": ["package"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_packages",
                    "description": (
                        "Return the list of packages (schematic symbol "
                        "variants) defined in the currently open datasheet, "
                        "each with its pin count (e.g. SO8N 8 pins, TSSOP20 20 "
                        "pins, LQFP48 48 pins). Use this to answer questions "
                        "about which packages are available or their pin "
                        "counts."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
        ]

    def _get_bookmarks_for_ai(self) -> list[dict]:
        """Return the bookmarks of the open document for the AI model."""
        if self._pdf_info is None:
            return []
        return [
            {"title": b.title, "page": b.page, "level": b.level}
            for b in self._pdf_info.bookmarks
        ]

    def _execute_ai_tool(self, name: str, args: dict) -> dict:
        """Execute a tool requested by the AI and return a serializable result."""
        self._log.info("AI tool call: %s %s", name, args)
        try:
            if name == "get_bookmarks":
                return {"bookmarks": self._get_bookmarks_for_ai()}

            if name == "add_pages_to_selection":
                added = []
                pages = args.get("page_numbers") or []
                for page in pages:
                    try:
                        page_number = int(page)
                    except (TypeError, ValueError):
                        continue
                    if self._pdf_info is None or not (
                        1 <= page_number <= self._pdf_info.page_count
                    ):
                        continue
                    if page_number not in self._selected_pages:
                        self._add_page_to_selected(page_number)
                        added.append(page_number)
                return {"added": added, "selected": sorted(self._selected_pages)}

            if name == "navigate_to_page":
                page_number = int(args.get("page", 1))
                self._navigate_to_page(page_number)
                return {"ok": True, "page": page_number}

            if name == "get_page_text":
                if self._pdf_info is None:
                    return {"error": "no document open"}
                page_number = int(args.get("page", 1))
                text = self._reader.get_page_text(self._pdf_info.path, page_number)
                return {"page": page_number, "text": text[:4000]}

            if name == "get_pinout":
                if self._pdf_info is None:
                    return {"error": "no document open"}
                package = str(args.get("package") or "LQFP48")
                rows = self._reader.get_pinout(self._pdf_info.path, package)
                if not rows:
                    return {
                        "error": f"no pinout table found for package {package}",
                        "package": package,
                    }
                return {"package": package, "count": len(rows), "rows": rows}

            if name == "get_packages":
                if self._pdf_info is None:
                    return {"error": "no document open"}
                packages = self._reader.get_available_packages(
                    self._pdf_info.path
                )
                return {"packages": packages, "count": len(packages)}

            return {"error": f"unknown tool: {name}"}
        except Exception as exc:
            self._log.exception("AI tool %s failed", name)
            return {"error": str(exc)}

    def _send_ai_message(self, force_message: str | None = None) -> None:
        """Send a message to the AI service (supports tool/function calls)."""
        if not hasattr(self, '_ai_chat_input') or not self._ai_chat_input:
            return

        if force_message is not None:
            message = force_message.strip()
        else:
            message = self._ai_chat_input.toPlainText().strip()
        if not message:
            return

        self._configure_ai_service()
        context = self._build_ai_context()
        tools = self._ai_tools_schema()
        self._log.info(
            "AI chat send: message=%r context_chars=%d tools=%d",
            message[:80],
            len(context),
            len(tools),
        )

        self._last_user_message = message
        self._append_ai_message("user", message)
        if not force_message:
            self._ai_chat_input.clear()
        self._retry_button.setEnabled(True)
        self._save_chat_md_button.setEnabled(True)

        # Status indicator ("thinking..." with an elapsed-seconds counter)
        self._start_ai_status_timer()

        from PySide6.QtCore import QThread, Signal

        bridge = _AiToolBridge(self)

        class AIWorker(QThread):
            result_ready = Signal(str)

            def __init__(self, ai_service, message, context, tools, tool_executor):
                super().__init__()
                self.ai_service = ai_service
                self.message = message
                self.context = context
                self.tools = tools
                self.tool_executor = tool_executor

            def run(self):
                try:
                    response = self.ai_service.chat(
                        [{"role": "user", "content": self.message}],
                        context=self.context,
                        tools=self.tools,
                        tool_executor=self.tool_executor,
                    )
                    self.result_ready.emit(response)
                except Exception as e:
                    self.result_ready.emit(f"Error: {e}")

        def on_result(result):
            self._stop_ai_status_timer()
            is_error = result.startswith("Error:")
            self._ai_status_label.setText("⚠ Error" if is_error else "✓ Done")
            self._append_ai_message("assistant", result)
            self.statusBar().showMessage(
                "AI response received" if not is_error else "AI request failed",
                2000,
            )
            self._log.info("AI chat response received (%d chars)", len(result))

        worker = AIWorker(self._ai_service, message, context, tools, bridge.execute)
        worker.result_ready.connect(on_result)
        worker.start()

        if not hasattr(self, '_ai_jobs'):
            self._ai_jobs = []
        self._ai_jobs.append((worker, bridge))
        self._ai_jobs = [(w, b) for (w, b) in self._ai_jobs if not w.isFinished()]
    def _retry_last_ai_message(self) -> None:
        """Re-send the last user message (retry the previous request)."""
        last = getattr(self, "_last_user_message", "")
        if not last:
            return
        self._log.info("AI retry: %r", last[:80])
        self._send_ai_message(force_message=last)

    def _append_ai_message(self, role: str, content: str) -> None:
        """Append a chat message and re-render the conversation."""
        if not hasattr(self, "_ai_chat_messages"):
            self._ai_chat_messages = []
        self._ai_chat_messages.append({"role": role, "content": content})
        self._render_ai_chat()
        if hasattr(self, "_save_chat_md_button"):
            self._save_chat_md_button.setEnabled(True)

    def _render_ai_chat(self) -> None:
        """Rebuild the chat bubble list from the message history."""
        # Remove all widgets except the trailing stretch.
        while self._ai_chat_layout.count() > 1:
            item = self._ai_chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for msg in self._ai_chat_messages:
            self._ai_chat_layout.insertWidget(
                self._ai_chat_layout.count() - 1,
                _ChatMessageWidget(msg["role"], msg["content"], self._ai_chat_scroll),
            )
        QTimer.singleShot(
            0,
            lambda: self._ai_chat_scroll.verticalScrollBar().setValue(
                self._ai_chat_scroll.verticalScrollBar().maximum()
            ),
        )

    def _clear_ai_chat(self) -> None:
        """Clear the chat history."""
        self._ai_chat_messages = []
        self._last_user_message = ""
        while self._ai_chat_layout.count() > 1:
            item = self._ai_chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if hasattr(self, "_ai_status_label"):
            self._ai_status_label.setText("")
        if hasattr(self, "_retry_button"):
            self._retry_button.setEnabled(False)
        if hasattr(self, "_save_chat_md_button"):
            self._save_chat_md_button.setEnabled(False)

    def _start_ai_status_timer(self) -> None:
        self._ai_status_start = time.monotonic()
        self._ai_status_label.setText("⏳ Thinking...")
        if not hasattr(self, "_ai_status_timer"):
            self._ai_status_timer = QTimer(self)
            self._ai_status_timer.setInterval(1000)
            self._ai_status_timer.timeout.connect(self._on_ai_status_tick)
        self._ai_status_timer.start()

    def _on_ai_status_tick(self) -> None:
        elapsed = int(time.monotonic() - self._ai_status_start)
        self._ai_status_label.setText(f"⏳ Thinking... {elapsed}s")

    def _stop_ai_status_timer(self) -> None:
        if hasattr(self, "_ai_status_timer"):
            self._ai_status_timer.stop()

    def _save_chat_markdown(self) -> None:
        """Save the current chat history as a Markdown file."""
        messages = getattr(self, "_ai_chat_messages", [])
        if not messages:
            QMessageBox.information(self, "No Chat", "There is no chat to save yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Chat as Markdown", "",
            "Markdown Files (*.md);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".md"):
            path += ".md"
        try:
            lines = [
                "# Datasheet Studio — AI Chat",
                "",
                f"- Date: {datetime.now().isoformat(timespec='seconds')}",
                f"- Provider: {self._ai_provider_combo.currentText()}",
                f"- Model: {self._ai_model_combo.currentText()}",
                f"- Document: {self._pdf_info.path if self._pdf_info else '—'}",
                "",
            ]
            for msg in messages:
                role = "You" if msg["role"] == "user" else "AI"
                lines.append(f"## {role}\n\n{msg['content']}\n")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.statusBar().showMessage(f"Chat saved to {path}", 3000)
            self._log.info("AI chat saved to %s", path)
        except Exception as exc:
            self._log.exception("Failed to save chat")
            QMessageBox.critical(self, "Save Failed", f"Failed to save chat:\n{exc}")

    def _fetch_ai_models(self) -> None:
        """Fetch available models from the custom API endpoint."""
        api_key = self._ai_api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please enter an API key first.")
            return

        base_url = self._ai_base_url_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, "No Base URL", "Please enter a base URL first.")
            return

        self._configure_ai_service()
        self.statusBar().showMessage("Fetching models...", 0)
        self._log.info(
            "AI fetch_models: provider=%s base_url=%s",
            self._ai_provider_combo.currentText(),
            base_url,
        )

        from PySide6.QtCore import QThread, Signal

        class FetchWorker(QThread):
            result_ready = Signal(list, str)

            def __init__(self, ai_service):
                super().__init__()
                self.ai_service = ai_service

            def run(self):
                try:
                    models = self.ai_service.fetch_models()
                    self.result_ready.emit(models, "")
                except Exception as e:
                    self.result_ready.emit([], str(e))

        def on_result(models, error):
            if error:
                self._log.error("AI fetch_models failed: %s", error)
                QMessageBox.warning(
                    self, "Fetch Models", f"Could not fetch models:\n{error}"
                )
                return
            if not models:
                QMessageBox.information(
                    self,
                    "Fetch Models",
                    "No models returned. You can type a model name manually.",
                )
                return
            self._ai_model_combo.clear()
            self._ai_model_combo.addItems(models)
            self.statusBar().showMessage(f"Loaded {len(models)} models", 2000)
            self._log.info("AI fetch_models loaded %d models", len(models))

        worker = FetchWorker(self._ai_service)
        worker.result_ready.connect(on_result)
        worker.start()

        if not hasattr(self, "_fetch_workers"):
            self._fetch_workers = []
        self._fetch_workers.append(worker)
        self._fetch_workers = [w for w in self._fetch_workers if not w.isFinished()]
    def _test_ai_connection(self) -> None:
        """Test the AI API connection."""
        api_key = self._ai_api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please enter an API key first.")
            return

        self._configure_ai_service()
        provider = self._ai_provider_combo.currentText()
        model = self._ai_model_combo.currentText()
        self.statusBar().showMessage("Testing connection...", 0)
        self._log.info("AI test_connection: provider=%s model=%s", provider, model)

        from PySide6.QtCore import QThread, Signal

        class TestWorker(QThread):
            result_ready = Signal(str, bool)

            def __init__(self, ai_service):
                super().__init__()
                self.ai_service = ai_service

            def run(self):
                try:
                    reply = self.ai_service.test_connection()
                    self.result_ready.emit(reply, True)
                except Exception as e:
                    self.result_ready.emit(str(e), False)

        def on_result(text, ok):
            if ok:
                self._log.info("AI test_connection OK")
                QMessageBox.information(
                    self,
                    "Connection Test",
                    f"Connection to {provider} ({model}) succeeded:\n\n{text}",
                )
            else:
                self._log.error("AI test_connection failed: %s", text)
                QMessageBox.critical(
                    self,
                    "Connection Test",
                    f"Connection to {provider} ({model}) failed:\n\n{text}",
                )
            self.statusBar().showMessage("", 0)

        worker = TestWorker(self._ai_service)
        worker.result_ready.connect(on_result)
        worker.start()

        if not hasattr(self, "_test_workers"):
            self._test_workers = []
        self._test_workers.append(worker)
        self._test_workers = [w for w in self._test_workers if not w.isFinished()]
    def _create_ai_chat_placeholder(self) -> QWidget:
        """Create the AI chat panel (styled like Claude / DeepSeek)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Toolbar: status + actions
        toolbar = QHBoxLayout()
        title = QLabel("AI Assistant")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._ai_status_label = QLabel("")
        self._ai_status_label.setStyleSheet("color: #666; font-size: 12px;")
        toolbar.addWidget(self._ai_status_label)

        self._retry_button = QPushButton("🔁 Retry")
        self._retry_button.setToolTip("Retry the last AI request")
        self._retry_button.setEnabled(False)
        self._retry_button.clicked.connect(self._retry_last_ai_message)
        toolbar.addWidget(self._retry_button)

        self._save_chat_md_button = QPushButton("💾 Save .md")
        self._save_chat_md_button.setToolTip("Save the chat as a Markdown file")
        self._save_chat_md_button.setEnabled(False)
        self._save_chat_md_button.clicked.connect(self._save_chat_markdown)
        toolbar.addWidget(self._save_chat_md_button)

        layout.addLayout(toolbar)

        # Chat history: scrollable area of message bubbles
        self._ai_chat_scroll = QScrollArea()
        self._ai_chat_scroll.setWidgetResizable(True)
        self._ai_chat_content = QWidget()
        self._ai_chat_layout = QVBoxLayout(self._ai_chat_content)
        self._ai_chat_layout.setContentsMargins(4, 4, 4, 4)
        self._ai_chat_layout.setSpacing(8)
        self._ai_chat_layout.addStretch(1)
        self._ai_chat_scroll.setWidget(self._ai_chat_content)
        self._ai_chat_scroll.setStyleSheet(
            "QScrollArea { background: #ffffff; border: 1px solid #e0e0e0; "
            "border-radius: 8px; }"
        )
        layout.addWidget(self._ai_chat_scroll, 1)

        # Input area
        self._ai_chat_input = QTextEdit()
        self._ai_chat_input.setPlaceholderText(
            "Ask a question about the selected datasheet pages..."
        )
        self._ai_chat_input.setEnabled(False)
        self._ai_chat_input.setFixedHeight(70)
        self._ai_chat_input.setAcceptRichText(False)
        layout.addWidget(self._ai_chat_input)

        # Buttons
        buttons = QHBoxLayout()
        self._ai_send_button = QPushButton("➤ Send")
        self._ai_send_button.setEnabled(False)
        # NOTE: connect via a lambda, not self._send_ai_message directly.
        # QPushButton.clicked emits a `checked: bool` argument; if connected
        # directly, PySide6 passes that `False`/`True` into
        # `_send_ai_message`'s `force_message` parameter (since it is not
        # None), which then crashes on `False.strip()` and silently makes
        # the Send button do nothing.
        self._ai_send_button.clicked.connect(lambda: self._send_ai_message())
        buttons.addWidget(self._ai_send_button)

        clear_button = QPushButton("🗑 Clear")
        clear_button.setToolTip("Clear the chat history")
        clear_button.clicked.connect(self._clear_ai_chat)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        return page
    def _create_ai_summary_placeholder(self) -> QWidget:
        """Create the AI summary panel."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        hint = QLabel(
            "AI-generated summaries of the selected datasheet pages\nwill appear here."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hint)

        self._ai_summary_display = QTextEdit()
        self._ai_summary_display.setReadOnly(True)
        layout.addWidget(self._ai_summary_display, 1)

        self._ai_summary_button = QPushButton("⚡ Generate Summary")
        self._ai_summary_button.setEnabled(False)
        self._ai_summary_button.clicked.connect(self._generate_ai_summary)
        layout.addWidget(self._ai_summary_button)

        self._save_summary_button = QPushButton("💾 Save Summary to Library…")
        self._save_summary_button.setEnabled(False)
        self._save_summary_button.setToolTip(
            "Write the generated summary into the library's summaries folder"
        )
        self._save_summary_button.clicked.connect(self._save_summary_to_library)
        layout.addWidget(self._save_summary_button)

        return page

    def _create_ai_report_placeholder(self) -> QWidget:
        """Create the AI report panel."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        hint = QLabel(
            "AI-generated reports (structure, findings, extraction)\nwill appear here."
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hint)

        self._ai_report_display = QTextEdit()
        self._ai_report_display.setReadOnly(True)
        layout.addWidget(self._ai_report_display, 1)

        self._ai_report_button = QPushButton("📄 Generate Report")
        self._ai_report_button.setEnabled(False)
        self._ai_report_button.clicked.connect(self._generate_ai_report)
        layout.addWidget(self._ai_report_button)

        return page

    def _configure_ai_service(self) -> None:
        """Push the current settings tab values into the AI service."""
        self._ai_service.configure(
            provider=self._ai_provider_combo.currentText(),
            api_key=self._ai_api_key_input.text().strip(),
            base_url=self._ai_base_url_input.text(),
            model=self._ai_model_combo.currentText(),
            protocol=self._ai_protocol_combo.currentText(),
        )

    def _build_ai_context(self) -> str:
        """Build AI context from the document outline and selected page text."""
        parts = []

        # The document outline helps the model map sections to page numbers.
        if self._pdf_info is not None and self._pdf_info.bookmarks:
            outline_lines = []
            for b in self._pdf_info.bookmarks:
                outline_lines.append(
                    f"{'  ' * (b.level - 1)}- {b.title} (page {b.page})"
                )
            parts.append("Document outline (bookmarks):\n" + "\n".join(outline_lines))

        # Text of the selected pages.
        if self._pdf_info is not None and self._selected_pages:
            for page_num in sorted(self._selected_pages):
                try:
                    text = self._reader.get_page_text(self._pdf_info.path, page_num)
                except Exception as exc:
                    self._log.warning(
                        "AI context: page %d text extraction failed: %s", page_num, exc
                    )
                    continue
                if text.strip():
                    parts.append(f"--- Page {page_num} ---\n{text.strip()}")

        joined = "\n\n".join(parts)
        return joined[:16000]
    def _open_debug_log(self) -> None:
        """Open a dialog showing the buffered debug log with a copy button."""
        from PySide6.QtWidgets import QDialogButtonBox, QPlainTextEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("Debug Log — Datasheet Studio")
        dialog.resize(760, 500)

        layout = QVBoxLayout(dialog)
        label = QLabel(
            "Copy everything below and send it for support. Logs are kept in "
            "memory only (max 2000 entries) and are never written to disk."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(get_log_text())
        layout.addWidget(text, 1)

        button_box = QDialogButtonBox()
        refresh_button = QPushButton("🔄 Refresh")
        refresh_button.clicked.connect(lambda: text.setPlainText(get_log_text()))
        copy_button = QPushButton("📋 Copy All")
        copy_button.clicked.connect(lambda: self._copy_text(text.toPlainText()))
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_box.addButton(refresh_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(close_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)

        dialog.exec()

    def _copy_text(self, text: str) -> None:
        """Copy text to the system clipboard."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.statusBar().showMessage("Log copied to clipboard", 2000)

    def _tool_context(self) -> ToolContext:
        """Create a current state snapshot for a registered engineering tool."""
        source_hash = ""
        if self._pdf_info is not None:
            try:
                from datasheet_studio.services.knowledge_hash import sha256_file

                source_hash = sha256_file(self._pdf_info.path)
            except OSError:
                source_hash = ""
        controller_profile = None
        if source_hash:
            vault_path = str(self._settings.value("knowledgeBasePath", "") or "")
            if vault_path:
                try:
                    from datasheet_studio.infrastructure.storage.knowledge_vault import (
                        KnowledgeVault,
                    )

                    matches = KnowledgeVault(vault_path).controller_profiles_for(source_hash)
                    controller_profile = matches[0] if matches else None
                except Exception:
                    controller_profile = None
        return ToolContext(
            parent=self,
            pdf_reader=self._reader,
            pdf_info=self._pdf_info,
            selected_pages=tuple(sorted(self._selected_pages)),
            ai_service=self._ai_service,
            source_hash=source_hash,
            controller_profile=controller_profile,
        )

    def _run_registered_tool(self, tool_id: str) -> None:
        """Run one tool without allowing a failure to close the application."""
        try:
            self._tool_registry.get(tool_id).run(self._tool_context())
        except Exception as exc:  # noqa: BLE001 - isolate optional tools
            self._log.exception("Registered tool failed: %s", tool_id)
            QMessageBox.critical(
                self,
                "Tool Error",
                f"The tool could not be opened:\n{exc}",
            )

    def _create_menu_bar(self) -> None:
        """Create the main menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")
        open_action = file_menu.addAction("&Open Datasheet...")
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Open a PDF datasheet")
        open_action.triggered.connect(self._open_datasheet)

        # Recent files submenu
        file_menu.addSeparator()
        self._recent_files_menu = file_menu.addMenu("Recent Files")
        self._recent_files_menu.setEnabled(False)
        self._update_recent_files_menu()

        file_menu.addSeparator()

        # Save/Load selection
        save_sel_action = file_menu.addAction("&Save Selection...")
        save_sel_action.setShortcut("Ctrl+S")
        save_sel_action.setStatusTip("Save selected pages to a new PDF file")
        save_sel_action.triggered.connect(self._save_selection)
        
        save_notes_action = file_menu.addAction("Save Notes to PDF...")
        save_notes_action.triggered.connect(self._save_pdf_with_notes)

        load_sel_action = file_menu.addAction("&Load Selection...")
        load_sel_action.setShortcut("Ctrl+L")
        load_sel_action.setStatusTip("Load selected pages from a file")
        load_sel_action.triggered.connect(self._load_selection)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close)

        # View menu
        view_menu = menu_bar.addMenu("&View")
        reset_action = view_menu.addAction("&Reset Layout")
        reset_action.setEnabled(False)
        reset_action.setStatusTip("Reset the workspace layout (not yet implemented)")

        search_strip_action = view_menu.addAction("جست‌وجوی دیتاشیت‌ها")
        search_strip_action.setShortcut("Ctrl+K")
        search_strip_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        search_strip_action.setStatusTip("باز کردن نوار جست‌وجوی پایین")
        search_strip_action.triggered.connect(self._search_strip.toggle_and_focus)
        self._search_strip_action = search_strip_action

        # Tools menu
        self._tools_menu = menu_bar.addMenu("&Tools")
        tools_menu = self._tools_menu
        # Keep Python references: PySide may otherwise delete submenu wrappers
        # after this method returns even though their QAction remains visible.
        self._tool_category_menus: dict[str, QMenu] = {}
        for tool in self._tool_registry.list_tools():
            category_menu = self._tool_category_menus.get(tool.category)
            if category_menu is None:
                category_menu = tools_menu.addMenu(tool.category)
                self._tool_category_menus[tool.category] = category_menu
            action = category_menu.addAction(tool.name)
            action.setStatusTip(tool.description)
            action.triggered.connect(
                lambda _checked=False, tool_id=tool.id: self._run_registered_tool(tool_id)
            )

        # Library menu
        library_menu = menu_bar.addMenu("&Library")
        open_library_action = library_menu.addAction("&Open Library Folder...")
        open_library_action.setStatusTip("Open an existing datasheet library folder")
        open_library_action.triggered.connect(self._open_library_folder_dialog)

        create_library_action = library_menu.addAction("Create &New Library...")
        create_library_action.setStatusTip("Create a new empty library folder")
        create_library_action.triggered.connect(self._create_library_dialog)

        upgrade_library_action = library_menu.addAction(
            "Upgrade Library to v2 (Knowledge Base)..."
        )
        upgrade_library_action.setStatusTip(
            "Safely migrate this library into a v2 knowledge-base vault "
            "(preview, report, accept or roll back; v1 is never modified)"
        )
        upgrade_library_action.triggered.connect(self._open_library_upgrade_dialog)

        library_menu.addSeparator()
        self._add_to_library_action = library_menu.addAction(
            "Add Current PDF to &Library..."
        )
        self._add_to_library_action.setShortcut("Ctrl+D")
        self._add_to_library_action.setStatusTip(
            "Copy the currently open datasheet into the library"
        )
        self._add_to_library_action.setEnabled(False)
        self._add_to_library_action.triggered.connect(self._add_current_pdf_to_library)

        search_online_action = library_menu.addAction("Search Datasheets &Online...")
        online_sources_settings = library_menu.addAction("&Online Sources Settings...")
        online_sources_settings.setStatusTip(
            "Enable and configure permitted online search sources (DigiKey)"
        )
        online_sources_settings.triggered.connect(self._open_online_sources_settings)
        search_online_action.setStatusTip(
            "Open a small web browser to find and temporarily download datasheets"
        )
        search_online_action.triggered.connect(self._open_datasheet_browser)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = help_menu.addAction("&About Datasheet Studio")
        about_action.setStatusTip("Show information about Datasheet Studio")
        about_action.triggered.connect(self._show_about_dialog)

        help_menu.addSeparator()
        debug_log_action = help_menu.addAction("Debug Log...")
        debug_log_action.setStatusTip("Open the temporary debug log (copy for support)")
        debug_log_action.triggered.connect(self._open_debug_log)

    def _show_about_dialog(self) -> None:
        """Show a small About dialog."""
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>Version {APP_VERSION}<br><br>"
            "A specialized desktop application for reading, organizing, "
            "annotating, and analyzing electronic-component datasheets.<br><br>"
            "<i>Current stage: Foundation + Application Shell + PDF Viewer.</i>",
        )

    # ------------------------------------------------------------------
    # Library actions
    # ------------------------------------------------------------------

    def _open_library_upgrade_dialog(self) -> None:
        """Open the v1 -> v2 knowledge-base upgrade for the active library."""
        store = self._library_service.store
        if store is None:
            QMessageBox.information(
                self,
                "Upgrade Library to v2",
                "Open a v1 library folder first (Library -> Open Library Folder...).",
            )
            return
        from datasheet_studio.ui.dialogs.library_upgrade_dialog import (
            LibraryUpgradeDialog,
        )

        dialog = LibraryUpgradeDialog(str(store.root), self)
        dialog.exec()

    def _open_library_folder_dialog(self) -> None:
        """Ask for a folder and open it as a library if it is one."""
        from PySide6.QtWidgets import QFileDialog

        start = "~"
        if self._library_service.store is not None:
            start = str(self._library_service.store.root)
        folder = QFileDialog.getExistingDirectory(self, "Open Library Folder", start)
        if not folder:
            return
        self._open_library_path(folder)

    def _open_library_path(self, folder: str) -> bool:
        """Open ``folder`` as a library; returns success."""
        from datasheet_studio.infrastructure.storage.library_store import (
            InvalidLibraryError,
            LibraryError,
        )

        try:
            self._library_service.open_library(folder)
        except (InvalidLibraryError, LibraryError) as exc:
            QMessageBox.warning(
                self,
                "Not a Library",
                f"{folder}\n\nis not a valid Datasheet Studio library.\n\n({exc})",
            )
            return False
        self._settings.setValue("libraryPath", folder)
        self._library_panel.refresh()
        self.statusBar().showMessage(f"Library opened: {folder}", 4000)
        self._log.info("Opened library: %s", folder)
        return True

    def _create_library_dialog(self) -> None:
        """Ask for a new empty folder and create a library in it."""
        from PySide6.QtWidgets import QFileDialog

        start = "~"
        if self._library_service.store is not None:
            start = str(self._library_service.store.root)
        folder = QFileDialog.getExistingDirectory(
            self, "Create Library (choose an empty folder)", start
        )
        if not folder:
            return
        from datasheet_studio.infrastructure.storage.library_store import LibraryError

        try:
            self._library_service.create_library(folder)
        except LibraryError as exc:
            QMessageBox.warning(self, "Create Library Failed", str(exc))
            return
        self._settings.setValue("libraryPath", folder)
        self._library_panel.refresh()

    def _add_current_pdf_to_library(self) -> None:
        """Copy the currently open PDF into the library (with a folder picker)."""
        if self._pdf_info is None:
            QMessageBox.information(self, "Add to Library", "Open a datasheet first.")
            return

        # Make sure a library exists.
        if self._library_service.store is None:
            answer = QMessageBox.question(
                self,
                "No Library",
                "No library is open yet.\n\nCreate a new library folder now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._create_library_dialog()
            if self._library_service.store is None:
                return

        meta = self._library_service.detect_metadata(self._pdf_info.path)
        from datasheet_studio.models.library_item import LibraryItemKind

        existing = self._library_service.store.manufacturer_folders(
            LibraryItemKind.DATASHEET
        )
        dialog = AddToLibraryDialog(
            self,
            source_name=self._pdf_info.path,
            detected_manufacturer=str(meta.get("manufacturer") or ""),
            existing_folders=existing,
        )
        if dialog.exec() != AddToLibraryDialog.DialogCode.Accepted:
            return

        try:
            item = self._library_service.add_pdf(
                self._pdf_info.path,
                manufacturer_folder=dialog.selected_folder(),
                kind=dialog.selected_kind(),
                tags=dialog.selected_tags(),
            )
        except Exception as exc:  # noqa: BLE001 - surface to the user
            QMessageBox.warning(self, "Add to Library Failed", str(exc))
            self._log.warning("Add to library failed: %s", exc)
            return

        self._library_panel.refresh()
        self.statusBar().showMessage(
            f"Added to library → {item.manufacturer_folder}/{item.title}", 4000
        )
        self._log.info("Added to library: %s", item.relative_path)

        self.statusBar().showMessage(f"Library created: {folder}", 4000)
        self._log.info("Created library: %s", folder)


    # ------------------------------------------------------------------
    # PDF open / navigation / rendering
    # ------------------------------------------------------------------

    def _open_datasheet(self) -> None:
        """Ask the user for a PDF and load its metadata, bookmarks, and page 1."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Datasheet",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if not path:
            return

        try:
            info = self._reader.open(path)
        except PdfOpenError as exc:
            QMessageBox.critical(self, "Open Error", str(exc))
            return

        self._pdf_info = info
        self._current_page = 1
        self._zoom = 1.0
        self._notes_by_page.clear()  # Clear notes from previous document
        self._clear_selected_pages()  # Clear selection from previous document

        self._populate_bookmarks(info)
        self._activate_document_ui()

        self._add_to_recent_files(info.path)
        self._update_recent_files_menu()

        self.statusBar().showMessage(f"Opened: {info.path}")
        self._log.info("Opened document: %s", info.path)

        self._render_page(self._current_page)

    def _activate_document_ui(self) -> None:
        """Enable all document-dependent controls after a PDF is loaded."""
        self._zoom_out_button.setEnabled(True)
        self._zoom_in_button.setEnabled(True)
        self._zoom_fit_button.setEnabled(True)
        self._note_button.setEnabled(True)
        self._manage_notes_button.setEnabled(True)
        self._page_range_input.setEnabled(True)
        self._add_range_button.setEnabled(True)
        self._add_to_library_action.setEnabled(True)
        self._library_panel.set_add_enabled(True)
        self._update_navigation_buttons()

    def _populate_bookmarks(self, info: PdfDocumentInfo) -> None:
        """Populate the bookmarks tree from the flattened outline."""
        self._bookmarks_tree.clear()

        if not info.bookmarks:
            item = QTreeWidgetItem(["No bookmarks in this document"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._bookmarks_tree.addTopLevelItem(item)
            return

        # Keep a flat list of items so we can attach by nesting level.
        items: list[QTreeWidgetItem | None] = [None]

        for bookmark in info.bookmarks:
            item = QTreeWidgetItem([bookmark.title])
            item.setData(0, Qt.ItemDataRole.UserRole, bookmark.page)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, bookmark.level)  # Store level

            parent = items[bookmark.level - 1] if bookmark.level - 1 < len(items) else None
            if parent is None:
                self._bookmarks_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

            # Ensure the items list is long enough for children.
            while len(items) <= bookmark.level:
                items.append(None)
            items[bookmark.level] = item

        self._bookmarks_tree.expandAll()

    def _on_bookmark_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Navigate to the page referenced by a bookmark (single click)."""
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page is None:
            return

        try:
            page_number = int(page)
        except (TypeError, ValueError):
            return

        self._current_page = page_number
        self._render_page(page_number)

    def _on_bookmark_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Add bookmark page to selected pages on double click."""
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page is None:
            return

        try:
            page_number = int(page)
        except (TypeError, ValueError):
            return

        # Navigate to the page
        self._current_page = page_number
        self._render_page(page_number)

        # Add to selected pages
        self._add_page_to_selected(page_number)

    def _on_bookmark_context_menu(self, position) -> None:
        """Show context menu for bookmarks."""
        item = self._bookmarks_tree.itemAt(position)
        if item is None:
            return

        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page is None:
            return

        try:
            page_number = int(page)
        except (TypeError, ValueError):
            return

        menu = QMenu(self)

        # Navigate action
        navigate_action = menu.addAction("Navigate to this page")
        navigate_action.triggered.connect(lambda: self._navigate_to_page(page_number))

        # Add to selected pages
        add_action = menu.addAction("Add to Selected Pages")
        add_action.triggered.connect(lambda: self._add_page_to_selected(page_number))

        # Add section to selected pages (from this bookmark to next)
        add_section_action = menu.addAction("Add Section to Selected Pages")
        add_section_action.triggered.connect(lambda: self._add_bookmark_section_to_selected(item))

        menu.addSeparator()

        # Expand/Collapse if has children
        if item.childCount() > 0:
            expand_action = menu.addAction("Expand all children")
            expand_action.triggered.connect(lambda: self._expand_tree_item(item, True))

            collapse_action = menu.addAction("Collapse all children")
            collapse_action.triggered.connect(lambda: self._expand_tree_item(item, False))

            menu.addSeparator()

        # Copy title
        copy_action = menu.addAction("Copy bookmark title")
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(item.text(0)))

        menu.exec(self._bookmarks_tree.viewport().mapToGlobal(position))

    def _get_bookmark_page_range(self, item: QTreeWidgetItem) -> tuple[int, int]:
        """Calculate the page range for a bookmark (from this bookmark to the next one at same or higher level)."""
        if self._pdf_info is None:
            return (1, 1)

        current_page = item.data(0, Qt.ItemDataRole.UserRole)

        try:
            start_page = int(current_page)
        except (TypeError, ValueError):
            return (1, 1)

        # Get the level of the current item (0-based: 0 = top level)
        current_level = self._get_item_level(item)

        # Find the next bookmark at same or higher level
        end_page = self._pdf_info.page_count  # Default to last page

        # Get all bookmark items in order
        all_items_ordered = self._get_all_bookmark_items_ordered()

        found_current = False
        for bookmark_item in all_items_ordered:
            if bookmark_item is item:
                found_current = True
                continue
            if found_current:
                bookmark_level = self._get_item_level(bookmark_item)
                # Found the next bookmark at same or higher level (lower number = higher level)
                if bookmark_level <= current_level:
                    bookmark_page = bookmark_item.data(0, Qt.ItemDataRole.UserRole)
                    try:
                        end_page = int(bookmark_page) - 1
                    except (TypeError, ValueError):
                        pass
                    break

        return (start_page, max(start_page, end_page))

    def _get_all_bookmark_items_ordered(self) -> list[QTreeWidgetItem]:
        """Get all bookmark items in document order (depth-first traversal)."""
        result = []

        def traverse(item: QTreeWidgetItem):
            result.append(item)
            for i in range(item.childCount()):
                traverse(item.child(i))

        for i in range(self._bookmarks_tree.topLevelItemCount()):
            traverse(self._bookmarks_tree.topLevelItem(i))

        return result

    def _get_item_level(self, item: QTreeWidgetItem) -> int:
        """Get the visual nesting level of a tree item."""
        level = 0
        parent = item.parent()
        while parent is not None:
            level += 1
            parent = parent.parent()
        return level

    def _add_bookmark_section_to_selected(self, item: QTreeWidgetItem) -> None:
        """Add all pages from this bookmark section to selected pages."""
        if self._pdf_info is None:
            return

        start_page, end_page = self._get_bookmark_page_range(item)

        added_count = 0
        for page_num in range(start_page, end_page + 1):
            if page_num not in self._selected_pages:
                self._add_page_to_selected(page_num)
                added_count += 1

        self.statusBar().showMessage(
            f"Added {added_count} pages from bookmark section (pages {start_page}-{end_page})",
            3000,
        )

    def _navigate_to_page(self, page_number: int) -> None:
        """Navigate to a specific page."""
        self._current_page = page_number
        self._render_page(page_number)

    def _expand_tree_item(self, item: QTreeWidgetItem, expand: bool) -> None:
        """Expand or collapse a tree item and all its children."""
        item.setExpanded(expand)
        for i in range(item.childCount()):
            self._expand_tree_item(item.child(i), expand)

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.statusBar().showMessage(f"Copied: {text}", 2000)

    def _add_page_to_selected(self, page_number: int) -> None:
        """Add a page to the selected pages collection."""
        if self._pdf_info is None:
            return

        if page_number in self._selected_pages:
            self.statusBar().showMessage(
                f"Page {page_number} is already selected", 2000
            )
            return

        selected = SelectedPage(
            page_number=page_number,
            document_path=self._pdf_info.path,
        )
        self._selected_pages[page_number] = selected
        
        # Add to list widget
        item = QListWidgetItem(f"Page {page_number}")
        item.setData(Qt.ItemDataRole.UserRole, page_number)
        self._selected_pages_list.addItem(item)
        
        self._update_selected_pages_count()
        self.statusBar().showMessage(f"Added page {page_number} to selected pages", 2000)
        self._log.info("Added page %d to selected pages", page_number)

    def _on_selected_page_clicked(self, item: QListWidgetItem) -> None:
        """Navigate to the clicked selected page."""
        page_number = item.data(Qt.ItemDataRole.UserRole)
        if page_number is not None:
            self._navigate_to_page(int(page_number))

    def _on_selected_page_double_clicked(self, item: QListWidgetItem) -> None:
        """Remove the double-clicked page from selected pages."""
        page_number = item.data(Qt.ItemDataRole.UserRole)
        if page_number is not None:
            self._remove_selected_page(int(page_number))

    def _remove_selected_page(self, page_number: int) -> None:
        """Remove a page from the selected pages collection."""
        if page_number not in self._selected_pages:
            return

        del self._selected_pages[page_number]
        
        # Remove from list widget
        for i in range(self._selected_pages_list.count()):
            item = self._selected_pages_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == page_number:
                self._selected_pages_list.takeItem(i)
                break
        
        self._update_selected_pages_count()
        self.statusBar().showMessage(f"Removed page {page_number} from selected pages", 2000)

    def _clear_selected_pages(self) -> None:
        """Clear all selected pages."""
        self._selected_pages.clear()
        self._selected_pages_list.clear()
        self._update_selected_pages_count()
        self.statusBar().showMessage("Cleared all selected pages", 2000)

    def _update_selected_pages_count(self) -> None:
        """Update the selected pages count label and clear button."""
        count = len(self._selected_pages)
        self._selected_count_label.setText(f"{count} page{'s' if count != 1 else ''} selected")
        self._clear_selected_button.setEnabled(count > 0)
        self._save_selection_button.setEnabled(count > 0)
        self._compress_selection_button.setEnabled(count > 0)
        self._compression_level_combo.setEnabled(count > 0)

    def _render_page(self, page_number: int) -> None:
        """Render the given 1-based page into the viewer label."""
        if self._pdf_info is None:
            return

        try:
            png = self._reader.render_page_png(
                self._pdf_info.path, page_number, zoom=self._zoom
            )
        except PdfOpenError as exc:
            self._viewer_label.setText(f"Could not render page:\n{exc}")
            return

        pixmap = QPixmap()
        pixmap.loadFromData(png, "PNG")

        # Resize the label to the rendered page size so zoomed pages become
        # scrollable. Previously setWidgetResizable(True) kept the label at
        # the viewport size, clipping the page and leaving no scrollbars, so
        # right-click-drag panning (and even plain wheel scrolling) had no
        # overflow to scroll.
        self._viewer_label.setPixmap(pixmap)
        self._viewer_label.setMinimumSize(pixmap.size())
        self._viewer_label.resize(pixmap.size())
        self._viewer_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._page_label.setText(
            f"Page {page_number} of {self._pdf_info.page_count}"
        )

        # Update navigation button states
        self._update_navigation_buttons()

        # Update scroll area boundary info
        # Always allow page navigation at boundaries
        self._scroll_area.set_at_boundaries(at_top=True, at_bottom=True)

        # Update note overlay size and show notes for this page
        self._note_overlay.setGeometry(0, 0, pixmap.width(), pixmap.height())
        self._note_overlay.set_notes(self._notes_by_page.get(page_number, []))
    def _on_empty_area_double_clicked(self) -> None:
        """Handle double-click on empty area of the overlay to add current page to selected."""
        if self._pdf_info is not None:
            self._add_page_to_selected(self._current_page)


    def _add_note_to_current_page(self) -> None:
        """Add a note to the current page."""
        if self._pdf_info is None:
            return

        # Create a new note at center of page
        note = PdfNote(
            page_number=self._current_page,
            text="New Note",
            x=0.5,
            y=0.5,
        )

        # Show editor dialog
        dialog = NoteEditorDialog(note, self)
        if dialog.exec():
            note = dialog.get_note()
            
            # Add to notes storage
            if self._current_page not in self._notes_by_page:
                self._notes_by_page[self._current_page] = []
            self._notes_by_page[self._current_page].append(note)
            
            # Update overlay
            self._note_overlay.set_notes(self._notes_by_page.get(self._current_page, []))
            
            self.statusBar().showMessage(
                f"Note added to page {self._current_page}", 2000
            )

    def _edit_note(self, note_id: str) -> None:
        """Edit an existing note."""
        # Find the note
        for page_notes in self._notes_by_page.values():
            for note in page_notes:
                if note.note_id == note_id:
                    dialog = NoteEditorDialog(note, self)
                    if dialog.exec():
                        updated_note = dialog.get_note()
                        # Update in storage
                        self._note_overlay.set_notes(
                            self._notes_by_page.get(self._current_page, [])
                        )
                        self.statusBar().showMessage("Note updated", 2000)
                    return

    def _manage_notes(self) -> None:
        """Show a dialog to manage all notes."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Notes")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # List of all notes
        notes_list = QListWidget()
        all_notes = []
        for page_num, page_notes in sorted(self._notes_by_page.items()):
            for note in page_notes:
                all_notes.append((page_num, note))
                preview = note.text[:50] + "..." if len(note.text) > 50 else note.text
                notes_list.addItem(f"Page {page_num}: {preview}")

        layout.addWidget(QLabel("All Notes:"))
        layout.addWidget(notes_list)

        # Buttons
        button_layout = QHBoxLayout()

        edit_button = QPushButton("✏️ Edit")
        edit_button.clicked.connect(lambda: self._edit_note_from_list(notes_list, all_notes))
        button_layout.addWidget(edit_button)

        delete_button = QPushButton("🗑️ Delete")
        delete_button.clicked.connect(lambda: self._delete_note_from_list(notes_list, all_notes, dialog))
        button_layout.addWidget(delete_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        dialog.exec()

    def _generate_ai_summary(self) -> None:
        """Generate a summary of the selected pages using AI."""
        if not self._selected_pages:
            QMessageBox.warning(self, "No Selection", "Please select pages to summarize first.")
            return

        api_key = self._ai_api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please configure your AI provider and API key first.")
            return

        self._configure_ai_service()
        content = self._build_ai_context()
        if not content:
            content = f"Summary requested for {len(self._selected_pages)} selected pages: {list(self._selected_pages.keys())}."
        self._log.info(
            "AI summary: pages=%d context_chars=%d",
            len(self._selected_pages),
            len(content),
        )

        self.statusBar().showMessage("Generating summary...", 0)

        from PySide6.QtCore import QThread, Signal

        class SummaryWorker(QThread):
            result_ready = Signal(str)

            def __init__(self, ai_service, content):
                super().__init__()
                self.ai_service = ai_service
                self.content = content

            def run(self):
                try:
                    response = self.ai_service.generate_summary(self.content)
                    self.result_ready.emit(response)
                except Exception as e:
                    self.result_ready.emit(f"Error: {e}")

        def on_result(result):
            self._ai_summary_display.setPlainText(result)
            self._save_summary_button.setEnabled(True)
            self.statusBar().showMessage("Summary generated", 2000)
            self._log.info("AI summary response received (%d chars)", len(result))

        worker = SummaryWorker(self._ai_service, content)
        worker.result_ready.connect(on_result)
        worker.start()

        if not hasattr(self, '_summary_workers'):
            self._summary_workers = []
        self._summary_workers.append(worker)
        self._summary_workers = [w for w in self._summary_workers if not w.isFinished()]
    def _generate_ai_report(self) -> None:
        """Generate a detailed report of the selected pages using AI."""
        if not self._selected_pages:
            QMessageBox.warning(self, "No Selection", "Please select pages to analyze first.")
            return

        api_key = self._ai_api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please configure your AI provider and API key first.")
            return

        self._configure_ai_service()
        content = self._build_ai_context()
        if not content:
            content = f"Report requested for {len(self._selected_pages)} selected pages: {list(self._selected_pages.keys())}."
        self._log.info(
            "AI report: pages=%d context_chars=%d",
            len(self._selected_pages),
            len(content),
        )

        self.statusBar().showMessage("Generating report...", 0)

        from PySide6.QtCore import QThread, Signal

        class ReportWorker(QThread):
            result_ready = Signal(str)

            def __init__(self, ai_service, content):
                super().__init__()
                self.ai_service = ai_service
                self.content = content

            def run(self):
                try:
                    response = self.ai_service.generate_report(self.content)
                    self.result_ready.emit(response)
                except Exception as e:
                    self.result_ready.emit(f"Error: {e}")

        def on_result(result):
            self._ai_report_display.setPlainText(result)
            self.statusBar().showMessage("Report generated", 2000)
            self._log.info("AI report response received (%d chars)", len(result))

        worker = ReportWorker(self._ai_service, content)
        worker.result_ready.connect(on_result)
        worker.start()

        if not hasattr(self, "_report_workers"):
            self._report_workers = []
        self._report_workers.append(worker)
        self._report_workers = [w for w in self._report_workers if not w.isFinished()]
    def _edit_note_from_list(self, notes_list: QListWidget, all_notes: list) -> None:
        """Edit selected note from manage dialog."""
        current_row = notes_list.currentRow()
        if current_row >= 0 and current_row < len(all_notes):
            page_num, note = all_notes[current_row]
            dialog = NoteEditorDialog(note, self)
            if dialog.exec():
                dialog.get_note()
                # Refresh the list
                notes_list.clear()
                for page_num, page_notes in sorted(self._notes_by_page.items()):
                    for note in page_notes:
                        preview = note.text[:50] + "..." if len(note.text) > 50 else note.text
                        notes_list.addItem(f"Page {page_num}: {preview}")
                # Update overlay if on same page
                if self._current_page in self._notes_by_page:
                    self._note_overlay.set_notes(self._notes_by_page[self._current_page])

    def _delete_note_from_list(self, notes_list: QListWidget, all_notes: list, dialog: QDialog) -> None:
        """Delete selected note from manage dialog."""
        current_row = notes_list.currentRow()
        if current_row >= 0 and current_row < len(all_notes):
            page_num, note = all_notes[current_row]
            # Remove from storage
            if page_num in self._notes_by_page:
                self._notes_by_page[page_num] = [
                    n for n in self._notes_by_page[page_num] if n.note_id != note.note_id
                ]
                if not self._notes_by_page[page_num]:
                    del self._notes_by_page[page_num]
            
            # Update overlay if on same page
            if self._current_page == page_num:
                self._note_overlay.set_notes(self._notes_by_page.get(self._current_page, []))
            
            # Refresh the list
            notes_list.clear()
            for page_num, page_notes in sorted(self._notes_by_page.items()):
                for note in page_notes:
                    preview = note.text[:50] + "..." if len(note.text) > 50 else note.text
                    notes_list.addItem(f"Page {page_num}: {preview}")

    def _on_note_selected(self, note_id: str) -> None:
        """Handle note selection in overlay."""
        if note_id:
            self.statusBar().showMessage(f"Note selected", 1000)


    def _update_navigation_buttons(self) -> None:
        """Update the enabled state of navigation buttons."""
        if self._pdf_info is None:
            self._prev_page_button.setEnabled(False)
            self._next_page_button.setEnabled(False)
            return

        self._prev_page_button.setEnabled(self._current_page > 1)
        self._next_page_button.setEnabled(self._current_page < self._pdf_info.page_count)

    def _build_default_selection_name(self) -> str:
        """Build a default filename for the save-selection dialog.

        A pre-filled name prevents the native save dialog from being
        submitted with an empty filename, which previously made the slot
        return silently (no file, no message).
        """
        if self._pdf_info:
            stem = self._pdf_info.title or os.path.basename(self._pdf_info.path)
            stem = os.path.splitext(stem)[0]
            # Sanitize illegal filename characters.
            for ch in '\\/:*?"<>|':
                stem = stem.replace(ch, "_")
            stem = stem.strip()
            # Keep very long PDF titles manageable in the dialog.
            if len(stem) > 60:
                stem = stem[:60].rstrip(" -_._")
            if not stem:
                stem = "selected_pages"
        else:
            stem = "selected_pages"

        page_numbers = sorted(self._selected_pages.keys())
        suffix = f"_{page_numbers[0]}-{page_numbers[-1]}" if page_numbers else ""
        return f"{stem}{suffix}.pdf"

    def _get_save_default_path(self) -> str:
        """Default directory + filename for the save/compress dialogs.

        Opens in the folder of the currently open datasheet so the output file
        lands where the user is already looking (previously the dialog opened
        in the OS "last used" folder, e.g. Documents, which made the saved file
        hard to find).
        """
        name = self._build_default_selection_name()
        if self._pdf_info:
            folder = os.path.dirname(self._pdf_info.path)
            if folder:
                return os.path.join(folder, name)
        return name

    def _ask_save_path(self, caption: str) -> tuple[str | None, str]:
        """Show a save-file dialog and return ``(path, status)``.

        ``status`` is ``"ok"`` (a non-empty path was chosen), ``"canceled"``
        (the user closed the dialog) or ``"empty"`` (the dialog was accepted
        with no filename). Using a QFileDialog instance lets us distinguish
        cancel from an empty filename, so the save flow never fails silently.
        """
        dialog = QFileDialog(self, caption, self._get_save_default_path())
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setNameFilter("PDF Files (*.pdf);;All Files (*)")
        dialog.setDefaultSuffix("pdf")
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return None, "canceled"
        files = dialog.selectedFiles()
        if not files or not files[0].strip():
            return None, "empty"
        return files[0].strip(), "ok"

    def _show_save_success(self, message: str, path: str) -> None:
        """Show a success box with a button that reveals the saved file."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Success")
        box.setText(message)
        open_button = box.addButton(
            "📂 Open Folder", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_button:
            self._reveal_in_explorer(path)

    @staticmethod
    def _reveal_in_explorer(path: str) -> None:
        """Open the folder containing ``path`` in Windows Explorer."""
        folder = os.path.dirname(path) or "."
        try:
            os.startfile(folder)  # Windows
        except (OSError, AttributeError):
            try:
                import subprocess

                subprocess.Popen(["explorer", folder])
            except OSError:
                pass

    def _save_selection(self) -> None:
        """Save selected pages to a new PDF file."""
        if self._pdf_info is None:
            QMessageBox.warning(self, "No Document", "No PDF document is currently open.")
            return
        if not self._selected_pages:
            QMessageBox.warning(self, "No Selection", "No pages are selected to save.")
            return

        path, status = self._ask_save_path("Save Selection as PDF")
        if status == "canceled":
            self.statusBar().showMessage("Save canceled", 2000)
            return
        if status == "empty":
            QMessageBox.warning(
                self,
                "No Filename",
                "No filename was entered, so nothing was saved.\n"
                "Type a filename in the save dialog and try again.",
            )
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        self._log.info("Save selection dialog accepted: %s", path)
        try:
            page_numbers = sorted(self._selected_pages.keys())
            self._reader.save_selected_pages(
                source_path=self._pdf_info.path,
                page_numbers=page_numbers,
                dest_path=path,
                notes_by_page=self._notes_by_page,
            )

            self._log.info(
                "Saved %d selected pages to PDF: %s", len(page_numbers), path
            )
            self._show_save_success(
                f"Saved {len(page_numbers)} pages to:\n{path}", path
            )
            self.statusBar().showMessage(f"PDF saved to {path}", 5000)
        except Exception as exc:
            # Always record the failure in the in-memory debug log (Help ->
            # Debug Log...) so the reason is visible even if the message box
            # is overlooked.
            self._log.error(
                "Failed to save selected pages to PDF: %s (pages=%s)",
                path,
                sorted(self._selected_pages.keys()),
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save PDF:\n{exc}\n\nDetails are in Help → Debug Log.",
            )

    def _compress_selection(self) -> None:
        """Compress the selected pages into a new (smaller) PDF file.

        The compression level combo (Fast / Normal / Best) selects the
        PyMuPDF save options used to shrink the output.
        """
        if self._pdf_info is None:
            QMessageBox.warning(self, "No Document", "No PDF document is currently open.")
            return
        if not self._selected_pages:
            QMessageBox.warning(self, "No Selection", "No pages are selected to save.")
            return

        path, status = self._ask_save_path("Compress Selected Pages to PDF")
        if status == "canceled":
            self.statusBar().showMessage("Compress canceled", 2000)
            return
        if status == "empty":
            QMessageBox.warning(
                self,
                "No Filename",
                "No filename was entered, so nothing was saved.\n"
                "Type a filename in the save dialog and try again.",
            )
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        compression = self._compression_level_combo.currentText().lower()
        self._log.info("Compress selection dialog accepted: %s (level=%s)", path, compression)
        try:
            page_numbers = sorted(self._selected_pages.keys())
            self._reader.save_selected_pages(
                source_path=self._pdf_info.path,
                page_numbers=page_numbers,
                dest_path=path,
                notes_by_page=self._notes_by_page,
                compression=compression,
            )

            self._log.info(
                "Compressed %d selected pages to PDF: %s (level=%s)",
                len(page_numbers),
                path,
                compression,
            )
            self._show_save_success(
                f"Compressed {len(page_numbers)} pages to:\n{path}", path
            )
            self.statusBar().showMessage(f"Compressed PDF saved to {path}", 5000)
        except Exception as exc:
            self._log.error(
                "Failed to compress selected pages to PDF: %s (pages=%s)",
                path,
                sorted(self._selected_pages.keys()),
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Compress Failed",
                f"Failed to compress PDF:\n{exc}",
            )

    def _save_pdf_with_notes(self) -> None:
        """Save the current PDF with embedded notes."""
        if self._pdf_info is None:
            QMessageBox.warning(self, "No Document", "No PDF document is currently open.")
            return
        
        # Collect all notes from all pages
        all_notes = []
        for page_notes in self._notes_by_page.values():
            all_notes.extend(page_notes)
        
        if not all_notes:
            QMessageBox.information(self, "No Notes", "There are no notes to save to the PDF.")
            return
        
        # Confirm with user before modifying the original file
        reply = QMessageBox.question(
            self,
            "Save Notes to PDF",
            f"This will modify the original PDF file '{self._pdf_info.title or self._pdf_info.path}' "
            f"and add {len(all_notes)} note(s) as annotations. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._reader.add_notes_to_pdf(self._pdf_info.path, all_notes)
                self.statusBar().showMessage("Notes successfully saved to PDF!", 3000)
                self._log.info("Notes saved to PDF: %s", self._pdf_info.path)
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Save Error", 
                    f"Failed to save notes to PDF:\n{str(e)}"
                )

    def _load_selection(self) -> None:
        """Load selected pages from a compressed selection file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Selection", "",
            "Datasheet Selection (*.dssel);;All Files (*)",
        )
        if not path:
            return

        try:
            document_path, selected_pages = SelectionStorage.load(path)
        except SelectionStorageError as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            return

        from pathlib import Path as FsPath
        if not FsPath(document_path).is_file():
            QMessageBox.warning(
                self, "Document Not Found",
                f"The original document is not available:\n{document_path}",
            )
            return

        max_page = self._pdf_info.page_count if self._pdf_info else None
        self._clear_selected_pages()
        added_count = 0
        for sp in selected_pages:
            if max_page is not None and not (1 <= sp.page_number <= max_page):
                continue
            if sp.page_number not in self._selected_pages:
                self._selected_pages[sp.page_number] = sp
                item = QListWidgetItem(f"Page {sp.page_number}")
                item.setData(Qt.ItemDataRole.UserRole, sp.page_number)
                self._selected_pages_list.addItem(item)
                added_count += 1

        self._update_selected_pages_count()
        self.statusBar().showMessage(f"Loaded {added_count} pages from {path}", 3000)
        self._log.info("Loaded %d pages from selection: %s", added_count, path)

    def _add_to_recent_files(self, path: str) -> None:
        """Add a file to the recent files list."""
        recent_files = self._settings.value("recentFiles", [])
        if not isinstance(recent_files, list):
            recent_files = []
        if path in recent_files:
            recent_files.remove(path)
        recent_files.insert(0, path)
        recent_files = recent_files[:MAX_RECENT_FILES]
        self._settings.setValue("recentFiles", recent_files)

    def _update_recent_files_menu(self) -> None:
        """Update the recent files submenu."""
        self._recent_files_menu.clear()
        recent_files = self._settings.value("recentFiles", [])
        if not isinstance(recent_files, list) or not recent_files:
            self._recent_files_menu.setEnabled(False)
            no_files_action = self._recent_files_menu.addAction("No recent files")
            no_files_action.setEnabled(False)
            return

        self._recent_files_menu.setEnabled(True)
        for file_path in recent_files:
            action = self._recent_files_menu.addAction(file_path)
            action.triggered.connect(
                lambda checked, p=file_path: self._open_recent_file(p)
            )
        self._recent_files_menu.addSeparator()
        clear_action = self._recent_files_menu.addAction("Clear Recent Files")
        clear_action.triggered.connect(self._clear_recent_files)

    def _open_recent_file(self, path: str) -> None:
        """Open a file from the recent files list."""
        from pathlib import Path as FsPath
        if not FsPath(path).is_file():
            QMessageBox.warning(self, "File Not Found", f"The file is not available:\n{path}")
            return
        try:
            info = self._reader.open(path)
        except PdfOpenError as exc:
            QMessageBox.critical(self, "Open Error", str(exc))
            return

        self._pdf_info = info
        self._current_page = 1
        self._zoom = 1.0
        self._notes_by_page.clear()
        self._clear_selected_pages()
        self._populate_bookmarks(info)
        self._activate_document_ui()
        self._add_to_recent_files(info.path)
        self._update_recent_files_menu()
        self.statusBar().showMessage(f"Opened: {info.path}")
        self._log.info("Opened recent document: %s", info.path)
        self._render_page(self._current_page)

    def _clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self._settings.setValue("recentFiles", [])
        self._update_recent_files_menu()
        self.statusBar().showMessage("Recent files cleared", 2000)

    def _open_library_item(self, path: str) -> None:
        """Open a PDF stored in the library (same flow as opening a file)."""
        from pathlib import Path as FsPath

        if not FsPath(path).is_file():
            QMessageBox.warning(
                self, "File Not Found", f"The library file is not available:\n{path}"
            )
            return
        try:
            info = self._reader.open(path)
        except PdfOpenError as exc:
            QMessageBox.critical(self, "Open Error", str(exc))
            return

        self._pdf_info = info
        self._current_page = 1
        self._zoom = 1.0
        self._notes_by_page.clear()
        self._clear_selected_pages()
        self._populate_bookmarks(info)
        self._activate_document_ui()
        self._add_to_recent_files(info.path)
        self._update_recent_files_menu()
        self.statusBar().showMessage(f"Opened from library: {info.path}")
        self._log.info("Opened library document: %s", info.path)
        self._render_page(self._current_page)

    @Slot(str, int)
    def _open_search_result(self, path: str, page: int) -> None:
        """Open a local knowledge-base PDF and navigate to its matched page."""

        self._open_library_item(path)
        if self._pdf_info is None:
            return
        if os.path.normcase(os.path.abspath(self._pdf_info.path)) != os.path.normcase(
            os.path.abspath(path)
        ):
            return
        target = max(1, min(int(page), self._pdf_info.page_count))
        self._navigate_to_page(target)

    def _open_summary_file(self, path: str) -> None:
        """Show a stored Markdown summary in a dialog."""
        from pathlib import Path as FsPath

        if not FsPath(path).is_file():
            QMessageBox.warning(self, "Summary Missing", f"No summary file:\n{path}")
            return
        try:
            text = FsPath(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Summary Error", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Summary — {FsPath(path).name}")
        dialog.resize(640, 500)
        layout = QVBoxLayout(dialog)
        browser = _AutoHeightTextBrowser()
        browser.setHtml(markdown_to_html(text))
        layout.addWidget(browser)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _open_datasheet_browser(self, query: str = "") -> None:
        """Open the embedded Chromium browser (optionally with a web search)."""

        from datasheet_studio.ui.dialogs.datasheet_browser import (
            DatasheetBrowserDialog,
        )

        download_dir = None
        store = self._library_service.store
        if store is not None:
            download_dir = store.root / "_downloads"

        dialog = DatasheetBrowserDialog(
            self,
            download_dir=download_dir,
            vault_path_getter=lambda: str(
                self._settings.value("knowledgeBasePath", "") or ""
            ),
            import_service=getattr(self, "_online_import_service", None),
            initial_query=query or "",
        )
        dialog.add_download_to_library.connect(self._add_download_to_library)
        dialog.open_pdf_requested.connect(self._open_library_item)
        dialog.saved_to_vault.connect(
            lambda message: self.statusBar().showMessage(message, 6000)
        )
        dialog.exec()

    def _add_download_to_library(self, path: str) -> None:
        """Add a temporarily downloaded PDF to the library."""
        if self._library_service.store is None:
            answer = QMessageBox.question(
                self,
                "No Library",
                "No library is open. Create one before adding this file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._create_library_dialog()
            if self._library_service.store is None:
                return

        meta = self._library_service.detect_metadata(path)
        from datasheet_studio.models.library_item import LibraryItemKind

        existing = self._library_service.store.manufacturer_folders(
            LibraryItemKind.DATASHEET
        )
        dialog = AddToLibraryDialog(
            self,
            source_name=path,
            detected_manufacturer=str(meta.get("manufacturer") or ""),
            existing_folders=existing,
        )
        if dialog.exec() != AddToLibraryDialog.DialogCode.Accepted:
            return
        try:
            item = self._library_service.add_pdf(
                path,
                manufacturer_folder=dialog.selected_folder(),
                kind=dialog.selected_kind(),
                tags=dialog.selected_tags(),
            )
        except Exception as exc:  # noqa: BLE001 - surface to the user
            QMessageBox.warning(self, "Add to Library Failed", str(exc))
            return
        self._library_panel.refresh()
        self.statusBar().showMessage(
            f"Added to library → {item.manufacturer_folder}/{item.title}", 4000
        )
    def _save_summary_to_library(self) -> None:
        """Write the current AI summary into the library summaries folder."""
        text = self._ai_summary_display.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self, "Save Summary", "Generate a summary first."
            )
            return
        if self._pdf_info is None:
            QMessageBox.information(self, "Save Summary", "Open a datasheet first.")
            return

        if self._library_service.store is None:
            answer = QMessageBox.question(
                self,
                "No Library",
                "No library is open. Create one to save summaries?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._create_library_dialog()
            if self._library_service.store is None:
                return

        store = self._library_service.store
        from pathlib import Path as FsPath

        current_path = FsPath(self._pdf_info.path).resolve()
        item = None
        for candidate in store.items:
            if FsPath(store.item_path(candidate)).resolve() == current_path:
                item = candidate
                break

        if item is None:
            answer = QMessageBox.question(
                self,
                "Not in Library",
                "The currently open PDF is not in the library.\n\n"
                "Add it to the library first so the summary can be linked?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._add_current_pdf_to_library()
            if self._library_service.store is None:
                return
            store = self._library_service.store
            for candidate in store.items:
                if FsPath(store.item_path(candidate)).resolve() == current_path:
                    item = candidate
                    break
            if item is None:
                return

        try:
            summary_path = self._library_service.save_summary(item.item_id, text)
        except Exception as exc:  # noqa: BLE001 - surface to the user
            QMessageBox.warning(self, "Save Summary Failed", str(exc))
            return
        self._library_panel.refresh()
        self.statusBar().showMessage(f"Summary saved → {summary_path}", 4000)
        self._log.info("Summary saved to library: %s", summary_path)



    def _go_to_previous_page(self) -> None:
        """Navigate to the previous page."""
        if self._pdf_info is None or self._current_page <= 1:
            return
        self._current_page -= 1
        self._render_page(self._current_page)

    def _go_to_next_page(self) -> None:
        """Navigate to the next page."""
        if self._pdf_info is None:
            return
        if self._current_page >= self._pdf_info.page_count:
            return
        self._current_page += 1
        self._render_page(self._current_page)

    def _on_scroll_zoom(self, delta: float) -> None:
        """Handle zoom request from scroll area (Ctrl+wheel)."""
        if delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _on_scroll_page_navigation(self, page_delta: int) -> None:
        """Handle page navigation request from scroll area (scroll at boundaries)."""
        if page_delta < 0:
            self._go_to_previous_page()
        elif page_delta > 0:
            self._go_to_next_page()

    def _zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 5.0)
        self._render_page(self._current_page)

    def _zoom_out(self) -> None:
        self._zoom = max(self._zoom / 1.25, 0.1)
        self._render_page(self._current_page)

    def _zoom_to_fit(self) -> None:
        """Zoom to fit the current page in the viewer."""
        if self._pdf_info is None:
            return

        # Get original page dimensions from PDF (in points, 72 dpi)
        try:
            page_width, page_height = self._reader.get_page_dimensions(
                self._pdf_info.path, self._current_page
            )
        except PdfOpenError:
            return

        if page_width == 0 or page_height == 0:
            return

        # Process events to ensure layout is updated
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        # Get the available space in the scroll area
        viewport_size = self._scroll_area.viewport().size()

        # Calculate zoom to fit (with some padding)
        padding = 20  # pixels
        available_width = viewport_size.width() - padding * 2
        available_height = viewport_size.height() - padding * 2

        # Calculate zoom factors based on original page dimensions
        # PDF points are 1/72 inch, so at zoom=1.0, 1 point = 1 pixel
        zoom_x = available_width / page_width
        zoom_y = available_height / page_height

        # Use the smaller zoom to ensure the entire page fits
        new_zoom = min(zoom_x, zoom_y)

        # Clamp to valid range
        self._zoom = max(0.1, min(new_zoom, 5.0))
        self._render_page(self._current_page)

    def _add_page_range_to_selected(self) -> None:
        """Parse page range input and add pages to selected."""
        if self._pdf_info is None:
            return

        range_text = self._page_range_input.text().strip()
        if not range_text:
            QMessageBox.warning(
                self,
                "Invalid Range",
                "Please enter a page range (e.g., 14-33 or 5,10,15-20)",
            )
            return

        # Parse the range
        pages = self._parse_page_range(range_text)
        if not pages:
            QMessageBox.warning(
                self,
                "Invalid Range",
                "Could not parse page range. Use format like: 14-33 or 5,10,15-20",
            )
            return

        # Validate pages
        max_page = self._pdf_info.page_count
        valid_pages = [p for p in pages if 1 <= p <= max_page]
        if not valid_pages:
            QMessageBox.warning(
                self,
                "Invalid Pages",
                f"No valid pages in range. Document has {max_page} pages.",
            )
            return

        # Add to selected
        added_count = 0
        for page_num in valid_pages:
            if page_num not in self._selected_pages:
                self._add_page_to_selected(page_num)
                added_count += 1

        self.statusBar().showMessage(
            f"Added {added_count} pages from range '{range_text}'",
            3000,
        )

        # Clear the input
        self._page_range_input.clear()

    def _parse_page_range(self, range_text: str) -> list[int]:
        """Parse page range string like '14-33' or '5,10,15-20' into list of page numbers."""
        pages = []
        
        # Split by comma
        parts = range_text.split(",")
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Check if it's a range (e.g., "14-33")
            if "-" in part:
                range_parts = part.split("-")
                if len(range_parts) == 2:
                    try:
                        start = int(range_parts[0].strip())
                        end = int(range_parts[1].strip())
                        # Add all pages in range
                        pages.extend(range(start, end + 1))
                    except ValueError:
                        continue
            else:
                # Single page number
                try:
                    page = int(part)
                    pages.append(page)
                except ValueError:
                    continue
        
        # Remove duplicates and sort
        return sorted(set(pages))

    # ------------------------------------------------------------------
    # Mouse events on viewer
    # ------------------------------------------------------------------

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click on the viewer to add current page to selected."""
        # Check if the double-click was on the viewer label or scroll area
        pos = event.position().toPoint()
        viewer_widget = self._viewer_label
        scroll_widget = self._scroll_area

        # Convert to scroll area coordinates
        scroll_pos = scroll_widget.mapFromGlobal(self.mapToGlobal(pos))

        if scroll_widget.rect().contains(scroll_pos):
            # Double-click in viewer area - add current page to selected
            if self._pdf_info is not None:
                self._add_page_to_selected(self._current_page)

        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Page navigation
        if key == Qt.Key.Key_PageUp or key == Qt.Key.Key_Left:
            self._go_to_previous_page()
        elif key == Qt.Key.Key_PageDown or key == Qt.Key.Key_Right:
            self._go_to_next_page()
        # Zoom
        elif key == Qt.Key.Key_Plus and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._zoom_in()
        elif key == Qt.Key.Key_Minus and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._zoom_out()
        # Add current page to selected (Ctrl+Enter)
        elif key == Qt.Key.Key_Return and modifiers == Qt.KeyboardModifier.ControlModifier:
            if self._pdf_info is not None:
                self._add_page_to_selected(self._current_page)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Status bar and shared panel helper
    # ------------------------------------------------------------------

    def _create_status_bar(self) -> None:
        """Create the application status bar."""
        self.statusBar().showMessage("Ready — no datasheet is open")

    def _create_panel(self, title: str, object_name: str) -> QFrame:
        """Create a consistently styled workspace panel."""
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("panel_title")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        return panel
