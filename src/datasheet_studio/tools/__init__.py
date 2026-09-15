"""Default engineering-tool registration for Datasheet Studio."""

from .flyback_designer.tool import FlybackDesignerTool
from .registry import Tool, ToolContext, ToolRegistry
from .symbol_creator_tool import SymbolCreatorTool
from .text_coverage_tool import DocumentTextCoverageTool


def create_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SymbolCreatorTool())
    registry.register(FlybackDesignerTool())
    registry.register(DocumentTextCoverageTool())
    return registry


__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "create_default_tool_registry",
]

