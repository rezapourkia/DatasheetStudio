"""Offscreen tests for the library upgrade dialog (no real threads)."""

from pathlib import Path

import pytest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.services.library_migration import LibraryMigrator
from datasheet_studio.ui.dialogs.library_upgrade_dialog import LibraryUpgradeDialog


def make_pdf(path: Path, text: str = "DK124") -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def v1_library(tmp_path: Path) -> Path:
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="Dialog Library")
    source = tmp_path / "dk124.pdf"
    make_pdf(source)
    store.add_item_from_source(
        source,
        manufacturer_folder="Linkage",
        manufacturer="Linkage",
        part_number="DK124",
        title="DK124 Datasheet",
    )
    return root


@pytest.fixture()
def cleanup_settings():
    yield
    QSettings().remove("knowledgeBasePath")


def test_preview_updates_summary_and_enables_start(qapp_instance, v1_library):
    dialog = LibraryUpgradeDialog(str(v1_library))
    assert dialog._default_target().endswith("v1-v2")

    dialog._do_preview()

    assert "اقلام: 1" in dialog._summary_label.text()
    assert "فایل موجود: 1" in dialog._summary_label.text()
    assert dialog._start_button.isEnabled()


def test_finished_report_enables_accept_and_rollback(
    qapp_instance, v1_library, tmp_path, cleanup_settings
):
    dialog = LibraryUpgradeDialog(str(v1_library))
    target = tmp_path / "vault"
    report = LibraryMigrator().migrate(v1_library, target)

    dialog._on_migration_finished(report)

    assert dialog._accept_button.isEnabled()
    assert dialog._rollback_button.isEnabled()
    assert "واردشده: 1" in dialog._summary_label.text()
    assert dialog._report_list.count() >= 1


def test_final_acceptance_writes_settings_and_marks_vault(
    qapp_instance, v1_library, tmp_path, monkeypatch, cleanup_settings
):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    dialog = LibraryUpgradeDialog(str(v1_library))
    target = tmp_path / "vault"
    report = LibraryMigrator().migrate(v1_library, target)
    dialog._on_migration_finished(report)

    dialog._accept_upgrade()

    settings = QSettings()
    assert settings.value("knowledgeBasePath", "") == str(target)
    _, accepted = KnowledgeVault(target).read_identity()
    assert accepted is True
    assert not dialog._accept_button.isEnabled()


def test_rollback_removes_vault_and_clears_settings(
    qapp_instance, v1_library, tmp_path, monkeypatch, cleanup_settings
):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    dialog = LibraryUpgradeDialog(str(v1_library))
    target = tmp_path / "vault"
    report = LibraryMigrator().migrate(v1_library, target)
    dialog._on_migration_finished(report)
    dialog._accept_upgrade()

    dialog._rollback_upgrade()

    assert not target.exists()
    assert QSettings().value("knowledgeBasePath", "") == ""
    assert dialog._start_button.isEnabled()
