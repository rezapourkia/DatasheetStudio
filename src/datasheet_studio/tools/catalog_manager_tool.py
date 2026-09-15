"""Registry entry for the catalogue pack manager (Phase 12)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class CatalogManagerTool:
    id: str = "catalog-manager"
    name: str = "مدیر کاتالوگ مغناطیسی…"
    category: str = "Knowledge Base"
    description: str = (
        "Open/preview/install/rollback manufacturer magnetics packs "
        "without any CLI use."
    )

    def run(self, context: ToolContext) -> None:
        from datasheet_studio.ui.dialogs.catalog_manager_dialog import (
            CatalogManagerDialog,
        )

        settings = QSettings(APP_ORGANIZATION, APP_NAME)
        CatalogManagerDialog(
            context.parent,
            vault_path_getter=lambda: str(
                settings.value("knowledgeBasePath", "") or ""
            ),
        ).exec()
