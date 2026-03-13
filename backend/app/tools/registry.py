from __future__ import annotations

from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> BaseTool:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def descriptions(self) -> str:
        lines: list[str] = []
        for tool in self._tools.values():
            params = "\n".join(
                f"    - {key} ({value.type}{', required' if value.required else ''}): {value.description}"
                for key, value in tool.definition.parameters.items()
            )
            lines.append(f"{tool.definition.name}: {tool.definition.description}\n  Parameters:\n{params}")
        return "\n\n".join(lines)


registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return registry

