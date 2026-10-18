"""Authentication middleware and dependency guard for FastAPI."""
import hmac
import logging
import os
import re
from typing import Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from services.auth.security import verify_session_token

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "investintel_session"

# Endpoints explicitly allowed without session authentication
EXEMPT_PATH_PATTERNS = [
    re.compile(r"^/health/?$"),
    re.compile(r"^/ready/?$"),
    re.compile(r"^/api/v1/health/?$"),
    re.compile(r"^/api/v1/ready/?$"),
    re.compile(r"^/api/v1/system/info/?$"),
    re.compile(r"^/api/v1/system/observability/?$"),
    re.compile(r"^/api/v1/auth/login/?$"),
    re.compile(r"^/api/v1/auth/logout/?$"),
    re.compile(r"^/api/v1/auth/session/?$"),
    re.compile(r"^/api/v1/auth/hash-password/?$"),
    re.compile(r"^/api/v1/system/cron/.*"),  # Separately authenticated via CRON_SECRET
    re.compile(r"^/docs/?$"),
    re.compile(r"^/redoc/?$"),
    re.compile(r"^/openapi\.json/?$"),
    re.compile(r"^/favicon\.ico/?$"),
]


def is_cloud_mode() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


def is_auth_enabled() -> bool:
    """Authentication is strictly enabled in cloud mode or when explicitly set."""
    if is_cloud_mode():
        return True
    return os.getenv("APP_AUTH_ENABLED", "false").lower() in ("1", "true", "yes")


def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    if raw.strip():
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Enforces authentication, CSRF/Origin validation, and private cache-control."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Check if path is exempt
        is_exempt = any(pattern.match(path) for pattern in EXEMPT_PATH_PATTERNS)

        # 2. Check if auth is required
        auth_required = is_auth_enabled() and not is_exempt

        if auth_required:
            secret = os.getenv("APP_AUTH_SECRET")
            # Fail closed in cloud mode if secret is missing
            if not secret:
                if is_cloud_mode():
                    logger.critical("APP_AUTH_SECRET missing in cloud mode. Failing closed.")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"detail": "Lỗi cấu hình bảo mật hệ thống.", "code": "AUTH_CONFIG_ERROR"},
                    )
                secret = "local-dev-secret-do-not-use-in-production-123456"

            # Extract session token
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()

            if not token:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Yêu cầu đăng nhập để truy cập tài nguyên này.",
                        "code": "UNAUTHORIZED",
                    },
                    headers={"WWW-Authenticate": "Cookie"},
                )

            payload = verify_session_token(token, secret)
            if not payload:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
                        "code": "SESSION_EXPIRED",
                    },
                    headers={"WWW-Authenticate": "Cookie"},
                )

            # 3. Origin / CSRF validation on state-changing requests
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                origin = request.headers.get("Origin") or request.headers.get("Referer")
                if origin:
                    # Strip path from Referer if necessary
                    from urllib.parse import urlparse
                    parsed = urlparse(origin)
                    origin_root = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                    allowed = get_allowed_origins()
                    # Also accept internal host/port
                    host_header = request.headers.get("Host", "")
                    if origin_root not in allowed and not (host_header and host_header in origin_root):
                        logger.warning(f"Blocked cross-origin request from: {origin_root}")
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={"detail": "Nguồn yêu cầu không được phép (CORS/CSRF).", "code": "FORBIDDEN_ORIGIN"},
                        )

            # Attach user info to request state
            request.state.user = payload.get("sub", "personal_investor")

        # Process request
        response: Response = await call_next(request)

        # 4. Strict Cache-Control for private APIs: NEVER let CDN or browser cache private financial data
        if not is_exempt and path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["X-Content-Type-Options"] = "nosniff"

        return response
