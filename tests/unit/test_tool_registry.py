"""Tests for the application engineering-tool registry."""

from dataclasses import dataclass

import pytest

from datasheet_studio.tools.registry import (
    DuplicateToolError,
    ToolContext,
    ToolRegistry,
)


@dataclass
class StubTool:
    id: str
    name: str
    category: str
    description: str = "test tool"
    runs: int = 0

    def run(self, context: ToolContext) -> None:
        self.runs += 1


def test_registry_orders_tools_by_category_then_name():
    registry = ToolRegistry()
    registry.register(StubTool("z", "Zulu", "Power"))
    registry.register(StubTool("a", "Alpha", "CAD"))
    registry.register(StubTool("b", "Beta", "Power"))

    assert [tool.id for tool in registry.list_tools()] == ["a", "b", "z"]
    assert registry.get("b").name == "Beta"


def test_registry_rejects_duplicate_ids():
    registry = ToolRegistry()
    registry.register(StubTool("same", "First", "Test"))

    with pytest.raises(DuplicateToolError):
        registry.register(StubTool("same", "Second", "Test"))


@pytest.mark.parametrize("field", ["id", "name", "category", "description"])
def test_registry_rejects_blank_required_metadata(field):
    values = {
        "id": "valid",
        "name": "Valid",
        "category": "Test",
        "description": "Valid description",
    }
    values[field] = "  "

    with pytest.raises(ValueError):
        ToolRegistry().register(StubTool(**values))

