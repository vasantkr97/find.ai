from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.errors import ToolValidationError
from app.core.request_context import get_request_user_id
from app.schemas.types import ParameterDef, ToolResult
from app.services.vector.store import get_vector_store
from app.tools.base import BaseTool, ToolDefinition


class VectorSearchArgs(BaseModel):
    query: str = Field(min_length=1)
    topK: int = Field(default=5, ge=1, le=20)


class VectorSearchTool(BaseTool):
    definition = ToolDefinition(
        name="vector_search",
        description=(
            "Search through ingested Google Drive documents using semantic similarity."
        ),
        parameters={
            "query": ParameterDef(type="string", description="The semantic search query", required=True),
            "topK": ParameterDef(type="number", description="Number of results to return (default: 5)"),
        },
    )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            parsed = VectorSearchArgs.model_validate(args)
        except ValidationError as err:
            raise ToolValidationError("vector_search", str(err)) from err

        user_id = get_request_user_id()
        if not user_id:
            return ToolResult(
                success=False,
                error="Not authenticated. Vector search is only available for signed-in users.",
            )

        try:
            store = get_vector_store(user_id)
            results = await store.search(parsed.query, top_k=parsed.topK)
            if not results:
                return ToolResult(
                    success=True,
                    data={
                        "results": [],
                        "query": parsed.query,
                        "message": "No relevant documents found. Drive files may not be ingested yet.",
                    },
                )

            formatted = [
                {
                    "content": row.document.content,
                    "score": round(row.score, 2),
                    "source": row.document.metadata.get("fileName")
                    or row.document.metadata.get("source")
                    or "unknown",
                    "fileId": row.document.metadata.get("fileId"),
                    "chunkIndex": row.document.metadata.get("chunkIndex"),
                }
                for row in results
            ]
            return ToolResult(success=True, data={"results": formatted, "query": parsed.query})
        except Exception as err:  # noqa: BLE001
            return ToolResult(success=False, error=f"Vector search failed: {err}")


vector_search_tool = VectorSearchTool()

