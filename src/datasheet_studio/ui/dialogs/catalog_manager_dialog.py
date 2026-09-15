"""Persian/RTL catalogue pack manager (Phase 12 review correction).

No-CLI flow: open a pack.json → validate → preview diff against the
installed pack of the same provider → install into the vault → list/rollback
installed versions. Nothing is ever auto-verified.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from datasheet_studio.infrastructure.storage.knowledge_vault import KnowledgeVault
from datasheet_studio.models.magnetics_catalog import (
    load_pack,
    pack_diff,
)


class CatalogManagerDialog(QDialog):
    """Install/update/rollback magnetics packs from the desktop."""

    def __init__(self, parent=None, *, vault_path_getter=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("مدیر کاتالوگ مغناطیسی — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(680, 520)
        self._vault_path_getter = vault_path_getter or (lambda: "")
        self._candidate = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        hint = QLabel(
            "یک فایل pack.json سازنده را باز کنید، پیش‌نمایش تغییرات را ببینید و "
            "نصب کنید. داده‌های نصب‌شده همیشه extracted/reviewed می‌مانند؛ حذف "
            "نسخه فقط پک را برمی‌گرداند و به داده‌های دیگر کاربر دست نمی‌زند."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "QLabel { background: #eef4ff; color: #1c3d6e; border: 1px solid #b8cdf0;"
            " border-radius: 6px; padding: 8px; }"
        )
        root.addWidget(hint)

        row = QHBoxLayout()
        open_button = QPushButton("باز کردن pack.json…")
        open_button.clicked.connect(self._open_pack)
        install_button = QPushButton("نصب در ولت")
        install_button.setEnabled(False)
        install_button.clicked.connect(self._install)
        self._install_button = install_button
        rollback_button = QPushButton("حذف نسخهٔ انتخابی")
        rollback_button.clicked.connect(self._rollback)
        close = QPushButton("بستن")
        close.clicked.connect(self.reject)
        row.addWidget(open_button)
        row.addWidget(install_button)
        row.addWidget(rollback_button)
        row.addStretch()
        row.addWidget(close)
        root.addLayout(row)

        self._status = QLabel("پکی باز نشده است.")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        self._installed_list = QListWidget()
        root.addWidget(self._installed_list, 1)
        self._refresh_installed()

    # -- actions ---------------------------------------------------------------

    def _vault(self) -> KnowledgeVault | None:
        raw = (self._vault_path_getter() or "").strip()
        return KnowledgeVault(raw) if raw else None

    def _open_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "باز کردن پک کاتالوگ", "", "Catalog Pack (pack.json *.json)"
        )
        if not path:
            return
        try:
            candidate = load_pack(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validation errors are data errors
            QMessageBox.critical(self, "پک نامعتبر", str(exc))
            return
        self._candidate = candidate
        vault = self._vault()
        installed = (
            vault.latest_catalog_pack(candidate.provider) if vault else None
        )
        diff = pack_diff(installed, candidate)
        self._status.setText(
            f"پک «{candidate.provider}» نسخهٔ {candidate.pack_version} — "
            f"{len(candidate.cores)} هسته / {len(candidate.materials)} جنس / "
            f"{len(candidate.bobbins)} بوبین. تغییرات نسبت به نصب‌شده: "
            f"افزوده {len(diff['added'])}، حذف {len(diff['removed'])}، "
            f"تغییر {len(diff['changed'])}."
        )
        needs_vault = "برای نصب، ابتدا کتابخانهٔ دانش v2 را فعال کنید." if vault is None else ""
        self._install_button.setEnabled(vault is not None)
        if needs_vault:
            self._status.setText(self._status.text() + " " + needs_vault)

    def _install(self) -> None:
        vault = self._vault()
        if vault is None or self._candidate is None:
            return
        try:
            target = vault.write_catalog_pack(self._candidate)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "نصب پک", str(exc))
            return
        self._status.setText(f"✅ نصب شد: {target}")
        self._install_button.setEnabled(False)
        self._refresh_installed()

    def _rollback(self) -> None:
        item = self._installed_list.currentItem()
        if item is None:
            return
        provider, version = item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self,
            "حذف نسخه",
            f"پک «{provider}» نسخهٔ {version} حذف شود؟ (فقط همین پک.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        vault = self._vault()
        if vault is None:
            return
        try:
            vault.rollback_catalog_pack(provider, version)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "حذف نسخه", str(exc))
            return
        self._refresh_installed()

    def _refresh_installed(self) -> None:
        self._installed_list.clear()
        vault = self._vault()
        if vault is None:
            self._installed_list.addItem(
                QListWidgetItem("ولت فعالی وجود ندارد (Library → Upgrade Library to v2).")
            )
            return
        for pack in vault.catalog_packs():
            item = QListWidgetItem(
                f"{pack.provider} — نسخهٔ {pack.pack_version} — "
                f"{len(pack.cores)} هسته ({pack.imported_at or 'زمان نامشخص'})"
            )
            item.setData(Qt.ItemDataRole.UserRole, (pack.provider, pack.pack_version))
            self._installed_list.addItem(item)
