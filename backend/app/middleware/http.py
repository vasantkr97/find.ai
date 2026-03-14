import time
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rate_limit import check_rate_limit, rate_limit_headers
from app.core.request_context import request_id_var
from app.core.utils import generate_id

log = get_logger("http")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Request-Id",
    "Access-Control-Max-Age": "86400",
}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def install_http_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def http_middleware(request: Request, call_next: Callable):
        request_id = request.headers.get("x-request-id") or generate_id()
        request.state.request_id = request_id
        token = request_id_var.set(request_id)

        path = request.url.path
        method = request.method
        ip = _client_ip(request)
        start = time.time()

        log.info(
            "API request",
            extra={
                "context": {
                    "requestId": request_id,
                    "method": method,
                    "path": path,
                    "ip": ip,
                }
            },
        )

        rl_headers: dict[str, str] = {}
        cfg = get_settings()
        if (
            cfg.RATE_LIMIT_ENABLED
            and path.startswith("/api/")
            and path != "/api/health"
            and method != "OPTIONS"
        ):
            rl_result = check_rate_limit(ip)
            rl_headers = rate_limit_headers(rl_result)
            if not rl_result.allowed:
                duration_ms = int((time.time() - start) * 1000)
                response = JSONResponse(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status_code=429,
                )
                response.headers["X-Request-Id"] = request_id
                for key, value in rl_headers.items():
                    response.headers[key] = value
                for key, value in SECURITY_HEADERS.items():
                    response.headers[key] = value
                log.info(
                    "API response",
                    extra={
                        "context": {
                            "requestId": request_id,
                            "status": 429,
                            "durationMs": duration_ms,
                        }
                    },
                )
                request_id_var.reset(token)
                return response

        try:
            response = await call_next(request)
        except Exception as err:  # noqa: BLE001
            if isinstance(err, (HTTPException, AppError)):
                raise
            duration_ms = int((time.time() - start) * 1000)
            response = JSONResponse({"error": "Internal server error"}, status_code=500)
            log.exception(
                "API handler failed",
                extra={
                    "context": {
                        "requestId": request_id,
                        "path": path,
                        "durationMs": duration_ms,
                    }
                },
            )

        duration_ms = int((time.time() - start) * 1000)
        response.headers["X-Request-Id"] = request_id
        for key, value in rl_headers.items():
            response.headers[key] = value
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value

        log.info(
            "API response",
            extra={
                "context": {
                    "requestId": request_id,
                    "status": response.status_code,
                    "durationMs": duration_ms,
                }
            },
        )

        request_id_var.reset(token)
        return response
