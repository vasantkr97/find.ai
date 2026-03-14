from __future__ import annotations

import asyncio
import calendar
from datetime import UTC, datetime
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]
from oauthlib.oauth2 import OAuth2Error
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import DriveAuthError
from app.core.logging import get_logger
from app.db.models import Account, User
from app.schemas.types import AppSession

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_PROVIDER = "google"
log = get_logger("drive_auth")


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


def get_auth_url() -> tuple[str, str, str | None]:
    flow = _build_flow()
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    return auth_url, state, flow.code_verifier


async def exchange_code_for_tokens(code: str, code_verifier: str | None = None) -> dict[str, Any]:
    try:
        flow = _build_flow()
        await asyncio.to_thread(flow.fetch_token, code=code, code_verifier=code_verifier)
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
    except (OAuth2Error, GoogleAuthError) as err:
        log.exception("Google OAuth exchange failed")
        raise DriveAuthError(f"Google OAuth failed: {err}") from err
    except Exception as err:  # noqa: BLE001
        log.exception("Google OAuth exchange failed")
        raise DriveAuthError("Google OAuth failed. Check backend logs for details.") from err


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
    expires_at = account.expiresAt
    if expires_at and expires_at > 10_000_000_000:
        # Legacy/alternate format: milliseconds.
        expires_at = int(expires_at / 1000)
    expiry = None
    if expires_at:
        expiry = datetime.fromtimestamp(expires_at, tz=UTC).replace(tzinfo=None)
    creds = Credentials(
        token=account.accessToken,
        refresh_token=account.refreshToken,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
        expiry=expiry,
    )
    if creds.expiry and creds.expiry.tzinfo is not None:
        creds.expiry = creds.expiry.replace(tzinfo=None)
    return creds


def _expiry_to_epoch_seconds(expiry: datetime) -> int:
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return calendar.timegm(expiry.utctimetuple())


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
    if creds.expired:
        if not creds.refresh_token:
            return None
        try:
            await asyncio.to_thread(creds.refresh, GoogleRequest())
        except GoogleAuthError:
            log.exception("Failed to refresh Google credentials")
            return None
        except Exception:  # noqa: BLE001
            log.exception("Failed to refresh Google credentials")
            return None
        if creds.expiry and creds.expiry.tzinfo is not None:
            creds.expiry = creds.expiry.replace(tzinfo=None)
        account.accessToken = creds.token
        account.refreshToken = creds.refresh_token or account.refreshToken
        account.expiresAt = _expiry_to_epoch_seconds(creds.expiry) if creds.expiry else account.expiresAt
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
