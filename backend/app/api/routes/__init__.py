from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.drive import router as drive_router
from app.api.routes.health import router as health_router
from app.api.routes.history import router as history_router
from app.api.routes.share import router as share_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(agent_router, prefix="/api")
api_router.include_router(auth_router, prefix="/api")
api_router.include_router(drive_router, prefix="/api")
api_router.include_router(health_router, prefix="/api")
api_router.include_router(history_router, prefix="/api")
api_router.include_router(share_router, prefix="/api")
api_router.include_router(users_router, prefix="/api")
