from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import ToolNotFoundError, ToolTimeoutError
from app.schemas.types import ToolResult
from app.tools.registry import get_tool_registry


def _summarize_args(args: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 100:
            output[key] = f"{value[:100]}..."
        else:
            output[key] = value
    return output


async def execute_tool(tool_name: str, args: dict[str, Any]) -> ToolResult:
    registry = get_tool_registry()
    if not registry.has(tool_name):
        available = registry.names()
        return ToolResult(success=False, data=None, error=ToolNotFoundError(tool_name, available).message)

    tool = registry.get(tool_name)
    timeout = get_settings().AGENT_STEP_TIMEOUT_MS / 1000
    start = time.time()
    try:
        result = await asyncio.wait_for(tool.execute(args), timeout=timeout)
        duration_ms = int((time.time() - start) * 1000)
        payload = result.data if isinstance(result.data, dict) else {"value": result.data}
        return ToolResult(success=result.success, data={**(payload or {}), "_meta": {"tool": tool_name, "durationMs": duration_ms}}, error=result.error)
    except TimeoutError:
        return ToolResult(success=False, data=None, error=ToolTimeoutError(tool_name, int(timeout * 1000)).message)
    except Exception as err:  # noqa: BLE001
        return ToolResult(success=False, data=None, error=f"Tool execution failed: {err}")

