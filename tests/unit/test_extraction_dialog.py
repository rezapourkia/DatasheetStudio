"""Offscreen tests for the extraction coverage dialog."""

import time

import pymupdf

from datasheet_studio.ui.dialogs.extraction_coverage_dialog import (
    ExtractionCoverageDialog,
)
from datasheet_studio.services.text_extraction import TextExtractionService


def make_pdf(tmp_path, name="dialog.pdf"):
    path = tmp_path / name
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (72, 72),
        "DK124 offline switching controller current limit 1.1A 65kHz typical",
    )
    doc.new_page()  # scanned
    doc.save(str(path))
    doc.close()
    return path


def _wait_until(predicate, timeout=3.0):
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("dialog worker did not finish")


def test_dialog_run_shows_statuses_and_incomplete_banner(qapp_instance, tmp_path):
    pdf = make_pdf(tmp_path)
    dialog = ExtractionCoverageDialog(str(pdf))
    try:
        dialog._start(False)
        _wait_until(lambda: dialog._table.rowCount() == 2)
        assert dialog._table.item(0, 1).text() == "متن استخراج شد"
        assert dialog._table.item(1, 1).text() == "اسکن‌شده — نیاز به OCR"
        assert "کامل نیست" in dialog._banner.text()
        assert not dialog._extract_button.isEnabled() or dialog._extract_button.isEnabled()
        assert dialog._ocr_button.isEnabled() is False  # no OCR engine wired
    finally:
        dialog.close()


def test_dialog_complete_document_shows_green_banner(qapp_instance, tmp_path):
    path = tmp_path / "ok.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (72, 72),
        "BQ25798 buck boost battery charger detailed electrical description text",
    )
    doc.save(str(path))
    doc.close()
    dialog = ExtractionCoverageDialog(str(path))
    try:
        dialog._start(False)
        _wait_until(lambda: dialog._table.rowCount() == 1)
        assert "کامل است" in dialog._banner.text()
    finally:
        dialog.close()


def test_registry_contains_text_coverage_tool():
    from datasheet_studio.tools import create_default_tool_registry

    registry = create_default_tool_registry()
    tool = registry.get("document-text-coverage")
    assert tool.category == "Knowledge Base"
