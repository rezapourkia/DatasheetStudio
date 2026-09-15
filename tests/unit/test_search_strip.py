"""Offscreen UI tests for the collapsible bottom search strip."""

import time

from PySide6.QtCore import Qt

from datasheet_studio.services.search_service import SearchResponse, SearchResult
from datasheet_studio.ui.main_window import MainWindow
from datasheet_studio.ui.widgets.search_strip import SearchStrip, _ResultRow


class _StateService:
    def search(self, query, *, provider_ids=None, limit=30):
        if query == "slow":
            time.sleep(0.15)
        if query == "none":
            return SearchResponse()
        if query == "error":
            return SearchResponse(errors=(("mock", "خطای آزمایشی"),))
        if query == "novault":
            return SearchResponse(notices=(("local-kb", "ولت فعالی وجود ندارد"),))
        return SearchResponse(
            results=(
                SearchResult(
                    provider_id="local-kb",
                    kind="page",
                    title=query,
                    subtitle="Linkage · page 3",
                    snippet="current «limit» value",
                    pdf_path="C:/vault/dk124.pdf",
                    page=3,
                    can_preview=True,
                    source_label="کتابخانهٔ محلی",
                ),
            )
        )


def _wait_for(qapp, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for search worker")


def _search(strip, qapp, query):
    strip._query_input.setText(query)
    strip.search_now()
    _wait_for(qapp, lambda: strip.state != "searching")


def test_strip_is_rtl_collapsible_and_debounce_searches(qapp_instance):
    strip = SearchStrip(service_factory=lambda: _StateService())
    strip.show()
    try:
        assert strip.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert strip.state == "hint"
        assert strip.is_expanded() is False

        strip.toggle_and_focus()
        strip.activateWindow()
        qapp_instance.processEvents()
        assert strip.is_expanded() is True
        assert strip._query_input.focusPolicy() != Qt.FocusPolicy.NoFocus

        strip._query_input.setText("DK124")
        _wait_for(qapp_instance, lambda: strip.state == "results", timeout=3.0)
        assert strip.findChildren(_ResultRow)

        strip.toggle_and_focus()
        assert strip.is_expanded() is False
    finally:
        _wait_for(qapp_instance, lambda: not strip._threads)
        strip.close()


def test_strip_renders_no_results_error_and_no_vault_states(qapp_instance):
    strip = SearchStrip(service_factory=lambda: _StateService())
    strip.show()
    strip.set_expanded(True)
    try:
        _search(strip, qapp_instance, "none")
        assert strip.state == "no-results"

        _search(strip, qapp_instance, "error")
        assert strip.state == "error"
        assert strip._retry_button.isVisible()

        _search(strip, qapp_instance, "novault")
        assert strip.state == "no-vault"
        assert "ولت" in strip._state_label.text()
    finally:
        _wait_for(qapp_instance, lambda: not strip._threads)
        strip.close()


def test_open_copy_and_save_affordances(qapp_instance):
    strip = SearchStrip(service_factory=lambda: _StateService())
    strip.show()
    opened = []
    strip.open_requested.connect(lambda path, page: opened.append((path, page)))
    try:
        _search(strip, qapp_instance, "DK124")
        row = strip.findChildren(_ResultRow)[0]
        assert row.open_button.isEnabled()
        assert row.copy_button.isEnabled()
        assert not row.save_button.isEnabled()

        row.open_button.click()
        assert opened == [("C:/vault/dk124.pdf", 3)]
        row.copy_button.click()
        assert qapp_instance.clipboard().text() == "C:/vault/dk124.pdf"
    finally:
        _wait_for(qapp_instance, lambda: not strip._threads)
        strip.close()


def test_stale_worker_result_is_discarded(qapp_instance):
    strip = SearchStrip(service_factory=lambda: _StateService())
    strip.show()
    try:
        strip._query_input.setText("slow")
        strip.search_now()
        strip._query_input.setText("newest")
        strip.search_now()

        _wait_for(qapp_instance, lambda: strip.state == "results")
        rows = strip.findChildren(_ResultRow)
        assert [row.result.title for row in rows] == ["newest"]
        _wait_for(qapp_instance, lambda: not strip._threads)
        assert [row.result.title for row in strip.findChildren(_ResultRow)] == ["newest"]
    finally:
        strip.shutdown()
        strip.close()


def test_main_window_hosts_strip_outside_splitter_and_registers_ctrl_k(qapp_instance):
    window = MainWindow()
    try:
        assert window.centralWidget() is window._workspace_splitter
        assert window._workspace_splitter.count() == 4
        assert window._search_dock.widget() is window._search_strip
        assert window._search_strip.parentWidget() is not window._workspace_splitter
        assert window._search_strip_action.shortcut().toString() == "Ctrl+K"

        window._search_strip_action.trigger()
        assert window._search_strip.is_expanded()
        assert window._search_dock.height() == 270
    finally:
        window.close()
