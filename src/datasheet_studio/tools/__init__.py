"""Default engineering-tool registration for Datasheet Studio."""

from .flyback_designer.tool import FlybackDesignerTool
from .registry import Tool, ToolContext, ToolRegistry
from .symbol_creator_tool import SymbolCreatorTool
from .text_coverage_tool import DocumentTextCoverageTool
from .controller_profile_tool import ControllerProfileTool
from .ai_extraction_tool import AiProfileExtractionTool


def create_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(SymbolCreatorTool())
    registry.register(FlybackDesignerTool())
    registry.register(DocumentTextCoverageTool())
    registry.register(ControllerProfileTool())
    registry.register(AiProfileExtractionTool())
    return registry


__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "create_default_tool_registry",
]

