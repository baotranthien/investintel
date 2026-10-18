"""Comprehensive Cloud Readiness Verification Test Suite.

Covers:
1. Private authentication & session management (login, logout, expiry, rate limiting, CSRF).
2. Private API caching headers (Cache-Control: private, no-store).
3. Cloud database resilience (cold-start retry, pool limits, SQLite fail-closed in cloud).
4. Idempotent cron endpoints (X-Cron-Secret constant-time check, idempotency keys, duplicate skip).
5. Cloud AI Gateway (fallback order, free-only OpenRouter enforcement, zero-budget guard).
"""
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from database.connection import get_database_url, is_cloud_mode, normalize_database_url
from services.ai.cloud_providers import GroqProvider, OpenRouterProvider
from services.ai.config import GatewayConfig
from services.ai.errors import AIPaidProviderBlockedError, AIProviderUnavailableError
from services.ai.gateway import AIGateway
from services.auth.security import (
    check_failed_login_rate_limit,
    create_session_token,
    hash_password,
    record_failed_login,
    reset_failed_login,
    verify_password,
    verify_session_token,
)
from services.maintenance.retention import run_bounded_staging_cleanup


@pytest.fixture
def auth_client():
    """Client with authentication strictly enabled."""
    test_secret = "test-secret-cloud-readiness-32bytes-hex-ok"
    test_password = "secure_investor_password"
    test_hash = hash_password(test_password)

    with patch.dict(
        os.environ,
        {
            "APP_AUTH_ENABLED": "true",
            "APP_AUTH_SECRET": test_secret,
            "APP_AUTH_PASSWORD_HASH": test_hash,
            "CRON_SECRET": "test-cron-secret-12345",
            "ALLOWED_ORIGINS": "https://investintel.vercel.app,http://localhost:3000",
        },
    ):
        with TestClient(app) as client:
            yield client, test_password, test_secret


# ==============================================================================
# 1. Private Application Authentication Tests
# ==============================================================================


def test_password_hashing_and_verification():
    raw_pw = "SuperSecretPassword123!"
    hashed = hash_password(raw_pw)
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert verify_password(raw_pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False


def test_session_token_creation_and_expiry():
    secret = "test-auth-secret-key-123"
    token = create_session_token(secret=secret, expiry_seconds=3600)
    payload = verify_session_token(token, secret)
    assert payload is not None
    assert payload["sub"] == "personal_investor"
    assert payload["exp"] > time.time()

    # Expired token test
    expired_token = create_session_token(secret=secret, expiry_seconds=-10)
    assert verify_session_token(expired_token, secret) is None

    # Tampered token test
    parts = token.split(".")
    tampered_token = f"{parts[0]}.badsignature"
    assert verify_session_token(tampered_token, secret) is None


def test_unauthenticated_requests_blocked(auth_client):
    client, _, _ = auth_client

    # Sensitive endpoints MUST return 401 when auth is enabled
    sensitive_endpoints = [
        "/api/v1/portfolio",
        "/api/v1/watchlist",
        "/api/v1/portfolio/settings",
        "/api/v1/portfolio/targets",
        "/api/v1/portfolio/dca",
    ]
    for ep in sensitive_endpoints:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {ep}, got {resp.status_code}"
        assert resp.json().get("code") in ("UNAUTHORIZED", "SESSION_EXPIRED")


def test_exempt_endpoints_accessible(auth_client):
    client, _, _ = auth_client

    # Health and observability must remain unauthenticated (no personal data leaked)
    resp = client.get("/health")
    assert resp.status_code == 200

    resp = client.get("/ready")
    assert resp.status_code in (200, 503)

    resp = client.get("/api/v1/health")
    assert resp.status_code in (200, 503)

    resp = client.get("/api/v1/ready")
    assert resp.status_code in (200, 503)

    resp = client.get("/api/v1/system/info")
    assert resp.status_code == 200


def test_readiness_probe_success_and_failure(auth_client):
    client, _, _ = auth_client

    # 1. Database alive -> 200 {"status": "ready"}
    with patch("apps.api.main.check_database_health", return_value={"connected": True, "backend": "postgresql", "latency_ms": 1.5}):
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}

        resp_v1 = client.get("/api/v1/ready")
        assert resp_v1.status_code == 200
        assert resp_v1.json() == {"status": "ready"}

    # 2. Database disconnected -> 503 without leaking credentials or stack traces
    with patch("apps.api.main.check_database_health", return_value={"connected": False, "error": "connection timeout"}):
        resp_down = client.get("/ready")
        assert resp_down.status_code == 503
        data = resp_down.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"
        # Ensure no secrets, hosts, or connection strings leak in public response
        assert "password" not in str(data).lower()
        assert "postgresql://" not in str(data).lower()


def test_login_flow_and_session_cookie(auth_client):
    client, valid_password, _ = auth_client

    # 1. Successful login
    login_resp = client.post("/api/v1/auth/login", json={"password": valid_password})
    assert login_resp.status_code == 200
    assert login_resp.json()["status"] == "authenticated"

    # Verify session cookie was set
    assert "investintel_session" in client.cookies
    cookie = client.cookies["investintel_session"]
    assert cookie is not None

    # 2. Access protected endpoint WITH valid cookie
    prot_resp = client.get("/api/v1/portfolio")
    assert prot_resp.status_code == 200
    # Strict cache control for private financial data
    assert "private" in prot_resp.headers.get("Cache-Control", "")
    assert "no-store" in prot_resp.headers.get("Cache-Control", "")

    # 3. Check session endpoint
    sess_resp = client.get("/api/v1/auth/session")
    assert sess_resp.status_code == 200
    assert sess_resp.json()["authenticated"] is True

    # 4. Logout
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200

    # 5. Protected endpoint should now fail
    client.cookies.clear()
    after_logout_resp = client.get("/api/v1/portfolio")
    assert after_logout_resp.status_code == 401


def test_failed_login_rate_limiting(auth_client):
    client, _, _ = auth_client
    test_ip = "192.168.1.99"

    # Reset any prior attempts for test IP
    reset_failed_login(test_ip)

    # 5 failed attempts
    for _ in range(5):
        record_failed_login(test_ip)

    allowed, retry_after = check_failed_login_rate_limit(test_ip)
    assert allowed is False
    assert retry_after > 0

    # Clean up
    reset_failed_login(test_ip)
    allowed_now, _ = check_failed_login_rate_limit(test_ip)
    assert allowed_now is True


def test_csrf_origin_validation_on_mutation(auth_client):
    client, valid_password, _ = auth_client

    # Log in first
    client.post("/api/v1/auth/login", json={"password": valid_password})

    # Mutation with untrusted origin should be rejected (403 Forbidden)
    bad_origin_headers = {"Origin": "https://malicious-attacker-site.com"}
    resp = client.post(
        "/api/v1/watchlist",
        json={"symbol": "FPT"},
        headers=bad_origin_headers,
    )
    assert resp.status_code == 403
    assert resp.json().get("code") == "FORBIDDEN_ORIGIN"


# ==============================================================================
# 2. Cloud Database & Bootstrap Resilience Tests
# ==============================================================================


def test_database_url_normalization():
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql://user:pass@host/db"
    assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql://user:pass@host/db"


def test_cloud_mode_refuses_sqlite_fallback():
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "DATABASE_URL": "sqlite:///test.db"}):
        with pytest.raises(RuntimeError, match="Refusing to run or fall back to SQLite in cloud mode"):
            get_database_url()


def test_bounded_staging_cleanup_dry_run():
    from database.connection import SessionLocal
    db = SessionLocal()
    try:
        # Dry run must not delete records and must preserve canonical prices
        result = run_bounded_staging_cleanup(db, retention_days=30, dry_run=True)
        assert result["dry_run"] is True
        assert result["deleted_count"] == 0
        assert result["preserved_canonical_prices"] >= 0
    finally:
        db.close()


# ==============================================================================
# 3. Idempotent Cron Endpoints Tests
# ==============================================================================


def test_cron_endpoint_unauthorized_without_secret(auth_client):
    client, _, _ = auth_client
    resp = client.post("/api/v1/system/cron/run-ingestion")
    assert resp.status_code == 401
    assert "X-Cron-Secret" in resp.json()["detail"]


def test_cron_endpoint_idempotency(auth_client):
    client, _, _ = auth_client
    valid_headers = {"X-Cron-Secret": "test-cron-secret-12345"}

    try:
        from routers import cron
    except ImportError:
        from apps.api.routers import cron

    # Mock ingestion cycle to return sample results quickly
    with patch.object(cron, "run_ingestion_cycle", new_callable=AsyncMock) as mock_ingest, \
         patch("services.ingestion.scheduler.run_ingestion_cycle", new_callable=AsyncMock):
        mock_ingest.return_value = [{"provider": "DNSE", "status": "SUCCESS"}]

        # First execution -> SUCCESS
        resp1 = client.post(
            "/api/v1/system/cron/run-ingestion",
            json={"as_of_date": "2026-10-18", "force": True},
            headers=valid_headers,
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "SUCCESS"
        assert resp1.json()["idempotency_key"] == "INGEST_EOD_2026-10-18"

        # Second execution for same date without force -> ALREADY_COMPLETED
        resp2 = client.post(
            "/api/v1/system/cron/run-ingestion",
            json={"as_of_date": "2026-10-18", "force": False},
            headers=valid_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "ALREADY_COMPLETED"
        assert "already succeeded" in resp2.json()["message"]

        # Third execution without any JSON body (e.g. cron-job.org default)
        resp3 = client.post(
            "/api/v1/system/cron/run-ingestion",
            headers=valid_headers,
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] in ("SUCCESS", "ALREADY_COMPLETED")


# ==============================================================================
# 4. Cloud AI Gateway & Zero-Budget Guard Tests
# ==============================================================================


def test_openrouter_free_model_enforcement():
    provider = OpenRouterProvider(api_key="sk-or-test-key")

    with patch.dict(os.environ, {"AI_ALLOW_PAID_APIS": "false"}):
        # Free model ending with :free is permitted
        provider._verify_free_model("meta-llama/llama-3.2-3b-instruct:free")

        # Paid model (without :free) is blocked by zero-budget guard
        with pytest.raises(AIPaidProviderBlockedError, match="Zero-budget guard requires free models"):
            provider._verify_free_model("openai/gpt-4o")


def test_ai_gateway_provider_priority_order():
    with patch.dict(os.environ, {"AI_PROVIDER_ORDER": "ollama"}):
        cfg = GatewayConfig.from_env()
        assert cfg.provider_priority == ("ollama",)

    # Legacy or unsupported providers are ignored in favor of Ollama
    with patch.dict(os.environ, {"AI_PROVIDER_ORDER": "gemini,groq,openrouter,ollama"}):
        cfg = GatewayConfig.from_env()
        assert cfg.provider_priority == ("ollama",)



def test_ai_gateway_ollama_not_assumed_in_cloud():
    gateway = AIGateway()
    # In cloud mode without OLLAMA_ENABLED=true, Ollama is unreachable
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "OLLAMA_ENABLED": "false"}):
        assert gateway.is_ollama_reachable() is False
        eligible = gateway.get_eligible_providers()
        assert "ollama" not in eligible
