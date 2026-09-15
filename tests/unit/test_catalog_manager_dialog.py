"""Offscreen tests for the no-CLI catalogue pack manager."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QListWidget

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.magnetics_catalog import dump_pack
from datasheet_studio.ui.dialogs.catalog_manager_dialog import CatalogManagerDialog

from tests.unit.test_magnetics_catalog import pack


def test_open_preview_install_and_rollback_without_cli(qapp_instance, tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    KnowledgeVault.create(vault_root, "Mgr Vault")
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(dump_pack(pack()), encoding="utf-8")

    dialog = CatalogManagerDialog(vault_path_getter=lambda: str(vault_root))
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(pack_file), "")),
    )

    dialog._open_pack()
    assert "tdk-official" in dialog._status.text()
    assert dialog._install_button.isEnabled()

    dialog._install()
    assert "نصب شد" in dialog._status.text()
    assert vault_root.joinpath("catalogs", "tdk-official", "2026.09", "pack.json").is_file()

    dialog._installed_list.setCurrentRow(0)
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.question",
        staticmethod(lambda *a, **k: __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes),
    )
    dialog._rollback()
    assert not vault_root.joinpath("catalogs", "tdk-official", "2026.09").exists()
    dialog.close()


def test_without_vault_install_is_blocked_with_guidance(qapp_instance):
    dialog = CatalogManagerDialog(vault_path_getter=lambda: "")
    assert not dialog._install_button.isEnabled()
    assert dialog._installed_list.count() == 1  # guidance row
    dialog.close()
