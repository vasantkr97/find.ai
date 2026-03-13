from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ToolValidationError
from app.core.request_context import get_request_runtime
from app.core.utils import truncate
from app.schemas.types import AppSession, ParameterDef, ToolResult
from app.services.drive.auth import is_connected
from app.services.drive.client import get_file_content, list_files, search_files
from app.tools.base import BaseTool, ToolDefinition


class DriveSearchArgs(BaseModel):
    query: str = ""
    fileId: str | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=20)


def _runtime() -> tuple[AsyncSession, AppSession] | None:
    runtime = get_request_runtime()
    if not runtime:
        return None
    db = runtime.get("db")
    session = runtime.get("session")
    if isinstance(db, AsyncSession) and isinstance(session, AppSession):
        return db, session
    return None


class DriveSearchTool(BaseTool):
    definition = ToolDefinition(
        name="drive_search",
        description=(
            "Search the user's connected Google Drive for documents. "
            "Supports pagination via offset/limit and direct file reads via fileId."
        ),
        parameters={
            "query": ParameterDef(
                type="string",
                description="Search query for Google Drive files. Use empty string to list all files.",
            ),
            "fileId": ParameterDef(
                type="string",
                description="If provided, reads this specific file's content directly.",
            ),
            "offset": ParameterDef(
                type="number",
                description="Skip the first N files in results. Use with limit to paginate.",
            ),
            "limit": ParameterDef(
                type="number",
                description="Max number of files to return per call, 1-20 (default: 10).",
            ),
        },
    )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        try:
            parsed = DriveSearchArgs.model_validate(args)
        except ValidationError as err:
            raise ToolValidationError("drive_search", str(err)) from err

        runtime = _runtime()
        if not runtime:
            return ToolResult(success=False, error="Drive search is unavailable outside request context.")
        db, session = runtime

        if not await is_connected(db, session.userId):
            return ToolResult(
                success=False,
                error="Google Drive is not connected. Ask the user to connect their Drive first.",
            )

        query = parsed.query.strip()
        if parsed.fileId:
            try:
                content = await get_file_content(db, session, parsed.fileId, "auto")
                return ToolResult(
                    success=True,
                    data={"fileId": parsed.fileId, "content": truncate(content, 8000), "fullLength": len(content)},
                )
            except Exception as err:  # noqa: BLE001
                return ToolResult(success=False, error=f"Failed to read file: {err}")

        try:
            if query:
                all_files = await search_files(db, session, query)
            else:
                all_files = []
                next_page_token: str | None = None
                while True:
                    files, next_page_token = await list_files(db, session, next_page_token)
                    all_files.extend(files)
                    if not next_page_token or len(all_files) >= 200:
                        break

            total_files = len(all_files)
            if total_files == 0:
                return ToolResult(
                    success=True,
                    data={
                        "results": [],
                        "query": query or "(all files)",
                        "totalFiles": 0,
                        "message": "No files found",
                    },
                )

            paged = all_files[parsed.offset : parsed.offset + parsed.limit]
            results = []
            for file in paged:
                try:
                    content = await get_file_content(db, session, file.id, file.mimeType)
                    results.append(
                        {
                            "fileName": file.name,
                            "fileId": file.id,
                            "mimeType": file.mimeType,
                            "content": truncate(content, 4000),
                            "modifiedTime": file.modifiedTime,
                        }
                    )
                except Exception:  # noqa: BLE001
                    results.append(
                        {"fileName": file.name, "fileId": file.id, "error": "Could not read file content"}
                    )

            return ToolResult(
                success=True,
                data={
                    "results": results,
                    "query": query or "(all files)",
                    "totalFiles": total_files,
                    "offset": parsed.offset,
                    "limit": parsed.limit,
                    "hasMore": parsed.offset + parsed.limit < total_files,
                },
            )
        except Exception as err:  # noqa: BLE001
            return ToolResult(success=False, error=f"Drive search failed: {err}")


drive_search_tool = DriveSearchTool()

