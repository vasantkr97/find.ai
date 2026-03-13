from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import (
    SESSION_COOKIE_NAME,
    delete_session,
    get_session,
)
from app.db.session import get_db
from app.services.drive.auth import disconnect

router = APIRouter()


@router.get("/auth/status")
async def auth_status(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    session = await get_session(request, db)
    if not session:
        return {"authenticated": False}
    return {"authenticated": True, "email": session.user.email}


@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            session = await get_session(request, db)
            if session:
                await disconnect(db, session.userId)
            await delete_session(db, token)
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return {"success": True}
    except Exception:  # noqa: BLE001
        return {"success": False, "error": "Failed to log out"}

