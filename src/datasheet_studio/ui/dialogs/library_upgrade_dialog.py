"""Persian/RTL desktop dialog for the safe v1 → v2 library upgrade.

Implements the Phase 4 UI contract in ``docs/modules/LIBRARY_UPGRADE.md``:
preview → cancellable run → itemized report → explicit final acceptance or
rollback.  All migration work runs on a worker thread; the dialog only
receives signals (see the threading rule in ``KNOWLEDGE_INDEX.md`` §2).
"""

from __future__ import annotations

import logging
from pathlib import Path
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.services.library_migration import (
    LibraryMigrator,
    MigrationCancelled,
    MigrationEntry,
    MigrationError,
    MigrationReport,
)

LOG = logging.getLogger("datasheet_studio.ui.library_upgrade")

_ENTRY_ICONS = {
    "imported": "✅",
    "duplicate": "♻️",
    "skipped": "⏭️",
    "failed": "❌",
    "ambiguous": "⚠️",
}

_ENTRY_LABELS = {
    "imported": "واردشده",
    "duplicate": "تکراری",
    "skipped": "ردشده",
    "failed": "ناموفق",
    "ambiguous": "نیازمند بازبینی",
}


class _MigrationWorker(QThread):
    """Runs the migrator off the GUI thread."""

    progressed = Signal(int, int, str)
    finished_ok = Signal(object)  # MigrationReport
    failed = Signal(str)

    def __init__(
        self,
        source_root: str,
        target_root: str,
        cancel_event: threading.Event,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source = source_root
        self._target = target_root
        self._cancel = cancel_event
        self._migrator = LibraryMigrator()

    def run(self) -> None:
        try:
            report = self._migrator.migrate(
                self._source,
                self._target,
                progress=lambda done, total, label: self.progressed.emit(
                    done, total, label
                ),
                should_cancel=self._cancel.is_set,
            )
        except MigrationCancelled:
            self.failed.emit("مهاجرت لغو شد؛ ولت ناقص حذف و کتابخانه v1 دست‌نخورده است.")
        except MigrationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - report, never crash the app
            LOG.exception("Unexpected migration failure")
            self.failed.emit(f"خطای غیرمنتظره: {exc}")
        else:
            self.finished_ok.emit(report)


class LibraryUpgradeDialog(QDialog):
    """Preview, run, review, accept or roll back the v2 upgrade."""

    def __init__(self, source_root: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ارتقای کتابخانه به نسخهٔ ۲ — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(760, 640)
        self._source_root = source_root
        self._migrator = LibraryMigrator()
        self._report: MigrationReport | None = None
        self._worker: _MigrationWorker | None = None
        self._cancel_event = threading.Event()
        self._pending_close = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        intro = QLabel(
            "کتابخانه فعلی (v1) به یک ولت دانش مهندسی (v2) با هش محتوا، رکوردهای "
            "Markdown و ایندکس جستجو ارتقا می‌یابد. فایل‌های v1 هرگز حذف یا تغییر "
            "نمی‌کنند و تا تأیید نهایی شما هر چیزی قابل بازگشت است."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            "QLabel { background: #eef4ff; color: #1c3d6e; border: 1px solid #b8cdf0;"
            " border-radius: 6px; padding: 8px; }"
        )
        root.addWidget(intro)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("کتابخانه مبدأ (v1):"))
        source_label = QLabel(source_root)
        source_label.setWordWrap(True)
        source_row.addWidget(source_label, 1)
        root.addLayout(source_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("پوشه مقصد ولت (v2):"))
        self._target_edit = QLineEdit(self._default_target())
        target_row.addWidget(self._target_edit, 1)
        browse = QPushButton("انتخاب…")
        browse.clicked.connect(self._browse_target)
        target_row.addWidget(browse)
        root.addLayout(target_row)

        self._summary_label = QLabel("برای شروع، پیش‌نمایش را بزنید.")
        self._summary_label.setWordWrap(True)
        root.addWidget(self._summary_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        root.addWidget(self._progress)

        self._report_list = QListWidget()
        self._report_list.setWordWrap(True)
        root.addWidget(self._report_list, 1)

        buttons = QHBoxLayout()
        self._preview_button = QPushButton("پیش‌نمایش")
        self._preview_button.clicked.connect(self._do_preview)
        self._start_button = QPushButton("شروع ارتقا")
        self._start_button.setEnabled(False)
        self._start_button.clicked.connect(self._start_migration)
        self._cancel_button = QPushButton("لغو")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._cancel_migration)
        self._accept_button = QPushButton("تأیید نهایی و فعال‌سازی")
        self._accept_button.setEnabled(False)
        self._accept_button.clicked.connect(self._accept_upgrade)
        self._rollback_button = QPushButton("حذف v2 و بازگشت")
        self._rollback_button.setEnabled(False)
        self._rollback_button.clicked.connect(self._rollback_upgrade)
        close_button = QPushButton("بستن")
        close_button.clicked.connect(self.accept)
        for button in (
            self._preview_button,
            self._start_button,
            self._cancel_button,
            self._accept_button,
            self._rollback_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    # -- helpers ---------------------------------------------------------------

    def _default_target(self) -> str:
        source = Path(self._source_root)
        return str(source.parent / f"{source.name}-v2")

    def _browse_target(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "انتخاب پوشه خالی برای ولت v2", self._target_edit.text()
        )
        if chosen:
            self._target_edit.setText(chosen)

    def _set_running(self, running: bool) -> None:
        self._preview_button.setEnabled(not running)
        self._start_button.setEnabled(not running and self._report is None)
        self._cancel_button.setEnabled(running)
        self._target_edit.setEnabled(not running)

    # -- steps -------------------------------------------------------------------

    def _do_preview(self) -> None:
        try:
            preview = self._migrator.preview(self._source_root)
        except Exception as exc:  # noqa: BLE001 - surface, never crash
            QMessageBox.critical(self, "پیش‌نمایش", f"خطا در خواندن کتابخانه v1:\n{exc}")
            return
        self._preview = preview
        self._summary_label.setText(
            f"اقلام: {preview.item_count} — فایل موجود: {preview.files_found} — "
            f"فایل گمشده: {preview.files_missing} — حجم قابل کپی: "
            f"{preview.total_bytes / 1_048_576:.1f} مگابایت"
        )
        self._start_button.setEnabled(True)

    def _start_migration(self) -> None:
        target = self._target_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "ارتقا", "پوشه مقصد را مشخص کنید.")
            return
        if Path(target).exists() and any(Path(target).iterdir()):
            QMessageBox.warning(
                self, "ارتقا", "پوشه مقصد باید خالی یا موجود نباشد."
            )
            return
        self._cancel_event.clear()
        self._report_list.clear()
        self._progress.setRange(0, 0)  # busy until first progress arrives
        self._set_running(True)
        self._worker = _MigrationWorker(
            self._source_root, target, self._cancel_event, self
        )
        self._worker.progressed.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_migration_finished)
        self._worker.failed.connect(self._on_migration_failed)
        self._worker.start()

    def _cancel_migration(self) -> None:
        self._cancel_event.set()
        self._summary_label.setText("در حال لغو… (پس از فایل جاری متوقف می‌شود)")

    def _on_progress(self, done: int, total: int, label: str) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(done)
        self._summary_label.setText(f"[{done}/{total}] {label}")

    def reject(self) -> None:
        """Refuse close while migration runs; cancel-and-close afterwards."""

        if self._worker is not None and self._worker.isRunning():
            self._pending_close = True
            self._cancel_event.set()
            self._summary_label.setText(
                "در حال لغو برای بستن… (پس از فایل جاری پنجره بسته می‌شود)"
            )
            return
        super().reject()

    def _maybe_finish_pending_close(self) -> None:
        if self._pending_close and (
            self._worker is None or not self._worker.isRunning()
        ):
            self._pending_close = False
            super().reject()

    def _on_migration_failed(self, message: str) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._set_running(False)
        self._start_button.setEnabled(True)
        self._summary_label.setText(message)
        QMessageBox.warning(self, "ارتقا", message)
        self._maybe_finish_pending_close()

    def _on_migration_finished(self, report: MigrationReport) -> None:
        self._report = report
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._set_running(False)
        self._start_button.setEnabled(False)
        self._accept_button.setEnabled(True)
        self._rollback_button.setEnabled(True)
        self._maybe_finish_pending_close()
        summary = " — ".join(
            f"{_ENTRY_LABELS[kind]}: {report.count(kind)}"
            for kind in ("imported", "duplicate", "ambiguous", "skipped", "failed")
        )
        self._summary_label.setText(f"ارتقا کامل شد. {summary}")
        for entry in report.entries:
            if entry.kind in ("imported",):
                continue  # keep the list focused on what needs attention
            self._add_report_row(entry)
        self._add_report_row(
            MigrationEntry(
                "imported",
                f"{report.count('imported')} فایل با موفقیت وارد شد",
                report.target_root,
            )
        )

    def _add_report_row(self, entry: MigrationEntry) -> None:
        icon = _ENTRY_ICONS.get(entry.kind, "•")
        label = _ENTRY_LABELS.get(entry.kind, entry.kind)
        text = f"{icon} [{label}] {entry.title}"
        if entry.reason:
            text += f" — {entry.reason}"
        item = QListWidgetItem(text)
        self._report_list.insertItem(0, item)

    def _accept_upgrade(self) -> None:
        if self._report is None:
            return
        answer = QMessageBox.question(
            self,
            "تأیید نهایی",
            "ولت v2 به‌عنوان کتابخانه دانش مهندسی فعال شود؟ (کتابخانه v1 دست‌نخورده باقی می‌ماند.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        from PySide6.QtCore import QSettings

        from datasheet_studio.infrastructure.storage.knowledge_vault import (
            KnowledgeVault,
        )

        # Review P1: mark the vault accepted FIRST; publish the QSettings
        # pointer only on success so it never references an unaccepted vault.
        try:
            KnowledgeVault(self._report.target_root).mark_accepted()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "تأیید نهایی", f"علامت‌گذاری ولت ناموفق بود:\n{exc}")
            return
        settings = QSettings(APP_ORGANIZATION, APP_NAME)
        settings.setValue("knowledgeBasePath", self._report.target_root)
        settings.sync()
        self._accept_button.setEnabled(False)
        self._rollback_button.setEnabled(False)
        self._summary_label.setText(
            f"ولت v2 فعال شد: {self._report.target_root} (کتابخانه v1 همچنان سالم است.)"
        )

    def _rollback_upgrade(self) -> None:
        if self._report is None:
            return
        answer = QMessageBox.question(
            self,
            "بازگشت",
            "ولت v2 کامل حذف شود؟ (به کتابخانه v1 اثری ندارد.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._migrator.rollback(self._report.target_root)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "بازگشت", f"حذف ولت ناموفق بود:\n{exc}")
            return
        from PySide6.QtCore import QSettings

        QSettings(APP_ORGANIZATION, APP_NAME).remove("knowledgeBasePath")
        self._report = None
        self._accept_button.setEnabled(False)
        self._rollback_button.setEnabled(False)
        self._start_button.setEnabled(True)
        self._summary_label.setText("ولت v2 حذف شد؛ می‌توانید دوباره شروع کنید.")
        self._report_list.clear()
