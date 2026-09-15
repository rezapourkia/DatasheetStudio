"""Persian/RTL coverage dialog for page-by-page text extraction (Phase 7)."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
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

from datasheet_studio.services.text_extraction import (
    COMPLETE_STATUSES,
    ExtractionCancelled,
    ExtractionError,
    PageCoverage,
    TextExtractionService,
)

_STATUS_LABELS = {
    "pending": "در انتظار",
    "extracted": "متن استخراج شد",
    "scanned": "اسکن‌شده — نیاز به OCR",
    "ocr": "OCR انجام شد",
    "failed": "خطا",
}


class _ExtractionWorker(QThread):
    finished_coverage = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: TextExtractionService,
        pdf_path: str,
        use_ocr: bool,
        cancel_event: threading.Event,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._path = pdf_path
        self._ocr = use_ocr
        self._cancel = cancel_event

    def run(self) -> None:
        try:
            coverage = self._service.extract(
                self._path,
                use_ocr=self._ocr,
                should_cancel=self._cancel.is_set,
            )
        except ExtractionCancelled:
            self.failed.emit("استخراج لغو شد؛ وضعیت قبلی سند دست‌نخورده ماند.")
        except ExtractionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - report, never crash
            self.failed.emit(f"خطای غیرمنتظره: {exc}")
        else:
            self.finished_coverage.emit(coverage)


class ExtractionCoverageDialog(QDialog):
    """Show per-page text coverage for one PDF and run extraction."""

    def __init__(
        self,
        pdf_path: str,
        parent=None,
        *,
        service: TextExtractionService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("پوشش متن سند — Datasheet Studio")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(640, 560)
        self._pdf_path = pdf_path
        self._service = service or TextExtractionService()
        self._worker: _ExtractionWorker | None = None
        self._cancel_event = threading.Event()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QLabel(f"فایل: {pdf_path}")
        header.setWordWrap(True)
        root.addWidget(header)
        self._banner = QLabel("برای شروع، «استخراج متن» را بزنید.")
        self._banner.setWordWrap(True)
        self._banner.setStyleSheet(
            "QLabel { background: #eef4ff; color: #1c3d6e;"
            " border: 1px solid #b8cdf0; border-radius: 6px; padding: 8px; }"
        )
        root.addWidget(self._banner)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["صفحه", "وضعیت", "تعداد نویسه"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self._table, 1)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        root.addWidget(self._progress)

        buttons = QHBoxLayout()
        self._extract_button = QPushButton("استخراج متن")
        self._extract_button.clicked.connect(lambda: self._start(False))
        self._ocr_button = QPushButton("استخراج با OCR")
        self._ocr_button.setEnabled(self._service._ocr.is_available())
        self._ocr_button.setToolTip(
            "موتور OCRای متصل نیست؛ پس از انتخاب موتور در تنظیمات فعال می‌شود."
        )
        self._ocr_button.clicked.connect(lambda: self._start(True))
        self._cancel_button = QPushButton("لغو")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._cancel)
        close = QPushButton("بستن")
        close.clicked.connect(self.reject)
        buttons.addWidget(self._extract_button)
        buttons.addWidget(self._ocr_button)
        buttons.addWidget(self._cancel_button)
        buttons.addStretch()
        buttons.addWidget(close)
        root.addLayout(buttons)

    # -- running ---------------------------------------------------------------

    def _start(self, use_ocr: bool) -> None:
        self._cancel_event.clear()
        self._extract_button.setEnabled(False)
        self._ocr_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress.setRange(0, 0)
        self._banner.setText("در حال استخراج…")
        self._worker = _ExtractionWorker(
            self._service, self._pdf_path, use_ocr, self._cancel_event, self
        )
        self._worker.finished_coverage.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._banner.setText("در حال لغو… (پس از صفحهٔ جاری متوقف می‌شود)")

    def _set_idle(self) -> None:
        self._extract_button.setEnabled(True)
        self._ocr_button.setEnabled(self._service._ocr.is_available())
        self._cancel_button.setEnabled(False)
        self._progress.setRange(0, 1)

    def _on_failed(self, message: str) -> None:
        self._set_idle()
        self._banner.setText(message)
        QMessageBox.warning(self, "استخراج متن", message)

    # -- rendering ---------------------------------------------------------------

    def show_coverage(self, coverage) -> None:
        self._table.setRowCount(len(coverage.pages))
        for row, page in enumerate(coverage.pages):
            self._table.setItem(row, 0, QTableWidgetItem(str(page.page)))
            self._table.setItem(
                row, 1, QTableWidgetItem(_STATUS_LABELS.get(page.status, page.status))
            )
            self._table.setItem(row, 2, QTableWidgetItem(str(page.char_count)))
        total = coverage.page_count
        complete = coverage.count("extracted") + coverage.count("ocr")
        if coverage.is_complete:
            self._banner.setText(
                f"✅ سند کامل است — {complete} صفحه از {total} صفحه متن دارد."
            )
            self._banner.setStyleSheet(
                "QLabel { background: #e6f4ea; color: #137333;"
                " border: 1px solid #9fd3b0; border-radius: 6px; padding: 8px; }"
            )
        else:
            missing = (
                f"اسکن‌شده: {coverage.count('scanned')}"
                if coverage.count("scanned")
                else ""
            )
            failed = f"خطا: {coverage.count('failed')}" if coverage.count("failed") else ""
            pending = (
                f"در انتظار: {coverage.count('pending')}"
                if coverage.count("pending")
                else ""
            )
            details = " | ".join(part for part in (missing, failed, pending) if part)
            self._banner.setText(
                f"⚠️ سند کامل نیست — {complete} از {total} صفحه آماده است"
                + (f" ({details})" if details else "")
                + ". ادعای «سند کامل» تا حساب‌شدن همهٔ صفحات ممکن نیست."
            )
            self._banner.setStyleSheet(
                "QLabel { background: #fff4ce; color: #5c4400;"
                " border: 1px solid #e6ca6a; border-radius: 6px; padding: 8px; }"
            )

    def _on_finished(self, coverage) -> None:
        self._set_idle()
        self._progress.setValue(1)
        self.show_coverage(coverage)
