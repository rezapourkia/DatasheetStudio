"""Embedded web browser dialog for searching and downloading datasheets.

Browsing is user-driven only (ADR-012): no automatic scraping. Files the
user downloads are routed to a temporary ``_downloads`` folder and can be
added to the library from the dialog.

If the QtWebEngine widgets cannot be initialized (headless/CI, missing
runtime files) the dialog falls back to the system browser.
"""

import logging
import os
import webbrowser
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LOG = logging.getLogger("datasheet_studio.ui.browser")

QUICK_LINKS = [
    ("Octopart", "https://octopart.com/search?q="),
    ("DigiKey", "https://www.digikey.com/en/products/result?keywords="),
    ("Mouser", "https://www.mouser.com/Search/Refine?Keyword="),
    ("SnapEDA", "https://www.snapeda.com/search/?q="),
    ("Component Search", "https://componentsearchengine.com/search?term="),
]



class DatasheetBrowserDialog(QDialog):
    """A small Chromium window for searching component sources."""

    add_download_to_library = Signal(str)  # absolute path of a downloaded PDF

    def __init__(self, parent=None, download_dir: str | Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search Datasheets Online — Datasheet Studio")
        self.resize(980, 700)

        if download_dir is None:
            download_dir = Path(os.path.expanduser("~")) / "DatasheetStudio_downloads"
        self._download_dir = Path(download_dir)
        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - defensive
            LOG.warning("Could not create download dir %s: %s", self._download_dir, exc)

        self._downloads: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        self._address = QLineEdit("https://octopart.com")
        self._address.setPlaceholderText("Enter a URL and press Enter")
        self._address.returnPressed.connect(self._navigate)
        go_button = QPushButton("Go")
        go_button.clicked.connect(self._navigate)
        nav.addWidget(QLabel("🔗"))
        nav.addWidget(self._address, 1)
        nav.addWidget(go_button)
        layout.addLayout(nav)

        links = QHBoxLayout()
        links.setSpacing(4)
        for label, url in QUICK_LINKS:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, u=url: self._quick_search(u))
            links.addWidget(button)
        system_button = QPushButton("🌐 System Browser")
        system_button.setToolTip("Open the current address in your default browser")
        system_button.clicked.connect(self._open_in_system_browser)
        links.addWidget(system_button)
        layout.addLayout(links)

        # Embedded browser area (with graceful fallback).
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView

            self._web_view = QWebEngineView()
            profile = self._web_view.page().profile()
            profile.downloadRequested.connect(self._on_download_requested)
            layout.addWidget(self._web_view, 1)
            self._web_view.setUrl(QUrl("https://octopart.com"))
            self._web_view.urlChanged.connect(self._on_url_changed)
            self._browser_fallback = False
        except Exception as exc:  # noqa: BLE001 - fall back to system browser
            LOG.warning("QtWebEngine unavailable, using system browser: %s", exc)
            self._browser_fallback = True
            fallback_box = QWidget()
            fallback_layout = QVBoxLayout(fallback_box)
            info = QLabel(
                "The embedded browser could not be initialized.\n"
                "Use the quick links or type a URL and click "
                "'Open in System Browser'."
            )
            info.setWordWrap(True)
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback_layout.addWidget(info)
            layout.addWidget(fallback_box, 1)

        # Downloads list.
        downloads_label = QLabel(f"Downloads → {self._download_dir}")
        downloads_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(downloads_label)
        self._downloads_list = QListWidget()
        self._downloads_list.setMaximumHeight(120)
        layout.addWidget(self._downloads_list)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_url_changed(self, url: QUrl) -> None:
        self._address.setText(url.toString())

    def _navigate(self) -> None:
        url = self._address.text().strip()
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        if self._browser_fallback:
            self._open_in_system_browser()
        else:
            self._web_view.setUrl(QUrl(url))

    def _quick_search(self, base_url: str) -> None:
        query = self._address.text().strip()
        if not query or query.startswith("http"):
            query = ""
        self._address.setText(base_url + query)
        self._navigate()


    def _open_in_system_browser(self) -> None:
        url = self._address.text().strip()
        if "://" not in url:
            url = "https://" + url
        webbrowser.open(url)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def _on_download_requested(self, download) -> None:
        """Route a download to the temporary folder and track its result."""
        self._downloads.append(download)  # keep a reference (prevents GC)
        download.setDownloadDirectory(str(self._download_dir))
        download.setDownloadFileName(self._safe_download_name(download))
        download.isFinishedChanged.connect(
            lambda: self._on_download_finished(download)
        )
        try:
            download.accept()
        except Exception as exc:  # noqa: BLE001 - never crash the dialog
            LOG.warning("Could not accept download: %s", exc)

    @staticmethod
    def _safe_download_name(download) -> str:
        from PySide6.QtCore import QFileInfo

        name = QFileInfo(download.downloadFileName()).fileName()
        if not name:
            name = "download"
        return name

    def _on_download_finished(self, download) -> None:
        from PySide6.QtWebEngineCore import QWebEngineDownloadRequest

        if not download.isFinished():
            return
        if download.state() != QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            return
        target = Path(download.downloadDirectory()) / download.downloadFileName()
        if not target.is_file():
            return
        self._add_download_entry(target)

    def _add_download_entry(self, path: Path) -> None:
        for i in range(self._downloads_list.count()):
            if self._downloads_list.item(i).data(Qt.ItemDataRole.UserRole) == str(path):
                return  # already listed

        item = QListWidgetItem(str(path.name))
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        item.setToolTip(str(path))
        self._downloads_list.addItem(item)

        add_button = QPushButton("＋ Add to Library")
        add_button.setProperty("downloadPath", str(path))
        add_button.clicked.connect(
            lambda: self._emit_add_download(str(path))
        )
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 0, 4, 0)
        row.addWidget(QLabel("✅"))
        row.addWidget(add_button)
        self._downloads_list.setItemWidget(item, container)

    def _emit_add_download(self, path: str) -> None:
        self.add_download_to_library.emit(path)

