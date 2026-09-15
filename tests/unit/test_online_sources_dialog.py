"""Additions for concurrent/cancellable search + Phase-6 strip affordances."""

import threading
import time

from PySide6.QtCore import QSettings

from datasheet_studio.models.search import SearchResult
from datasheet_studio.services.search_service import SearchService
from datasheet_studio.ui.widgets.search_strip import SearchStrip, _ResultRow

from tests.unit.test_search_strip import _wait_for


class _SlowProvider:
    provider_id = "slow"

    def search(self, query, *, limit=30):
        time.sleep(0.05)
        return [SearchResult("slow", "datasheet", f"{query}-slow")]


class _FastProvider:
    provider_id = "fast"

    def search(self, query, *, limit=30):
        return [SearchResult("fast", "datasheet", f"{query}-fast")]


def test_concurrent_search_preserves_provider_order():
    service = SearchService((_SlowProvider(), _FastProvider()))
    response = service.search("dk", provider_ids=("slow", "fast"))
    assert [row.provider_id for row in response.results] == ["slow", "fast"]

    response = service.search("dk", provider_ids=("fast", "slow"))
    assert [row.provider_id for row in response.results] == ["fast", "slow"]


def test_cancelled_search_reports_notice():
    service = SearchService((_FastProvider(),))
    cancel = threading.Event()
    cancel.set()
    response = service.search("dk", cancel_event=cancel)
    assert response.results == ()
    assert any("لغو" in message for _pid, message in response.notices)


class _OnlineService:
    def search(self, query, *, provider_ids=None, limit=30, cancel_event=None):
        return __import__("datasheet_studio.models.search", fromlist=["SearchResponse"]).SearchResponse(
            results=(
                SearchResult(
                    provider_id="digikey",
                    kind="datasheet",
                    title="DK124",
                    subtitle="Linkage",
                    snippet="official API row",
                    url="https://example.com/dk124.pdf",
                    can_preview=True,
                    can_save=True,
                    source_label="DigiKey · API رسمی",
                ),
            )
        )


def test_strip_online_row_preview_and_save_signals(qapp_instance):
    strip = SearchStrip(service_factory=lambda: _OnlineService())
    strip.show()
    strip.set_expanded(True)
    previews = []
    saves = []
    strip.preview_requested.connect(previews.append)
    strip.save_requested.connect(saves.append)
    try:
        strip._query_input.setText("dk124")
        _wait_for(qapp_instance, lambda: strip.state == "results")
        row = strip.findChildren(_ResultRow)[0]

        assert row.open_button.text() == "پیش‌نمایش" and row.open_button.isEnabled()
        assert row.save_button.isEnabled()

        row.open_button.click()
        row.save_button.click()
        assert [r.title for r in previews] == ["DK124"]
        assert [r.title for r in saves] == ["DK124"]
    finally:
        _wait_for(qapp_instance, lambda: not strip._threads)
        strip.close()


def test_strip_default_sources_include_digikey(qapp_instance):
    strip = SearchStrip()
    labels = [strip._source_combo.itemText(i) for i in range(strip._source_combo.count())]
    assert labels[0] == "همه"
    assert "DigiKey" in labels
    strip.close()


def test_settings_dialog_round_trip_and_injected_tester(qapp_instance, tmp_path):
    from PySide6.QtCore import QCoreApplication

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    from datasheet_studio.ui.dialogs.online_sources_dialog import OnlineSourcesDialog

    dialog = OnlineSourcesDialog(
        settings=settings,
        connection_tester=lambda creds: f"ok-{creds.client_id}",
    )
    dialog._digikey_enabled.setChecked(True)
    dialog._digikey_client_id.setText("cid-1")
    dialog._digikey_client_secret.setText("sec-1")

    dialog._test_connection()
    _wait_for(qapp_instance, lambda: dialog._status_label.text().startswith(("✅", "❌")))
    assert "ok-cid-1" in dialog._status_label.text()

    dialog._save()
    assert settings.value("onlineSources/digikeyEnabled", False, type=bool) is True
    assert settings.value("onlineSources/digikeyClientId", "") == "cid-1"
    assert settings.value("onlineSources/digikeyClientSecret", "") == "sec-1"
    dialog.close()
