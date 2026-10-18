"""Cryptographic security, password hashing, session tokens and login rate-limiting."""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# PBKDF2 configuration
PBKDF2_ITERATIONS = 600_000
SALT_SIZE_BYTES = 16
HASH_ALGORITHM = "sha256"

# In-memory rate limiting fallback
_MEMORY_ATTEMPTS: dict[str, list[float]] = {}
_MEMORY_LOCK = threading.Lock()
MAX_FAILED_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Generate a PBKDF2-HMAC-SHA256 hash for a password using a secure random salt."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_bytes(SALT_SIZE_BYTES)
    derived = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        logger.warning("Unrecognized password hash format.")
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])
    except (ValueError, TypeError):
        return False

    computed_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(computed_hash, expected_hash)


def _b64encode_str(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode_str(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_session_token(
    secret: str,
    expiry_seconds: int = 86400,
    user_id: str = "personal_investor",
) -> str:
    """Issue a server-signed tamper-evident session token."""
    if not secret:
        raise ValueError("APP_AUTH_SECRET must be configured to generate session tokens.")

    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expiry_seconds,
        "jti": secrets.token_hex(8),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64encode_str(payload_bytes)

    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64encode_str(signature)

    return f"{payload_b64}.{sig_b64}"


def verify_session_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    """Verify session token signature and check expiration. Returns payload dict or None."""
    if not token or not secret:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None

    payload_b64, sig_b64 = parts[0], parts[1]
    try:
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        provided_sig = _b64decode_str(sig_b64)
    except Exception:
        return None

    if not hmac.compare_digest(expected_sig, provided_sig):
        return None

    try:
        payload_bytes = _b64decode_str(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    # Check expiry
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or time.time() >= exp:
        return None

    return payload


def _get_redis_client():
    """Attempt to get redis client if REDIS_URL is configured."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis_url == "NOT_CONFIGURED":
        return None
    try:
        import redis
        client = redis.from_url(redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
        client.ping()
        return client
    except Exception:
        return None


def check_failed_login_rate_limit(ip: str) -> Tuple[bool, int]:
    """Check if the given IP has exceeded failed login rate limits.
    Returns (is_allowed, retry_after_seconds).
    """
    clean_ip = ip.strip() or "unknown_ip"
    redis_client = _get_redis_client()

    if redis_client is not None:
        try:
            key = f"auth:failed:{clean_ip}"
            count_str = redis_client.get(key)
            if count_str is not None and int(count_str) >= MAX_FAILED_ATTEMPTS:
                ttl = redis_client.ttl(key)
                return False, max(1, ttl)
            return True, 0
        except Exception as e:
            logger.warning(f"Redis rate limit check failed, falling back to memory: {e}")

    # In-memory sliding window fallback
    now = time.time()
    with _MEMORY_LOCK:
        # Purge stale entries across all IPs
        for k in list(_MEMORY_ATTEMPTS.keys()):
            _MEMORY_ATTEMPTS[k] = [t for t in _MEMORY_ATTEMPTS[k] if now - t < RATE_LIMIT_WINDOW_SECONDS]
            if not _MEMORY_ATTEMPTS[k]:
                del _MEMORY_ATTEMPTS[k]

        attempts = _MEMORY_ATTEMPTS.get(clean_ip, [])
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            oldest = attempts[0]
            retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest))
            return False, max(1, retry_after)
        return True, 0


def record_failed_login(ip: str) -> None:
    """Record a failed login attempt for the given IP."""
    clean_ip = ip.strip() or "unknown_ip"
    redis_client = _get_redis_client()

    if redis_client is not None:
        try:
            key = f"auth:failed:{clean_ip}"
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, RATE_LIMIT_WINDOW_SECONDS)
            pipe.execute()
            return
        except Exception as e:
            logger.warning(f"Redis record failed login failed, using memory: {e}")

    now = time.time()
    with _MEMORY_LOCK:
        attempts = _MEMORY_ATTEMPTS.get(clean_ip, [])
        attempts.append(now)
        _MEMORY_ATTEMPTS[clean_ip] = attempts


def reset_failed_login(ip: str) -> None:
    """Reset failed login count for an IP upon successful authentication."""
    clean_ip = ip.strip() or "unknown_ip"
    redis_client = _get_redis_client()

    if redis_client is not None:
        try:
            redis_client.delete(f"auth:failed:{clean_ip}")
        except Exception:
            pass

    with _MEMORY_LOCK:
        _MEMORY_ATTEMPTS.pop(clean_ip, None)
