from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.schemas.types import ParameterDef, ToolResult


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, ParameterDef]


class BaseTool(ABC):
    definition: ToolDefinition

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

