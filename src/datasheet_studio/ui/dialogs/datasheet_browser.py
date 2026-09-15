"""Embedded Chromium browser for online datasheet search (owner-directed UX).

The owner explicitly asked for a browser *inside* Datasheet Studio: search the
web (Google by default), open datasheet PDFs from result links, and add them
to the local library without ever leaving the application (ADR-021).
Browsing stays user-driven only (ADR-012): no scraping. Downloaded files are
validated (%PDF, SHA-256) and can be saved straight into the accepted v2
knowledge vault; without a vault the legacy v1 signal is kept as fallback.
"""

import logging
import os
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus
from uuid import uuid4

from PySide6.QtCore import QFileInfo, QUrl, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

from datasheet_studio.services.knowledge_hash import sha256_file
from datasheet_studio.services.online_import import OnlineImportError

LOG = logging.getLogger("datasheet_studio.ui.browser")

SEARCH_ENGINES: tuple[tuple[str, str, str], ...] = (
    # (id, label, query-url prefix)
    ("google", "Google", "https://www.google.com/search?q="),
    ("duckduckgo", "DuckDuckGo", "https://duckduckgo.com/?q="),
    ("bing", "Bing", "https://www.bing.com/search?q="),
)

QUICK_LINKS = [
    ("Octopart", "https://octopart.com/search?q="),
    ("DigiKey", "https://www.digikey.com/en/products/result?keywords="),
    ("Mouser", "https://www.mouser.com/Search/Refine?Keyword="),
    ("SnapEDA", "https://www.snapeda.com/search/?q="),
    ("Component Search", "https://componentsearchengine.com/search?term="),
]

DEFAULT_ENGINE = "google"


def search_url(engine_id: str, query: str) -> str:
    """Build a web-search URL for the given engine and free-text query."""

    prefix = next(
        (prefix for eid, _label, prefix in SEARCH_ENGINES if eid == engine_id),
        SEARCH_ENGINES[0][2],
    )
    terms = " ".join(query.split())
    return prefix + quote_plus(terms)


def looks_like_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(5).lstrip().startswith(b"%PDF-")
    except OSError:
        return False


class DatasheetBrowserDialog(QDialog):
    """A Chromium window inside Datasheet Studio for datasheet hunting."""

    add_download_to_library = Signal(str)  # legacy v1 flow (no v2 vault)
    open_pdf_requested = Signal(str)  # open a downloaded PDF in the viewer
    saved_to_vault = Signal(str)  # human-readable save result message

    def __init__(
        self,
        parent=None,
        download_dir: str | Path | None = None,
        *,
        vault_path_getter: Callable[[], str] | None = None,
        import_service=None,
        initial_query: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("مرورگر وب — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1180, 800)

        if download_dir is None:
            download_dir = Path(os.path.expanduser("~")) / "DatasheetStudio_downloads"
        self._download_dir = Path(download_dir)
        try:
            self._download_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover - defensive
            LOG.warning("Could not create download dir %s: %s", self._download_dir, exc)

        self._vault_path_getter = vault_path_getter or (lambda: "")
        self._import_service = import_service
        self._downloads: list = []
        self._build_ui()
        if initial_query.strip():
            self.search_web(initial_query)

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        self._back_button = QPushButton("⟵")
        self._back_button.setToolTip("عقب")
        self._forward_button = QPushButton("⟶")
        self._forward_button.setToolTip("جلو")
        self._reload_button = QPushButton("⟳")
        self._reload_button.setToolTip("بارگذاری دوباره")
        self._address = QLineEdit()
        self._address.setPlaceholderText("نشانی سایت یا عبارت جست‌وجو + Enter")
        self._address.returnPressed.connect(self._navigate)
        self._engine_combo = QComboBox()
        for engine_id, label, _prefix in SEARCH_ENGINES:
            self._engine_combo.addItem(label, engine_id)
        self._engine_combo.setToolTip("موتور جست‌وجوی نوار نشانی")
        go_button = QPushButton("برو")
        go_button.clicked.connect(self._navigate)
        nav.addWidget(self._back_button)
        nav.addWidget(self._forward_button)
        nav.addWidget(self._reload_button)
        nav.addWidget(self._address, 1)
        nav.addWidget(self._engine_combo)
        nav.addWidget(go_button)
        layout.addLayout(nav)

        links = QHBoxLayout()
        links.setSpacing(4)
        for label, url in QUICK_LINKS:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _=False, u=url: self._quick_search(u, from_menu=True)
            )
            links.addWidget(button)
        system_button = QPushButton("🌐 مرورگر ویندوز")
        system_button.setToolTip("باز کردن همین نشانی در مرورگر پیش‌فرض سیستم")
        system_button.clicked.connect(self._open_in_system_browser)
        links.addStretch()
        links.addWidget(system_button)
        layout.addLayout(links)

        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView

            self._web_view = QWebEngineView()
            profile = self._web_view.page().profile()
            profile.downloadRequested.connect(self._on_download_requested)
            self._back_button.clicked.connect(self._web_view.back)
            self._forward_button.clicked.connect(self._web_view.forward)
            self._reload_button.clicked.connect(self._web_view.reload)
            layout.addWidget(self._web_view, 1)
            self._web_view.setUrl(QUrl("https://www.google.com"))
            self._web_view.urlChanged.connect(self._on_url_changed)
            self._browser_fallback = False
        except Exception as exc:  # noqa: BLE001 - fall back to system browser
            LOG.warning("QtWebEngine unavailable, using system browser: %s", exc)
            self._browser_fallback = True
            fallback_box = QWidget()
            fallback_layout = QVBoxLayout(fallback_box)
            info = QLabel(
                "مرورگر داخلی در این محیط راه‌اندازی نشد.\n"
                "از لینک‌های سریع استفاده کنید یا نشانی را وارد و «مرورگر ویندوز» را بزنید."
            )
            info.setWordWrap(True)
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback_layout.addWidget(info)
            layout.addWidget(fallback_box, 1)

        downloads_label = QLabel(
            f"دانلودها → {self._download_dir}  |  فایل‌های PDF دانلودشده را می‌توانید "
            "مستقیم در نمایشگر برنامه باز کنید یا به کتابخانه دانش اضافه کنید."
        )
        downloads_label.setStyleSheet("color: #66717d; font-size: 11px;")
        downloads_label.setWordWrap(True)
        layout.addWidget(downloads_label)
        self._downloads_list = QListWidget()
        self._downloads_list.setMaximumHeight(140)
        layout.addWidget(self._downloads_list)

    # -- navigation -----------------------------------------------------------

    def search_web(self, query: str) -> None:
        """Run a web search for ``query`` in the embedded browser."""

        engine_id = str(self._engine_combo.currentData() or DEFAULT_ENGINE)
        url = search_url(engine_id, query)
        self._address.setText(url)
        self._navigate()

    def _on_url_changed(self, url: QUrl) -> None:
        self._address.setText(url.toString())

    def _navigate(self) -> None:
        text = self._address.text().strip()
        if not text:
            return
        if "://" not in text and "." not in text:
            # Free text without a dot: treat as a web search.
            self.search_web(text)
            return
        url = text if "://" in text else "https://" + text
        if self._browser_fallback:
            self._open_in_system_browser(url)
        else:
            self._web_view.setUrl(QUrl(url))

    def _quick_search(self, base_url: str, *, from_menu: bool = False) -> None:
        query = self._address.text().strip()
        if query.startswith("http") or "://" in query:
            query = ""
        self._address.setText(base_url + quote_plus(" ".join(query.split())))
        self._navigate()

    def _open_in_system_browser(self, url: str | None = None) -> None:
        import webbrowser

        target = (url or self._address.text()).strip()
        if "://" not in target:
            target = "https://" + target
        webbrowser.open(target)

    # -- downloads ------------------------------------------------------------

    def _on_download_requested(self, download) -> None:
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
        name = QFileInfo(download.downloadFileName()).fileName()
        if not name:
            name = f"download-{uuid4().hex[:8]}"
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
                return

        is_pdf = looks_like_pdf(path)
        item = QListWidgetItem(("📄 " if is_pdf else "📦 ") + path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        item.setToolTip(str(path))
        self._downloads_list.addItem(item)

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 0, 4, 0)
        if is_pdf:
            open_button = QPushButton("باز کردن در نمایشگر")
            open_button.setToolTip("باز کردن همین فایل در نمایشگر PDF برنامه")
            open_button.clicked.connect(
                lambda _=False, p=str(path): self.open_pdf_requested.emit(p)
            )
            row.addWidget(open_button)
            add_button = QPushButton("افزودن به کتابخانه")
            add_button.setToolTip(
                "اعتبارسنجی و ذخیره در کتابخانهٔ دانش v2 (و در نبود آن، کتابخانه v1)"
            )
            add_button.clicked.connect(
                lambda _=False, p=str(path): self._save_download(Path(p))
            )
            row.addWidget(add_button)
        else:
            note = QLabel("فایل PDF نیست؛ برای کتابخانهٔ دانش قابل ذخیره نیست.")
            note.setStyleSheet("color: #8a5a00;")
            row.addWidget(note)
        self._downloads_list.setItemWidget(item, container)

    def _save_download(self, path: Path) -> None:
        """Save a downloaded PDF into the v2 vault (or fall back to v1)."""

        vault_path = (self._vault_path_getter() or "").strip()
        if vault_path and self._import_service is not None:
            if not looks_like_pdf(path):
                QMessageBox.warning(
                    self, "افزودن به کتابخانه", "این فایل یک PDF معتبر نیست."
                )
                return
            from datasheet_studio.infrastructure.web.http_client import DownloadedFile

            try:
                downloaded = DownloadedFile(
                    path=path,
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                    final_url=self._address.text().strip(),
                    content_type="application/pdf",
                )
                outcome = self._import_service.save_to_vault(
                    downloaded,
                    manufacturer="",
                    part_number=path.stem,
                    title=path.stem,
                )
            except OnlineImportError as exc:
                QMessageBox.warning(self, "افزودن به کتابخانه", str(exc))
                return
            message = (
                f"«{path.name}» در کتابخانهٔ دانش ذخیره شد"
                + (" (محتوای تکراری — شیء منبع موجود بود)" if outcome.duplicate else "")
                + " و در جست‌وجوی محلی پیدا می‌شود."
            )
            self.saved_to_vault.emit(message)
            return
        # Legacy v1 flow (or explicit v1 library usage).
        self.add_download_to_library.emit(str(path))
