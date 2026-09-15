"""Persian/RTL AI extraction review dialog (Phase 9).

Explicit consent gate (sending document text to the AI provider is a
checkbox, never automatic), cancellable run, per-field accept diff, and
acceptance-only profile creation. Runs on a worker thread.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from datasheet_studio.models.controller_profile import FIELD_SPECS
from datasheet_studio.services.controller_extraction import (
    ExtractionRunError,
    archive_run,
    run_extraction,
)
from datasheet_studio.services.knowledge_hash import sha256_file
from datasheet_studio.services.text_extraction import TextExtractionService


class _AiWorker(QThread):
    done = Signal(object)  # CompleteExtraction
    failed = Signal(str)

    def __init__(self, chat, part_number, page_texts, complete_pages,
                 page_count, source_hash, archive_root, cancel_event, parent=None):
        super().__init__(parent)
        self._chat = chat
        self._part = part_number
        self._texts = page_texts
        self._complete_pages = tuple(complete_pages)
        self._count = page_count
        self._hash = source_hash
        self._archive = archive_root
        self._cancel = cancel_event

    def run(self):
        from datasheet_studio.services.controller_extraction import extract_complete

        try:
            outcome = extract_complete(
                self._chat,
                part_number=self._part,
                page_texts=self._texts,
                complete_pages=self._complete_pages,
                page_count=self._count,
                source_hash=self._hash,
                archive_root=self._archive,
                should_cancel=self._cancel.is_set,
            )
        except ExtractionRunError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"خطای غیرمنتظره: {exc}")
        else:
            self.done.emit(outcome)


class AiExtractionReviewDialog(QDialog):
    """Consent → run → review diff → accept selected fields."""

    def __init__(
        self,
        parent=None,
        *,
        pdf_path: str,
        ai_chat=None,
        vault_path_getter=None,
        provider: str = "",
        model: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("استخراج پروفایل با AI — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(900, 640)
        self._pdf_path = pdf_path
        self._chat = ai_chat
        self._vault_path_getter = vault_path_getter or (lambda: "")
        self._provider = provider
        self._model = model
        self._worker: _AiWorker | None = None
        self._cancel_event = threading.Event()
        self._result = None
        self._source_hash = ""
        self._request_text = ""
        self._response_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._consent = QCheckBox(
            "می‌دانم متن این دیتاشیت برای ارائه‌دهندهٔ AI ارسال می‌شود و با ارسال موافقم."
        )
        root.addWidget(self._consent)
        self._run_button = QPushButton("ارسال برای استخراج")
        self._run_button.setEnabled(False)
        self._consent.toggled.connect(lambda checked: self._run_button.setEnabled(bool(checked and self._chat)))
        self._run_button.clicked.connect(self._start)
        self._retry_button = QPushButton("تلاش دوباره")
        self._retry_button.clicked.connect(self._start)
        self._retry_button.hide()
        self._cancel_button = QPushButton("لغو")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._cancel_event.set)
        self._accept_button = QPushButton("پذیرش انتخاب‌شده‌ها و ذخیره پروفایل")
        self._accept_button.setEnabled(False)
        self._accept_button.clicked.connect(self._accept)
        close = QPushButton("بستن")
        close.clicked.connect(self.reject)

        controls = QHBoxLayout()
        controls.addWidget(self._run_button)
        controls.addWidget(self._retry_button)
        controls.addWidget(self._cancel_button)
        controls.addStretch()
        controls.addWidget(self._accept_button)
        controls.addWidget(close)
        root.addLayout(controls)

        self._status = QLabel("برای ارسال، ابتدا تأیید رضایت را علامت بزنید.")
        self._status.setWordWrap(True)
        root.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        root.addWidget(self._progress)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["پذیرش", "فیلد", "مقدار (واحد)", "صفحه", "مسئله"]
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

    # -- run --------------------------------------------------------------------

    def _start(self):
        if self._chat is None:
            QMessageBox.information(
                self, "AI", "ابتدا تنظیمات AI را در پنل هوش مصنوعی پیکربندی کنید."
            )
            return
        self._cancel_event.clear()
        self._run_button.setEnabled(False)
        self._retry_button.hide()
        self._cancel_button.setEnabled(True)
        self._progress.show()
        self._status.setText("در حال آماده‌سازی متن صفحات و ارسال…")

        def prepare():
            service = TextExtractionService(
                vault_path_getter=self._vault_path_getter
            )
            coverage = service.extract(self._pdf_path)
            texts = service._cached_page_texts(coverage.source_hash)
            return coverage, texts

        class _Prep(QThread):
            ready = Signal(object, object)
            failed = Signal(str)

            def run(self_inner):
                try:
                    coverage, texts = prepare()
                except Exception as exc:  # noqa: BLE001
                    self_inner.failed.emit(str(exc))
                else:
                    self_inner.ready.emit(coverage, texts)

        self._prep = _Prep(self)

        def _ready(coverage, texts):
            self._source_hash = coverage.source_hash
            from datasheet_studio.services.text_extraction import COMPLETE_STATUSES

            complete_pages = tuple(
                page.page for page in coverage.pages
                if page.status in COMPLETE_STATUSES and page.page in texts
            )
            archive_root = None
            vault_path = (self._vault_path_getter() or "").strip()
            if vault_path:
                from pathlib import Path as _P

                archive_root = _P(vault_path) / "ai-runs"
            self._worker = _AiWorker(
                self._chat,
                Path_stem(self._pdf_path),
                texts,
                complete_pages,
                coverage.page_count,
                coverage.source_hash,
                archive_root,
                self._cancel_event,
                self,
            )
            self._worker.done.connect(self._on_done)
            self._worker.failed.connect(self._on_failed)
            self._worker.start()

        def _prep_failed(message):
            self._on_failed(message)

        self._prep.ready.connect(_ready)
        self._prep.failed.connect(_prep_failed)
        self._prep.start()

    def _on_failed(self, message: str):
        self._progress.hide()
        self._cancel_button.setEnabled(False)
        self._retry_button.show()
        self._run_button.setEnabled(self._consent.isChecked())
        self._status.setText(message)

    # -- review -------------------------------------------------------------------

    def _on_done(self, outcome):
        result = outcome.result
        self._result = result
        self._request_text = ""  # archived per-chunk by extract_complete
        self._response_text = ""
        if outcome.omitted_pages:
            shown = "، ".join(map(str, outcome.omitted_pages[:12]))
            self._status.setText(
                "⚠️ استخراج «کامل» نیست — صفحات حساب‌نشده: " + shown
                + ("…" if len(outcome.omitted_pages) > 12 else "")
                + " (برای این صفحات ابتدا پوشش متن را کامل کنید.)"
            )
        self._progress.hide()
        self._cancel_button.setEnabled(False)
        self._retry_button.show()
        self._run_button.setEnabled(self._consent.isChecked())
        if not result.ok:
            self._status.setText(
                "پاسخ AI قابل استفاده نیست: "
                + "؛ ".join(i.message for i in result.issues[:3])
            )
            return
        issues_by_field = {i.field_name: i.message for i in result.issues if i.field_name}
        self._table.setRowCount(len(result.candidate_fields))
        for row, item in enumerate(result.candidate_fields):
            spec = FIELD_SPECS[item["name"]]
            check = QCheckBox()
            check.setChecked(not issues_by_field.get(item["name"]))
            container = QWidget()
            box = QHBoxLayout(container)
            box.addWidget(check)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, container)
            self._table.setItem(row, 1, QTableWidgetItem(f"{spec.label_fa} ({item['name']})"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{item.get('value')!s} {spec.unit}".strip()))
            self._table.setItem(row, 3, QTableWidgetItem(str(item.get("page", "—"))))
            self._table.setItem(
                row, 4, QTableWidgetItem(issues_by_field.get(item["name"], ""))
            )
            result.candidate_fields[row]["_checkbox"] = check
        self._status.setText(
            f"{len(result.candidate_fields)} فیلد کاندید دریافت شد — موارد مشکل‌دار علامت نخورده‌اند. "
            "فقط فیلدهای تیک‌خورده وارد پروفایل می‌شوند (با وضعیت «استخراج‌شده»)."
        )
        self._accept_button.setEnabled(bool(result.candidate_fields))

    def _accept(self):
        if self._result is None:
            return
        from datasheet_studio.services.controller_extraction import accepted_profile

        accepted = {
            item["name"]
            for item in self._result.candidate_fields
            if item.get("_checkbox") is not None and item["_checkbox"].isChecked()
        }
        if not accepted:
            QMessageBox.information(self, "پذیرش", "هیچ فیلدی انتخاب نشده است.")
            return
        try:
            profile = accepted_profile(
                self._result,
                accepted_names=accepted,
                source_hash=self._source_hash or sha256_file(self._pdf_path),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "پذیرش", str(exc))
            return
        saved = None
        vault_path = (self._vault_path_getter() or "").strip()
        if vault_path:
            from datasheet_studio.infrastructure.storage.knowledge_vault import (
                KnowledgeVault,
            )

            try:
                saved = KnowledgeVault(vault_path).write_controller_profile(profile)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "ذخیره پروفایل", str(exc))
                return
        archive_run(
            self._vault_path_getter,
            run_id=self._result.run_id,
            request_text=self._request_text,
            response_text=self._response_text,
            result=self._result,
            source_hash=self._source_hash,
            provider=self._provider,
            model=self._model,
        )
        where = f"در ولت: {saved}" if saved else "پروفایل AI بدون ولت ذخیره نشد (ولتی فعال نیست)."
        self._status.setText(
            f"✅ {len(accepted)} فیلد پذیرفته و با وضعیت «استخراج‌شده» ذخیره شد {where}"
        )
        self._accept_button.setEnabled(False)


def Path_stem(path: str) -> str:
    from pathlib import Path as _P

    return _P(path).stem
