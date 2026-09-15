"""Registry contract for independently launchable engineering tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Read-only snapshot of application state made available to a tool."""

    parent: Any = None
    pdf_reader: Any = None
    pdf_info: Any = None
    selected_pages: tuple[int, ...] = ()
    ai_service: Any = None


@runtime_checkable
class Tool(Protocol):
    """Contract implemented by every registered Datasheet Studio tool."""

    id: str
    name: str
    category: str
    description: str

    def run(self, context: ToolContext) -> None:
        """Launch the tool with a current application-state snapshot."""


class DuplicateToolError(ValueError):
    """Raised when two tools use the same stable identifier."""


class ToolRegistry:
    """Store and list tools independently from the main-window menu code."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        tool_id = str(getattr(tool, "id", "")).strip()
        if not tool_id:
            raise ValueError("Tool id must be a non-empty string.")
        if tool_id in self._tools:
            raise DuplicateToolError(f"Tool id is already registered: {tool_id}")
        for field in ("name", "category", "description"):
            if not str(getattr(tool, field, "")).strip():
                raise ValueError(f"Tool {field} must be a non-empty string.")
        if not callable(getattr(tool, "run", None)):
            raise TypeError("Tool run must be callable.")
        self._tools[tool_id] = tool

    def get(self, tool_id: str) -> Tool:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {tool_id}") from exc

    def list_tools(self) -> tuple[Tool, ...]:
        return tuple(
            sorted(
                self._tools.values(),
                key=lambda tool: (
                    tool.category.casefold(),
                    tool.name.casefold(),
                    tool.id,
                ),
            )
        )

    def __len__(self) -> int:
        return len(self._tools)

