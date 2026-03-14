import time
from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()
_started_at = time.time()


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime": time.time() - _started_at,
    }


@router.get("/debug")
async def debug_env() -> dict[str, object]:
    import os

    from app.core.config import get_settings

    return {
        "cwd": os.getcwd(),
        "has_google_client": bool(get_settings().GOOGLE_CLIENT_ID),
        "google_client_value": get_settings().GOOGLE_CLIENT_ID,
    }
