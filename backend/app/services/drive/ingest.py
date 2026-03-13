from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import to_error_message
from app.schemas.types import AppSession, IngestError, IngestProgress
from app.services.drive.client import get_file_content, list_files
from app.services.vector.store import get_vector_store


async def ingest_all_files(
    db: AsyncSession,
    session: AppSession,
    on_progress: Callable[[IngestProgress], None] | None = None,
    incremental: bool = True,
) -> IngestProgress:
    vector_store = get_vector_store(session.userId)
    all_files = []
    page_token: str | None = None

    while True:
        files, next_page_token = await list_files(db, session, page_token)
        all_files.extend(files)
        if not next_page_token:
            break
        page_token = next_page_token

    progress = IngestProgress(total=len(all_files), processed=0, errors=[])
    for file in all_files:
        progress.current = file.name
        if on_progress:
            on_progress(progress)
        try:
            if incremental and await vector_store.has_documents_from_source(file.id):
                progress.processed += 1
                continue

            await vector_store.delete_by_source(file.id)
            content = await get_file_content(db, session, file.id, file.mimeType)
            if len(content) >= 10:
                await vector_store.ingest_text(
                    content,
                    metadata={
                        "source": "google-drive",
                        "fileId": file.id,
                        "fileName": file.name,
                        "mimeType": file.mimeType,
                        "modifiedTime": file.modifiedTime,
                    },
                )
        except Exception as err:  # noqa: BLE001
            progress.errors.append(IngestError(file=file.name, error=to_error_message(err)))
        finally:
            progress.processed += 1
            if on_progress:
                on_progress(progress)

    progress.current = None
    return progress

