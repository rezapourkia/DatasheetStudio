"""Review P1: Phase-4 activation atomicity and close-during-run safety."""

from pathlib import Path

import pymupdf
import pytest

from PySide6.QtCore import QSettings

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.infrastructure.storage.library_store import LibraryStore
from datasheet_studio.services.library_migration import LibraryMigrator
from datasheet_studio.ui.dialogs.library_upgrade_dialog import LibraryUpgradeDialog


def make_v1(tmp_path: Path) -> Path:
    root = tmp_path / "v1"
    store = LibraryStore.create(root, name="Life")
    pdf = tmp_path / "a.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "DK124")
    doc.save(str(pdf))
    doc.close()
    store.add_item_from_source(
        pdf, manufacturer_folder="Linkage", manufacturer="Linkage",
        part_number="DK124",
    )
    return root


@pytest.fixture()
def cleanup_settings():
    yield
    QSettings(APP_ORGANIZATION, APP_NAME).remove("knowledgeBasePath")


def test_accept_failure_does_not_publish_vault_setting(
    qapp_instance, tmp_path, monkeypatch, cleanup_settings
):
    """mark_accepted must run BEFORE QSettings; failure must not publish."""

    monkeypatch.setattr(
        QMessageBox_mod(), "question",
        staticmethod(lambda *a, **k: QMessageBox_yes()),
    )
    critical_calls = []
    monkeypatch.setattr(
        QMessageBox_mod(), "critical",
        staticmethod(lambda *a, **k: critical_calls.append(a)),
    )
    dialog = LibraryUpgradeDialog(str(make_v1(tmp_path)))
    target = tmp_path / "vault"
    report = LibraryMigrator().migrate(dialog._source_root, target)
    dialog._on_migration_finished(report)

    import datasheet_studio.infrastructure.storage.knowledge_vault as vault_module

    def boom(self):
        raise vault_module.VaultError("disk full")

    monkeypatch.setattr(vault_module.KnowledgeVault, "mark_accepted", boom)
    dialog._accept_upgrade()

    assert critical_calls  # the failure was surfaced, not swallowed
    settings = QSettings(APP_ORGANIZATION, APP_NAME)
    assert settings.value("knowledgeBasePath", "") == ""  # NOT published
    _, accepted = KnowledgeVault(target).read_identity()
    assert accepted is False
    dialog.close()


def QMessageBox_mod():
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox


def QMessageBox_yes():
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox.StandardButton.Yes


def test_close_is_blocked_while_worker_runs(qapp_instance, tmp_path):
    dialog = LibraryUpgradeDialog(str(make_v1(tmp_path)))

    class _FakeWorker:
        def isRunning(self):
            return True

    dialog._worker = _FakeWorker()
    dialog.reject()  # must be refused while running
    assert dialog.isVisible() or dialog.result() == 0
    assert dialog._pending_close is True

    dialog._worker = None  # simulate finished
    dialog.reject()
    assert dialog.result() != 0 or not dialog.isVisible()


def test_successful_accept_marks_then_publishes(
    qapp_instance, tmp_path, monkeypatch, cleanup_settings
):
    monkeypatch.setattr(
        QMessageBox_mod(), "question",
        staticmethod(lambda *a, **k: QMessageBox_yes()),
    )
    source = make_v1(tmp_path)
    dialog = LibraryUpgradeDialog(str(source))
    target = tmp_path / "vault2"
    report = LibraryMigrator().migrate(source, target)
    dialog._on_migration_finished(report)
    dialog._accept_upgrade()

    _, accepted = KnowledgeVault(target).read_identity()
    assert accepted is True
    assert QSettings(APP_ORGANIZATION, APP_NAME).value(
        "knowledgeBasePath", ""
    ) == str(target)
    dialog.close()
