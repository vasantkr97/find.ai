import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Session, User
from app.db.session import get_db
from app.schemas.types import AppSession, SessionUser

SESSION_COOKIE_NAME = "auth_token"
SESSION_MAX_AGE_SEC = 60 * 60 * 24 * 7


class SessionCookieOptions(TypedDict):
    httponly: bool
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str
    max_age: int


def _session_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(seconds=SESSION_MAX_AGE_SEC)


def generate_token() -> str:
    return secrets.token_hex(32)


async def create_session(db: AsyncSession, user_id: str) -> str:
    token = generate_token()
    db.add(Session(id=secrets.token_hex(12), userId=user_id, token=token, expiresAt=_session_expires_at()))
    await db.commit()
    return token


def session_cookie_options() -> SessionCookieOptions:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.is_prod,
        "samesite": "lax",
        "path": "/",
        "max_age": SESSION_MAX_AGE_SEC,
    }


async def get_session(request: Request, db: AsyncSession) -> AppSession | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    stmt = (
        select(Session, User)
        .join(User, Session.userId == User.id)
        .where(Session.token == token)
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        return None
    session_row, user = row

    now = datetime.now(UTC)
    expires_at = session_row.expiresAt
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        await db.execute(delete(Session).where(Session.id == session_row.id))
        await db.commit()
        return None

    return AppSession(
        userId=session_row.userId,
        user=SessionUser(id=user.id, email=user.email, name=user.name),
    )


async def require_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AppSession:
    session = await get_session(request, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return session


async def delete_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(Session).where(Session.token == token))
    await db.commit()
