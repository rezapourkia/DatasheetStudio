"""Registry entry for the document text-coverage tool (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.services.text_extraction import TextExtractionService
from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class DocumentTextCoverageTool:
    id: str = "document-text-coverage"
    name: str = "پوشش متن سند…"
    category: str = "Knowledge Base"
    description: str = (
        "Page-by-page text extraction with a coverage ledger, scanned-page "
        "detection, and page-aware search indexing for the open PDF."
    )

    def run(self, context: ToolContext) -> None:
        if context.pdf_info is None or context.pdf_reader is None:
            QMessageBox.information(
                context.parent,
                "پوشش متن سند",
                "ابتدا یک دیتاشیت باز کنید.",
            )
            return
        from datasheet_studio.ui.dialogs.extraction_coverage_dialog import (
            ExtractionCoverageDialog,
        )

        settings = QSettings()
        service = TextExtractionService(
            pdf_reader=context.pdf_reader,
            vault_path_getter=lambda: str(settings.value("knowledgeBasePath", "") or ""),
        )
        dialog = ExtractionCoverageDialog(
            context.pdf_info.path, context.parent, service=service
        )
        dialog.exec()
