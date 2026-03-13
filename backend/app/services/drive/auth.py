from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import DriveAuthError
from app.db.models import Account, User
from app.schemas.types import AppSession

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_PROVIDER = "google"


def _oauth_client_config() -> dict[str, Any]:
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise DriveAuthError("Google OAuth credentials are not configured")
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.redirect_uri],
        }
    }


def _build_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        _oauth_client_config(),
        scopes=SCOPES,
        redirect_uri=get_settings().redirect_uri,
        state=state,
    )
    return flow


def get_auth_url() -> str:
    flow = _build_flow()
    auth_url, _state = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    flow = _build_flow()
    await asyncio.to_thread(flow.fetch_token, code=code)
    creds = flow.credentials

    import googleapiclient.discovery as google_discovery  # type: ignore[import-untyped]

    oauth2 = google_discovery.build("oauth2", "v2", credentials=creds, cache_discovery=False)
    profile = await asyncio.to_thread(lambda: oauth2.userinfo().get().execute())
    return {
        "tokens": {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expiry_date": int(creds.expiry.timestamp() * 1000) if creds.expiry else None,
        },
        "email": profile.get("email", ""),
        "name": profile.get("name"),
    }


async def save_tokens_for_user(db: AsyncSession, user_id: str, tokens: dict[str, Any]) -> None:
    expires_at = int(tokens["expiry_date"] / 1000) if tokens.get("expiry_date") else None
    user = await db.get(User, user_id)
    if not user:
        return

    existing = await db.execute(
        select(Account).where(
            Account.provider == GOOGLE_PROVIDER,
            Account.providerAccountId == user.email,
        )
    )
    account = existing.scalar_one_or_none()
    if account:
        account.accessToken = tokens.get("access_token") or account.accessToken
        account.refreshToken = tokens.get("refresh_token") or account.refreshToken
        account.expiresAt = expires_at
    else:
        db.add(
            Account(
                id=f"acc_{user.id}",
                userId=user.id,
                provider=GOOGLE_PROVIDER,
                providerAccountId=user.email,
                accessToken=tokens.get("access_token"),
                refreshToken=tokens.get("refresh_token"),
                expiresAt=expires_at,
            )
        )
    await db.commit()


def _credentials_from_account(account: Account) -> Credentials:
    settings = get_settings()
    creds = Credentials(
        token=account.accessToken,
        refresh_token=account.refreshToken,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
        expiry=datetime.fromtimestamp(account.expiresAt, tz=UTC) if account.expiresAt else None,
    )
    return creds


async def get_authenticated_credentials(
    db: AsyncSession,
    user_id: str,
) -> Credentials | None:
    row = await db.execute(
        select(Account).where(Account.userId == user_id, Account.provider == GOOGLE_PROVIDER).limit(1)
    )
    account = row.scalar_one_or_none()
    if not account:
        return None
    if not account.accessToken and not account.refreshToken:
        return None

    creds = _credentials_from_account(account)
    if creds.expired and creds.refresh_token:
        await asyncio.to_thread(creds.refresh, GoogleRequest())
        account.accessToken = creds.token
        account.refreshToken = creds.refresh_token or account.refreshToken
        account.expiresAt = int(creds.expiry.timestamp()) if creds.expiry else account.expiresAt
        await db.commit()
    return creds


async def is_connected(db: AsyncSession, user_id: str) -> bool:
    creds = await get_authenticated_credentials(db, user_id)
    return creds is not None


async def disconnect(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        delete(Account).where(Account.userId == user_id, Account.provider == GOOGLE_PROVIDER)
    )
    await db.commit()


async def require_authenticated_credentials(db: AsyncSession, session: AppSession) -> Credentials:
    creds = await get_authenticated_credentials(db, session.userId)
    if not creds:
        raise DriveAuthError()
    return creds
