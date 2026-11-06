from collections.abc import Callable
from typing import Any

from .schemas import MCPTool

ToolHandler = Callable[[dict[str, Any]], Any]


class MCPToolRegistry:
    """Small MCP-compatible boundary for discovery and validated invocation.

    A real remote MCP transport can replace handlers without changing API or workflow code.
    """

    def __init__(self) -> None:
        self._tools: dict[str, tuple[MCPTool, ToolHandler]] = {}

    def register(self, tool: MCPTool, handler: ToolHandler) -> None:
        self._tools[tool.name] = (tool, handler)

    def discover(self) -> list[MCPTool]:
        return [tool for tool, _ in self._tools.values()]

    def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        registered = self._tools.get(name)
        if registered is None:
            raise KeyError(f"MCP tool '{name}' is not registered")
        return registered[1](arguments)

