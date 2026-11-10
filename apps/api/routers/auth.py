"""Authentication endpoints for single-user personal investment platform."""
import logging
import os
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from services.auth.security import (
    check_failed_login_rate_limit,
    create_session_token,
    get_jwt_secret,
    hash_password,
    record_failed_login,
    reset_failed_login,
    verify_password,
    verify_session_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SESSION_COOKIE_NAME = "investintel_session"
DEFAULT_SESSION_EXPIRY = 86400  # 24 hours


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, description="Personal application password")


class HashPasswordRequest(BaseModel):
    password: str = Field(..., min_length=6, description="Plaintext password to hash for configuration")


def _get_client_ip(request: Request) -> str:
    """Extract client IP, only trusting X-Forwarded-For if explicitly enabled or from loopback."""
    client_host = request.client.host if request.client else "127.0.0.1"
    trust_proxy = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")
    is_loopback = client_host in ("127.0.0.1", "::1", "localhost")
    if (trust_proxy or is_loopback) and "X-Forwarded-For" in request.headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return client_host


def is_cloud_environment() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


def is_secure_cookie() -> bool:
    if os.getenv("COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
        return True
    if os.getenv("COOKIE_SECURE", "").lower() in ("0", "false", "no"):
        return False
    return is_cloud_environment()


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    """Authenticate single personal user and issue HttpOnly session cookie."""
    client_ip = _get_client_ip(request)

    # 1. Check rate limit
    allowed, retry_after = check_failed_login_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều lần đăng nhập không thành công. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Retrieve server secrets (fail-closed if missing or insecure)
    try:
        secret = get_jwt_secret(require_valid=True)
    except Exception as e:
        logger.critical("Authentication secrets validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cấu hình xác thực máy chủ chưa hoàn tất: Khóa bảo mật chưa được thiết lập.",
        )

    password_hash = os.getenv("APP_AUTH_PASSWORD_HASH")
    if is_cloud_environment():
        if not password_hash:
            logger.critical("Authentication password hash missing in cloud mode.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cấu hình xác thực máy chủ chưa hoàn tất.",
            )
    else:
        if not password_hash:
            dev_pw = os.getenv("APP_AUTH_PASSWORD")
            if not dev_pw:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Cấu hình mật khẩu máy chủ chưa hoàn tất. Vui lòng thiết lập APP_AUTH_PASSWORD hoặc APP_AUTH_PASSWORD_HASH.",
                )
            password_hash = hash_password(dev_pw)

    # 3. Verify password
    is_valid = verify_password(req.password, password_hash)
    if not is_valid:
        record_failed_login(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mật khẩu không chính xác.",
        )

    # 4. Password valid: reset rate limit & issue session token
    reset_failed_login(client_ip)
    expiry = int(os.getenv("APP_AUTH_EXPIRY_SECONDS", str(DEFAULT_SESSION_EXPIRY)))
    token = create_session_token(secret=secret, expiry_seconds=expiry)

    # Set secure, HttpOnly, SameSite=Strict cookie
    secure_flag = is_secure_cookie()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=expiry,
        expires=expiry,
        httponly=True,
        secure=secure_flag,
        samesite="strict",
        path="/",
    )

    return {
        "status": "authenticated",
        "message": "Đăng nhập thành công.",
        "expires_in": expiry,
        "secure": secure_flag,
    }


@router.post("/logout")
async def logout(response: Response):
    """Log out personal user by clearing session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="strict",
    )
    return {"status": "logged_out", "message": "Đã đăng xuất thành công."}


@router.get("/session")
async def get_session(request: Request):
    """Inspect current session status without leaking sensitive data."""
    secret = get_jwt_secret(require_valid=False)
    if not secret:
        return {"authenticated": False, "reason": "auth_unconfigured"}

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        # Check Authorization header bearer token as optional alternative for tools
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()

    if not token:
        return {"authenticated": False}

    payload = verify_session_token(token, secret)
    if not payload:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "expires_at": payload.get("exp"),
        "user": payload.get("sub"),
    }


@router.post("/hash-password")
async def generate_password_hash(req: HashPasswordRequest, request: Request):
    """Utility endpoint to generate a secure PBKDF2 hash for initial configuration."""
    client_ip = _get_client_ip(request)
    allowed, retry_after = check_failed_login_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều yêu cầu. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)},
        )
    hashed = hash_password(req.password)
    return {
        "password_hash": hashed,
        "algorithm": "pbkdf2_sha256",
        "iterations": 600000,
        "instructions": "Copy this string into APP_AUTH_PASSWORD_HASH in your server environment variables.",
    }
