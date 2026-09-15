"""Registry entry for the AI profile-extraction review tool (Phase 9)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class AiProfileExtractionTool:
    id: str = "ai-profile-extraction"
    name: str = "استخراج پروفایل با AI…"
    category: str = "Knowledge Base"
    description: str = (
        "Consent-gated AI extraction of the controller profile with a "
        "per-field review diff; only accepted fields reach the profile."
    )

    def run(self, context: ToolContext) -> None:
        if context.pdf_info is None or context.pdf_reader is None:
            QMessageBox.information(
                context.parent, "استخراج با AI", "ابتدا یک دیتاشیت باز کنید."
            )
            return
        from datasheet_studio.ui.dialogs.ai_extraction_review_dialog import (
            AiExtractionReviewDialog,
        )

        settings = QSettings()

        def chat(prompt: str) -> str:
            if context.ai_service is None:
                raise RuntimeError("سرویس AI در دسترس نیست.")
            reply = context.ai_service.chat(
                [{"role": "user", "content": prompt}],
                provider=str(settings.value("ai/provider", "deepseek") or "deepseek"),
            )
            if isinstance(reply, dict):
                reply = reply.get("content", "")
            return str(reply)

        dialog = AiExtractionReviewDialog(
            context.parent,
            pdf_path=context.pdf_info.path,
            ai_chat=chat,
            vault_path_getter=lambda: str(
                settings.value("knowledgeBasePath", "") or ""
            ),
            provider=str(settings.value("ai/provider", "") or ""),
            model=str(settings.value("ai/model", "") or ""),
        )
        dialog.exec()
