from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.db.models import Account, QueryRun, Session, User
from app.db.session import get_db

router = APIRouter()


class CreateUserInput(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, min_length=1, max_length=100)
    image: HttpUrl | None = None


class UpdateUserInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    image: HttpUrl | None = None


@router.get("/users")
async def list_users(
    limit: int = Query(default=20, le=100),
    cursor: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(User).order_by(desc(User.createdAt)).limit(limit + 1)
    if cursor:
        cursor_row = await db.get(User, cursor)
        if cursor_row:
            stmt = stmt.where(User.createdAt <= cursor_row.createdAt, User.id != cursor)

    users = [row[0] for row in (await db.execute(stmt)).all()]
    has_more = len(users) > limit
    users = users[:limit]

    payload = []
    for user in users:
        runs_count = await db.scalar(select(func.count()).select_from(QueryRun).where(QueryRun.userId == user.id))
        payload.append(
            {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "image": user.image,
                "createdAt": user.createdAt,
                "_count": {"runs": int(runs_count or 0)},
            }
        )

    return {"items": payload, "nextCursor": payload[-1]["id"] if has_more and payload else None}


@router.post("/users", status_code=201)
async def create_user(body: CreateUserInput, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    exists = await db.scalar(select(func.count()).select_from(User).where(User.email == body.email))
    if exists:
        raise HTTPException(status_code=409, detail="A user with this email already exists")
    user = User(id=generate_id(), email=str(body.email), name=body.name, image=str(body.image) if body.image else None)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "image": user.image, "createdAt": user.createdAt}


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    runs = await db.scalar(select(func.count()).select_from(QueryRun).where(QueryRun.userId == user.id))
    sessions = await db.scalar(select(func.count()).select_from(Session).where(Session.userId == user.id))
    accounts = await db.scalar(select(func.count()).select_from(Account).where(Account.userId == user.id))
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "image": user.image,
        "createdAt": user.createdAt,
        "updatedAt": user.updatedAt,
        "_count": {"runs": int(runs or 0), "sessions": int(sessions or 0), "accounts": int(accounts or 0)},
    }


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: str,
    body: UpdateUserInput,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.name is not None:
        user.name = body.name
    user.image = str(body.image) if body.image else None
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "image": user.image, "updatedAt": user.updatedAt}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

