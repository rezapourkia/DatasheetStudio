"""Offline tests for the embedded browser's non-GUI logic and wiring."""

from pathlib import Path

import pymupdf
import pytest

from datasheet_studio.ui.dialogs.datasheet_browser import (
    DatasheetBrowserDialog,
    looks_like_pdf,
    search_url,
)


def test_search_url_builds_engine_prefixes():
    # whitespace collapses; double space becomes a single plus
    assert (
        search_url("google", "DK124  datasheet")
        == "https://www.google.com/search?q=DK124+datasheet"
    )
    assert search_url("duckduckgo", "dk124").startswith("https://duckduckgo.com/?q=dk124")
    assert search_url("bing", "dk124").startswith("https://www.bing.com/search?q=dk124")
    # unknown engine falls back to Google
    assert search_url("nope", "dk124").startswith("https://www.google.com/search?q=")


def test_looks_like_pdf(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "hi")
    doc.save(str(pdf))
    doc.close()
    assert looks_like_pdf(pdf) is True

    text_file = tmp_path / "b.pdf"
    text_file.write_text("<html>nope</html>", encoding="utf-8")
    assert looks_like_pdf(text_file) is False
    assert looks_like_pdf(tmp_path / "missing.pdf") is False


def make_dialog(qapp_instance, tmp_path, **kwargs):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    kwargs.setdefault("download_dir", tmp_path / "dl")
    try:
        return DatasheetBrowserDialog(**kwargs)
    except Exception as exc:  # noqa: BLE001 - WebEngine may not start headless
        pytest.skip(f"QtWebEngine view could not start: {exc}")


def test_download_entry_offers_open_and_vault_save(qapp_instance, tmp_path):
    dialog = make_dialog(
        qapp_instance,
        tmp_path,
        vault_path_getter=lambda: "",
        import_service=None,
    )
    pdf = tmp_path / "dk124.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "DK124")
    doc.save(str(pdf))
    doc.close()

    opened = []
    dialog.open_pdf_requested.connect(opened.append)
    dialog._add_download_entry(pdf)

    assert dialog._downloads_list.count() == 1
    dialog.open_pdf_requested.emit(str(pdf))
    assert opened == [str(pdf)]
    dialog.close()


def test_save_download_without_vault_falls_back_to_v1_signal(qapp_instance, tmp_path):
    dialog = make_dialog(
        qapp_instance, tmp_path, vault_path_getter=lambda: "", import_service=None
    )
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.7 stub")
    legacy = []
    dialog.add_download_to_library.connect(legacy.append)

    dialog._save_download(pdf)

    assert legacy == [str(pdf)]
    dialog.close()


def test_save_download_routes_into_vault(qapp_instance, tmp_path):
    from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
    from datasheet_studio.services.online_import import OnlineImportService

    root = tmp_path / "vault"
    KnowledgeVault.create(root, "Browser Vault").mark_accepted()
    dialog = make_dialog(
        qapp_instance,
        tmp_path,
        vault_path_getter=lambda: str(root),
        import_service=OnlineImportService(lambda: str(root)),
    )
    pdf = tmp_path / "y.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "BQ25798")
    doc.save(str(pdf))
    doc.close()

    messages = []
    dialog.saved_to_vault.connect(messages.append)
    dialog._save_download(pdf)

    assert messages and "ذخیره شد" in messages[0]
    objects = list((root / "objects" / "sha256").rglob("*.pdf"))
    assert len(objects) == 1
    dialog.close()
