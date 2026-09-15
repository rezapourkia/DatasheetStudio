"""Collapsible Persian/RTL bottom search strip for Phase 5."""

from __future__ import annotations

from collections.abc import Callable
from html import escape

from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.services.search_service import (
    SearchResponse,
    SearchResult,
    SearchService,
    create_phase5_search_service,
)


class _SearchThread(QThread):
    response_ready = Signal(int, object)

    def __init__(
        self,
        generation: int,
        query: str,
        provider_ids: tuple[str, ...],
        service_factory: Callable[[], SearchService],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._generation = generation
        self._query = query
        self._provider_ids = provider_ids
        self._service_factory = service_factory

    def run(self) -> None:
        try:
            response = self._service_factory().search(
                self._query, provider_ids=self._provider_ids
            )
        except Exception as exc:  # noqa: BLE001 - keep optional search isolated
            response = SearchResponse(errors=(("search", str(exc)),))
        self.response_ready.emit(self._generation, response)


class _ResultRow(QFrame):
    def __init__(
        self,
        result: SearchResult,
        open_callback: Callable[[SearchResult], None],
        copy_callback: Callable[[SearchResult], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result = result
        self.setObjectName("searchResultRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame#searchResultRow { background: #ffffff; border: 1px solid #d9e0e7;"
            " border-radius: 7px; } QLabel { border: none; background: transparent; }"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 7, 10, 7)
        outer.setSpacing(10)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(f"<b>{escape(result.title)}</b>")
        title.setTextFormat(Qt.TextFormat.RichText)
        subtitle = QLabel(
            escape(" · ".join(filter(None, (result.subtitle, result.source_label))))
        )
        subtitle.setStyleSheet("color: #66717d; font-size: 11px;")
        subtitle.setWordWrap(True)
        snippet_html = escape(result.snippet).replace("«", "<mark>").replace("»", "</mark>")
        snippet = QLabel(snippet_html or "—")
        snippet.setTextFormat(Qt.TextFormat.RichText)
        snippet.setWordWrap(True)
        text_col.addWidget(title)
        text_col.addWidget(subtitle)
        text_col.addWidget(snippet)
        outer.addLayout(text_col, 1)

        actions = QVBoxLayout()
        actions.setSpacing(3)
        self.open_button = QPushButton("باز کردن")
        self.open_button.setEnabled(result.can_preview and bool(result.pdf_path))
        self.open_button.setToolTip(
            "PDF محلی را در صفحهٔ مرتبط باز می‌کند"
            if self.open_button.isEnabled()
            else "پیش‌نمایش واقعی در Phase 6 فعال می‌شود"
        )
        self.open_button.clicked.connect(lambda: open_callback(result))
        self.copy_button = QPushButton("کپی لینک")
        self.copy_button.setEnabled(bool(result.copy_target))
        self.copy_button.clicked.connect(lambda: copy_callback(result))
        self.save_button = QPushButton("ذخیره در کتابخانه")
        self.save_button.setEnabled(False)
        self.save_button.setToolTip("دانلود و ذخیرهٔ امن در Phase 6 پیاده‌سازی می‌شود")
        actions.addWidget(self.open_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.save_button)
        outer.addLayout(actions)


class SearchStrip(QWidget):
    """Thin collapsed bar that expands into local/mock search results."""

    open_requested = Signal(str, int)
    expanded_changed = Signal(bool)

    def __init__(
        self,
        vault_path_getter: Callable[[], str] | None = None,
        service_factory: Callable[[], SearchService] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bottomSearchStrip")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._vault_path_getter = vault_path_getter or (lambda: "")
        self._service_factory = service_factory
        self._generation = 0
        self._threads: dict[int, _SearchThread] = {}
        self._state = "hint"
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._toggle_button = QPushButton("⌃  جست‌وجوی دیتاشیت‌ها")
        self._toggle_button.setObjectName("searchStripToggle")
        self._toggle_button.setToolTip("باز/بسته کردن جست‌وجو (Ctrl+K)")
        self._toggle_button.clicked.connect(self.toggle_and_focus)
        bar.addWidget(self._toggle_button)
        self._collapsed_hint = QLabel("جست‌وجو در کتابخانهٔ دانش و منابع آینده — Ctrl+K")
        self._collapsed_hint.setStyleSheet("color: #607080;")
        bar.addWidget(self._collapsed_hint, 1)
        layout.addLayout(bar)

        self._expanded_panel = QWidget()
        expanded = QVBoxLayout(self._expanded_panel)
        expanded.setContentsMargins(0, 2, 0, 0)
        expanded.setSpacing(5)

        controls = QHBoxLayout()
        self._query_input = QLineEdit()
        self._query_input.setObjectName("searchQueryInput")
        self._query_input.setPlaceholderText("شماره قطعه، سازنده یا متن؛ مثال: DK124 یا maker:Linkage")
        self._query_input.setClearButtonEnabled(True)
        self._query_input.returnPressed.connect(self.search_now)
        self._query_input.textChanged.connect(self._schedule_search)
        controls.addWidget(self._query_input, 1)

        self._source_combo = QComboBox()
        self._source_combo.setObjectName("searchSourceFilter")
        self._source_combo.addItem("همه", "all")
        self._source_combo.addItem("کتابخانهٔ محلی", "local-kb")
        self._source_combo.addItem("نمایشی", "mock-online")
        self._source_combo.currentIndexChanged.connect(self._schedule_search)
        controls.addWidget(self._source_combo)

        self._search_button = QPushButton("جست‌وجو")
        self._search_button.clicked.connect(self.search_now)
        controls.addWidget(self._search_button)
        expanded.addLayout(controls)

        state_row = QHBoxLayout()
        self._state_label = QLabel()
        self._state_label.setObjectName("searchStateLabel")
        self._state_label.setWordWrap(True)
        state_row.addWidget(self._state_label, 1)
        self._retry_button = QPushButton("تلاش دوباره")
        self._retry_button.clicked.connect(self.search_now)
        self._retry_button.hide()
        state_row.addWidget(self._retry_button)
        expanded.addLayout(state_row)

        self._results_host = QWidget()
        self._results_layout = QVBoxLayout(self._results_host)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(5)
        self._results_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("searchResultsArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._results_host)
        scroll.setMinimumHeight(145)
        expanded.addWidget(scroll, 1)
        layout.addWidget(self._expanded_panel)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self.search_now)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(
            "QWidget#bottomSearchStrip { background: #f4f7fa; border-top: 1px solid #cfd8e2; }"
            "QPushButton#searchStripToggle { font-weight: 600; text-align: right; }"
        )
        self._expanded_panel.hide()
        self._set_state("hint", "برای جست‌وجو عبارت را وارد کنید.")

    @property
    def state(self) -> str:
        return self._state

    def is_expanded(self) -> bool:
        return self._expanded

    @Slot()
    def toggle_and_focus(self) -> None:
        self.set_expanded(not self._expanded)
        if self._expanded:
            self._query_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self._query_input.selectAll()

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._expanded_panel.setVisible(expanded)
        self._toggle_button.setText(
            "⌄  بستن جست‌وجو" if expanded else "⌃  جست‌وجوی دیتاشیت‌ها"
        )
        self.expanded_changed.emit(expanded)
        self.updateGeometry()

    @Slot()
    def _schedule_search(self, *_args: object) -> None:
        if not self._query_input.text().strip():
            self._debounce.stop()
            self._generation += 1
            self._clear_results()
            self._set_state("hint", "برای جست‌وجو عبارت را وارد کنید.")
            return
        self._debounce.start()

    @Slot()
    def search_now(self) -> None:
        self._debounce.stop()
        query = self._query_input.text().strip()
        if not query:
            self._clear_results()
            self._set_state("hint", "برای جست‌وجو عبارت را وارد کنید.")
            return

        self._generation += 1
        generation = self._generation
        source = str(self._source_combo.currentData())
        provider_ids = (
            ("local-kb", "mock-online") if source == "all" else (source,)
        )
        vault_path = self._vault_path_getter()
        factory = self._service_factory or (
            lambda path=vault_path: create_phase5_search_service(path)
        )

        self._clear_results()
        self._set_state("searching", "در حال جست‌وجو…")
        self._search_button.setEnabled(False)

        thread = _SearchThread(generation, query, provider_ids, factory, self)
        thread.response_ready.connect(self._on_search_finished)
        thread.finished.connect(lambda g=generation: self._forget_thread(g))
        self._threads[generation] = thread
        thread.start()

    @Slot(int, object)
    def _on_search_finished(self, generation: int, response: SearchResponse) -> None:
        if generation != self._generation:
            return
        self._search_button.setEnabled(True)
        self._clear_results()
        for result in response.results:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1,
                _ResultRow(result, self._open_result, self._copy_result, self._results_host),
            )

        messages = [message for _provider, message in response.notices]
        errors = [message for _provider, message in response.errors]
        if response.results:
            suffix = "  |  ".join(messages + errors)
            message = f"{len(response.results)} نتیجه پیدا شد."
            self._set_state("results", f"{message} {suffix}".strip())
        elif messages and not errors:
            self._set_state("no-vault", "  |  ".join(messages))
        elif errors:
            self._set_state("error", "  |  ".join(errors))
        else:
            self._set_state("no-results", "نتیجه‌ای پیدا نشد.")

    def _forget_thread(self, generation: int) -> None:
        self._threads.pop(generation, None)

    def shutdown(self) -> None:
        """Stop timers and wait for the bounded Phase-5 local/mock work."""

        self._debounce.stop()
        self._generation += 1
        for thread in tuple(self._threads.values()):
            thread.requestInterruption()
            thread.wait(3000)
        self._threads.clear()

    def _set_state(self, state: str, message: str) -> None:
        self._state = state
        self._state_label.setProperty("searchState", state)
        self._state_label.setText(message)
        self._retry_button.setVisible(state == "error")
        self._state_label.style().unpolish(self._state_label)
        self._state_label.style().polish(self._state_label)

    def _clear_results(self) -> None:
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _open_result(self, result: SearchResult) -> None:
        if result.pdf_path:
            self.open_requested.emit(result.pdf_path, result.page or 1)

    def _copy_result(self, result: SearchResult) -> None:
        target = result.copy_target
        clipboard = QApplication.clipboard()
        if target and clipboard is not None:
            clipboard.setText(target)
            self._set_state("results", "لینک/مسیر نتیجه در کلیپ‌بورد کپی شد.")
