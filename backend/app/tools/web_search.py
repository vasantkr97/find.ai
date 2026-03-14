from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.core.errors import ToolValidationError
from app.schemas.types import ParameterDef, ToolResult
from app.tools.base import BaseTool, ToolDefinition


class WebSearchArgs(BaseModel):
    query: str = Field(min_length=1)
    numResults: int = Field(default=5, ge=1, le=20)


class WebSearchTool(BaseTool):
    definition = ToolDefinition(
        name="web_search",
        description=(
            "Search the web using Google to find current information, articles, documentation, or answers."
        ),
        parameters={
            "query": ParameterDef(type="string", description="The search query", required=True),
            "numResults": ParameterDef(
                type="number", description="Number of results to return (default: 5)"
            ),
        },
    )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            parsed = WebSearchArgs.model_validate(args)
        except ValidationError as err:
            raise ToolValidationError("web_search", str(err)) from err

        cfg = get_settings()
        if not cfg.SERPER_API_KEY:
            return ToolResult(success=False, error="SERPER_API_KEY not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": cfg.SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": parsed.query, "num": parsed.numResults},
                )
            if response.status_code >= 400:
                return ToolResult(success=False, error=f"Search API error: {response.status_code}")
            payload = response.json()
            results = [
                {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet")}
                for item in payload.get("organic", [])
            ]
            answer_box = None
            if payload.get("answerBox"):
                answer_box = {
                    "answer": payload["answerBox"].get("answer") or payload["answerBox"].get("snippet"),
                    "title": payload["answerBox"].get("title"),
                }
            return ToolResult(
                success=True,
                data={"results": results, "answerBox": answer_box, "query": parsed.query},
            )
        except Exception as err:  # noqa: BLE001
            return ToolResult(success=False, error=f"Search failed: {err}")


web_search_tool = WebSearchTool()
