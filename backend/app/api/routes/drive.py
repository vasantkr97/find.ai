import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.utils import sse_event, sse_stream_from_queue
from app.auth.session import (
    SESSION_COOKIE_NAME,
    create_session,
    require_session,
    session_cookie_options,
)
from app.core.config import get_settings
from app.core.utils import generate_id
from app.db.models import User
from app.db.session import SessionLocal, get_db
from app.schemas.types import AppSession, IngestRequest
from app.services.drive.auth import (
    exchange_code_for_tokens,
    get_auth_url,
    is_connected,
    save_tokens_for_user,
)
from app.services.drive.client import list_files
from app.services.drive.ingest import ingest_all_files
from app.services.vector.store import get_vector_store

router = APIRouter()
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_VERIFIER_COOKIE = "oauth_code_verifier"
OAUTH_COOKIE_MAX_AGE_SEC = 10 * 60


def _oauth_cookie_options() -> dict[str, object]:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.is_prod,
        "samesite": "lax",
        "path": "/api/drive/callback",
        "max_age": OAUTH_COOKIE_MAX_AGE_SEC,
    }


@router.get("/drive/auth")
async def drive_auth() -> JSONResponse:
    url, state, code_verifier = get_auth_url()
    response = JSONResponse({"url": url})
    cookie = _oauth_cookie_options()
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=cookie["httponly"],
        secure=cookie["secure"],
        samesite=cookie["samesite"],
        path=cookie["path"],
        max_age=cookie["max_age"],
    )
    if code_verifier:
        response.set_cookie(
            key=OAUTH_VERIFIER_COOKIE,
            value=code_verifier,
            httponly=cookie["httponly"],
            secure=cookie["secure"],
            samesite=cookie["samesite"],
            path=cookie["path"],
            max_age=cookie["max_age"],
        )
    return response


@router.get("/drive/callback")
async def drive_callback(
    request: Request, code: str | None = None, state: str | None = None, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    stored_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if stored_state and state and stored_state != state:
        raise HTTPException(status_code=400, detail="OAuth state mismatch")
    if stored_state and not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    code_verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE)
    payload = await exchange_code_for_tokens(code, code_verifier=code_verifier)
    email = payload["email"]
    name = payload.get("name")
    if not email:
        raise HTTPException(status_code=500, detail="OAuth callback missing email")

    row = await db.execute(select(User).where(User.email == email).limit(1))
    user = row.scalar_one_or_none()
    if not user:
        user = User(id=generate_id(), email=email, name=name)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.name = name or user.name
        await db.commit()

    await save_tokens_for_user(db, user.id, payload["tokens"])
    token = await create_session(db, user.id)

    redirect = RedirectResponse(url=f"{get_settings().app_url}/drive/callback", status_code=307)
    cookie = session_cookie_options()
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=cookie["httponly"],
        secure=cookie["secure"],
        samesite=cookie["samesite"],
        path=cookie["path"],
        max_age=cookie["max_age"],
    )
    redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/api/drive/callback")
    redirect.delete_cookie(OAUTH_VERIFIER_COOKIE, path="/api/drive/callback")
    return redirect


@router.get("/drive/status")
async def drive_status(
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    connected = await is_connected(db, session.userId)
    stats = await get_vector_store(session.userId).get_stats()
    return {"connected": connected, "email": session.user.email if connected else None, "vectorStore": stats.model_dump()}


@router.get("/drive/files")
async def drive_files(
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    connected = await is_connected(db, session.userId)
    if not connected:
        raise HTTPException(status_code=401, detail="Not connected to Google Drive")
    files, _next = await list_files(db, session)
    return {"files": [f.model_dump() for f in files]}


@router.post("/drive/ingest")
async def drive_ingest(
    body: IngestRequest,
    session: AppSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
):
    if not await is_connected(db, session.userId):
        raise HTTPException(status_code=401, detail="Not connected to Google Drive")

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run() -> None:
        async with SessionLocal() as task_db:
            try:
                def on_progress(progress):
                    queue.put_nowait(sse_event({"type": "progress", **progress.model_dump()}))

                result = await ingest_all_files(
                    task_db,
                    session,
                    on_progress=on_progress,
                    incremental=body.incremental,
                )
                queue.put_nowait(sse_event({"type": "complete", **result.model_dump()}))
            except Exception as err:  # noqa: BLE001
                queue.put_nowait(sse_event({"type": "error", "error": str(err)}))
            finally:
                queue.put_nowait(None)

    asyncio.create_task(_run())
    return sse_stream_from_queue(queue)
