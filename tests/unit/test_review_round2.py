"""Review round 2: real-button UI paths and isolated test settings."""

import json
import time
from pathlib import Path

import pymupdf
import pytest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.ui.dialogs.ai_extraction_review_dialog import (
    AiExtractionReviewDialog,
)
from datasheet_studio.tools.flyback_designer.dialog import FlybackDesignerDialog


def _wait_until(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


# --- isolated settings --------------------------------------------------------


def test_qsettings_stay_in_temp_ini(isolated_qsettings):
    # Production code (and this suite) uses QSettings(), which honors the
    # default format + app-level organization/application names.
    settings = QSettings()
    assert settings.format() == QSettings.Format.IniFormat
    file_name = settings.fileName()
    assert Path(file_name).is_relative_to(Path(str(isolated_qsettings)))
    assert file_name.endswith(".ini")
    assert "HKEY" not in file_name  # never the Windows registry
    settings.setValue("reviewRound2/probe", "kept-out-of-user-store")
    settings.sync()
    assert Path(file_name).exists()


# --- AI extraction dialog: real consent → run → display → accept → archive ----


def _make_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "dk124_ai.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (72, 72),
        "DK124 controller fixed frequency 65kHz switching regulator ic",
    )
    doc.save(str(pdf))
    doc.close()
    return pdf


def _ai_response(prompt: str) -> str:
    return json.dumps(
        {
            "manufacturer": "Linkage",
            "part_number": "DK124",
            "fields": [
                {"name": "frequency_khz", "value": 65.0, "unit": "kHz", "page": 1},
            ],
            "contradictions": [],
            "unknown_facts": [],
        },
        ensure_ascii=False,
    )


def test_ai_dialog_real_button_flow_to_archive(qapp_instance, tmp_path):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "AI Flow Vault").mark_accepted()
    pdf = _make_pdf(tmp_path)

    dialog = AiExtractionReviewDialog(
        pdf_path=str(pdf),
        ai_chat=_ai_response,
        vault_path_getter=lambda: str(vault_root),
        provider="fake",
        model="test-model",
    )
    try:
        assert not dialog._run_button.isEnabled()  # consent gate holds
        dialog._consent.setChecked(True)  # the real checkbox
        assert dialog._run_button.isEnabled()
        dialog._run_button.click()  # the real run button

        assert _wait_until(lambda: dialog._table.rowCount() == 1)
        assert dialog._accept_button.isEnabled()
        row_label = dialog._table.item(0, 1).text()
        assert "frequency_khz" in row_label  # response is displayed

        dialog._accept_button.click()  # the real acceptance button
        assert _wait_until(
            lambda: "پذیرفته" in dialog._status.text()
        )

        profiles = list((vault_root / "records" / "components").rglob("profile.json"))
        assert profiles, "accepted profile must be stored in the vault"
        runs = list((vault_root / "ai-runs").glob("*/metadata.json"))
        assert runs, "the AI run must be archived"
        meta = json.loads(runs[0].read_text(encoding="utf-8"))
        assert meta["provider"] == "fake" and meta["model"] == "test-model"
        assert meta["complete"] is True and meta["omitted_pages"] == []
        assert list((runs[0].parent / "chunks").glob("chunk-*"))
    finally:
        dialog.close()


def test_ai_dialog_failure_shows_retry(qapp_instance, tmp_path):
    def broken(prompt: str) -> str:
        raise ConnectionError("provider down")

    dialog = AiExtractionReviewDialog(
        pdf_path=str(_make_pdf(tmp_path)),
        ai_chat=broken,
        vault_path_getter=lambda: "",
    )
    try:
        dialog._consent.setChecked(True)
        dialog._run_button.click()
        assert _wait_until(lambda: not dialog._retry_button.isHidden())
        assert "ناموفق" in dialog._status.text()
    finally:
        dialog.close()


# --- Flyback project open/save through the real buttons ----------------------


def test_flyback_save_then_open_with_real_buttons(qapp_instance, tmp_path, monkeypatch):
    target = tmp_path / "design.flyback.json"

    saving = FlybackDesignerDialog(prefill={"frequency_khz": 100.0})
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    saving._save_project_button.click()
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["project"]["frequency_khz"] == 100.0
    saving.close()

    opening = FlybackDesignerDialog()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    opening._open_project_button.click()
    assert opening._fields["frequency_khz"].value() == 100.0
    assert opening._status.text().startswith("باز شد")
    opening.close()
