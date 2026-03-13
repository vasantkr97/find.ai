from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.middleware.http import install_http_middleware
from app.tools import register_default_tools

configure_logging()
settings = get_settings()

app = FastAPI(title="Archon Backend", version="0.1.0")
app.include_router(api_router)
install_http_middleware(app)

allowed_origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    register_default_tools()


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "code": exc.code, "context": exc.context},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "archon-backend"}
