"""Registry adapter for the existing datasheet Symbol Creator dialog."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QMessageBox

from .registry import ToolContext


@dataclass(frozen=True, slots=True)
class SymbolCreatorTool:
    id: str = "symbol-creator"
    name: str = "Symbol Creator…"
    category: str = "CAD"
    description: str = (
        "Extract package pin tables and export CSV or a DipTrace schematic symbol."
    )

    def run(self, context: ToolContext) -> None:
        from datasheet_studio.ui.symbol_creator import SymbolCreatorDialog

        if context.pdf_info is None or context.pdf_reader is None:
            QMessageBox.information(
                context.parent,
                "Symbol Creator",
                "Open a datasheet first.",
            )
            return
        dialog = SymbolCreatorDialog(
            context.parent,
            context.pdf_reader,
            context.pdf_info.path,
            context.pdf_info.title,
            context.ai_service,
            symbol_pages=list(context.selected_pages),
        )
        dialog.exec()

