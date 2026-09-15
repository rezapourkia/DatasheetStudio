"""Registry entry for the controller profile form (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from datasheet_studio.core.constants import APP_NAME, APP_ORGANIZATION
from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class ControllerProfileTool:
    id: str = "controller-profile"
    name: str = "پروفایل کنترلر…"
    category: str = "Knowledge Base"
    description: str = (
        "Edit and review the strict controller IC profile (limits, timing, "
        "switch, protection, feedback) with per-field evidence."
    )

    def run(self, context: ToolContext) -> None:
        from datasheet_studio.ui.dialogs.controller_profile_dialog import (
            ControllerProfileDialog,
        )

        part_number = ""
        manufacturer = ""
        if context.pdf_info is not None:
            stem = Path(context.pdf_info.path).stem
            match = re.match(r"^([A-Za-z]{2,6})[-_ ]?(\d{2,6}[A-Za-z0-9]*)", stem)
            if match:
                manufacturer, part_number = match.group(1), match.group(2)
            else:
                part_number = stem
        settings = QSettings(APP_ORGANIZATION, APP_NAME)
        dialog = ControllerProfileDialog(
            context.parent,
            part_number=part_number,
            manufacturer=manufacturer,
            vault_path_getter=lambda: str(
                settings.value("knowledgeBasePath", "") or ""
            ),
        )
        dialog.exec()

