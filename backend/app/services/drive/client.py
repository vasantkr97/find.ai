from __future__ import annotations

import asyncio

import googleapiclient.discovery  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DriveAuthError, DriveError
from app.schemas.types import AppSession, DriveFile
from app.services.drive.auth import require_authenticated_credentials

SUPPORTED_TYPES = [
    "application/vnd.google-apps.document",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.google-apps.spreadsheet",
]


async def _get_drive(db: AsyncSession, session: AppSession):
    creds = await require_authenticated_credentials(db, session)
    return await asyncio.to_thread(
        lambda: googleapiclient.discovery.build("drive", "v3", credentials=creds, cache_discovery=False)
    )


async def list_files(
    db: AsyncSession,
    session: AppSession,
    page_token: str | None = None,
) -> tuple[list[DriveFile], str | None]:
    try:
        drive = await _get_drive(db, session)
        mime_query = " or ".join(f"mimeType='{mime}'" for mime in SUPPORTED_TYPES)

        def _execute():
            return (
                drive.files()
                .list(
                    q=f"({mime_query}) and trashed=false",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    pageSize=100,
                    orderBy="modifiedTime desc",
                    pageToken=page_token,
                )
                .execute()
            )

        payload = await asyncio.to_thread(_execute)
        files = [DriveFile.model_validate(item) for item in payload.get("files", [])]
        return files, payload.get("nextPageToken")
    except DriveAuthError:
        raise
    except Exception as err:  # noqa: BLE001
        raise DriveError(f"Failed to list Drive files: {err}") from err


async def search_files(db: AsyncSession, session: AppSession, query: str) -> list[DriveFile]:
    try:
        drive = await _get_drive(db, session)
        safe_query = query.replace("'", "\\'")

        def _execute():
            return (
                drive.files()
                .list(
                    q=f"fullText contains '{safe_query}' and trashed=false",
                    fields="files(id, name, mimeType, modifiedTime, size)",
                    pageSize=20,
                )
                .execute()
            )

        payload = await asyncio.to_thread(_execute)
        return [DriveFile.model_validate(item) for item in payload.get("files", [])]
    except DriveAuthError:
        raise
    except Exception as err:  # noqa: BLE001
        raise DriveError(f"Failed to search Drive files: {err}") from err


def _extract_text_from_pdf(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore")
    cleaned = " ".join(text.split())
    if len(cleaned) < 50:
        return "[PDF content could not be fully extracted - binary content]"
    return cleaned


async def get_file_content(
    db: AsyncSession,
    session: AppSession,
    file_id: str,
    mime_type: str,
) -> str:
    try:
        drive = await _get_drive(db, session)
        if mime_type == "auto":
            meta = await asyncio.to_thread(
                lambda: drive.files().get(fileId=file_id, fields="mimeType").execute()
            )
            mime_type = meta.get("mimeType", "application/octet-stream")

        if mime_type == "application/vnd.google-apps.document":
            payload = await asyncio.to_thread(
                lambda: drive.files().export(fileId=file_id, mimeType="text/plain").execute()
            )
            return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)

        if mime_type == "application/vnd.google-apps.spreadsheet":
            payload = await asyncio.to_thread(
                lambda: drive.files().export(fileId=file_id, mimeType="text/csv").execute()
            )
            return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)

        if mime_type == "application/pdf":
            payload = await asyncio.to_thread(
                lambda: drive.files().get(fileId=file_id, alt="media").execute()
            )
            if isinstance(payload, bytes):
                return _extract_text_from_pdf(payload)
            if isinstance(payload, str):
                return payload
            return _extract_text_from_pdf(bytes(payload))

        payload = await asyncio.to_thread(
            lambda: drive.files().get(fileId=file_id, alt="media").execute()
        )
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="ignore")
        return str(payload)
    except DriveAuthError:
        raise
    except Exception as err:  # noqa: BLE001
        raise DriveError(f"Failed to read file {file_id}: {err}") from err
