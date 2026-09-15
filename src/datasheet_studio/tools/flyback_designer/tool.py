"""Registry entry for the native Flyback Designer."""

from __future__ import annotations

from dataclasses import dataclass

from datasheet_studio.tools.registry import ToolContext


@dataclass(frozen=True, slots=True)
class FlybackDesignerTool:
    id: str = "flyback-designer"
    name: str = "طراح فلای‌بک…"
    category: str = "Power Design"
    description: str = "Native Persian DCM flyback pre-design and transformer calculator."

    def run(self, context: ToolContext) -> None:
        from .dialog import FlybackDesignerDialog

        FlybackDesignerDialog(context.parent).exec()

