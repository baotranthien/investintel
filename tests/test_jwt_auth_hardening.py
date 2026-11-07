# tests/test_jwt_secret_hardening.py
"""
Test Suite: JWT Secret Hardening & Security Enforcement.

Verifies:
1. Production without JWT_SECRET_KEY/APP_AUTH_SECRET -> startup rejected (fail-closed).
2. Production using known prohibited default secrets -> startup rejected.
3. Production using valid configured secret (>= 32 chars) -> startup succeeds.
4. Test/Dev environment with explicit secret fixture -> authentication succeeds.
5. Missing secret in dev/runtime -> fail-closed (NO silent fallback to hardcoded string).
6. Token signed with valid secret verifies successfully.
7. Token signed with mismatched/tampered secret is rejected.
8. Health endpoint, diagnostics, and application logs never leak secret values.
"""

import os
import json
import logging
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.auth.security import (
    create_session_token,
    get_jwt_secret,
    hash_password,
    is_cloud_mode,
    validate_jwt_secret_configuration,
    verify_session_token,
    MIN_SECRET_LENGTH,
    PROHIBITED_JWT_SECRETS,
)


VALID_TEST_SECRET = "test-jwt-secret-hardening-valid-32bytes-hex-ok"
VALID_PASSWORD = "strong_test_password_123"


def test_production_without_jwt_secret_fails_startup():
    """1. Production without JWT_SECRET_KEY or APP_AUTH_SECRET must fail closed."""
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "CLOUD_MODE": "true",
            "JWT_SECRET_KEY": "",
            "APP_AUTH_SECRET": "",
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            validate_jwt_secret_configuration()
        assert "JWT secret key missing in production" in str(exc_info.value)

        # Also verify get_jwt_secret(require_valid=True) raises
        with pytest.raises(RuntimeError) as exc_info2:
            get_jwt_secret(require_valid=True)
        assert "JWT secret key missing in production" in str(exc_info2.value)


@pytest.mark.parametrize("prohibited_secret", [
    "local-dev-secret-do-not-use-in-production-123456",
    "secret",
    "password",
    "changeme",
    "admin",
    "GENERATE_WITH_OPENSSL_RAND_HEX_32",
    "custom-local-dev-do-not-use-in-production-sample",
])
def test_production_with_prohibited_default_secret_fails_startup(prohibited_secret):
    """2. Production using known default or sample secrets must fail closed."""
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "CLOUD_MODE": "true",
            "JWT_SECRET_KEY": prohibited_secret,
            "APP_AUTH_PASSWORD_HASH": hash_password(VALID_PASSWORD),
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            validate_jwt_secret_configuration()
        assert "prohibited default" in str(exc_info.value).lower()


def test_production_with_short_secret_fails_startup():
    """Production secret shorter than MIN_SECRET_LENGTH (32 chars) must fail closed."""
    short_secret = "too_short_secret_12345"
    assert len(short_secret) < MIN_SECRET_LENGTH
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "CLOUD_MODE": "true",
            "JWT_SECRET_KEY": short_secret,
            "APP_AUTH_PASSWORD_HASH": hash_password(VALID_PASSWORD),
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError) as exc_info:
            validate_jwt_secret_configuration()
        assert f"{MIN_SECRET_LENGTH} characters" in str(exc_info.value)


def test_production_with_valid_configured_secret_succeeds():
    """3. Production using valid 32+ char secret and password hash succeeds validation."""
    strong_secret = "prod_strong_isolated_secret_key_32chars_min_ok"
    assert len(strong_secret) >= MIN_SECRET_LENGTH
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "CLOUD_MODE": "true",
            "JWT_SECRET_KEY": strong_secret,
            "APP_AUTH_PASSWORD_HASH": hash_password(VALID_PASSWORD),
        },
        clear=False,
    ):
        # Must not raise
        validate_jwt_secret_configuration()
        resolved = get_jwt_secret(require_valid=True)
        assert resolved == strong_secret


def test_test_environment_with_explicit_secret_fixture_authenticates():
    """4. In test/dev environment with explicit secret fixture, authentication flow succeeds."""
    pw_hash = hash_password(VALID_PASSWORD)
    with patch.dict(
        os.environ,
        {
            "APP_AUTH_ENABLED": "true",
            "JWT_SECRET_KEY": VALID_TEST_SECRET,
            "APP_AUTH_PASSWORD_HASH": pw_hash,
            "ALLOWED_ORIGINS": "http://localhost:3000",
        },
        clear=False,
    ):
        with TestClient(app) as client:
            # Login
            login_resp = client.post("/api/v1/auth/login", json={"password": VALID_PASSWORD})
            assert login_resp.status_code == 200
            data = login_resp.json()
            assert data["status"] == "authenticated"
            assert "investintel_session" in login_resp.cookies

            # Check session
            session_resp = client.get("/api/v1/auth/session")
            assert session_resp.status_code == 200
            session_data = session_resp.json()
            assert session_data["authenticated"] is True
            assert session_data["user"] == "personal_investor"


def test_no_silent_fallback_when_config_missing():
    """5. When JWT secret is missing, system must fail closed with NO silent fallback to known string."""
    # A. In dev mode with auth enabled, startup fails closed
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "development",
            "CLOUD_MODE": "false",
            "JWT_SECRET_KEY": "",
            "APP_AUTH_SECRET": "",
            "APP_AUTH_ENABLED": "true",
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError) as startup_exc:
            validate_jwt_secret_configuration()
        assert "JWT secret key is not configured" in str(startup_exc.value)

    # B. Test endpoint behavior when secret is not configured
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "development",
            "CLOUD_MODE": "false",
            "JWT_SECRET_KEY": "",
            "APP_AUTH_SECRET": "",
            "APP_AUTH_ENABLED": "false",
        },
        clear=False,
    ):
        # 1. get_jwt_secret must raise RuntimeError when required
        with pytest.raises(RuntimeError) as exc_info:
            get_jwt_secret(require_valid=True)
        assert "JWT secret key is not configured" in str(exc_info.value)
        assert "local-dev-secret" not in str(exc_info.value)

        # 2. require_valid=False returns None
        assert get_jwt_secret(require_valid=False) is None

        # 3. Router endpoints fail closed (HTTP 500 on login, unconfigured on session)
        with TestClient(app) as client:
            resp = client.post("/api/v1/auth/login", json={"password": "any_password"})
            assert resp.status_code == 500
            detail = resp.json()["detail"]
            assert "Khóa bảo mật chưa được thiết lập" in detail or "chưa hoàn tất" in detail

            s_resp = client.get("/api/v1/auth/session")
            assert s_resp.status_code == 200
            assert s_resp.json() == {"authenticated": False, "reason": "auth_unconfigured"}


def test_token_signed_with_valid_secret_verifies_successfully():
    """6. Token signed with valid secret verifies successfully and preserves claims."""
    token = create_session_token(secret=VALID_TEST_SECRET, expiry_seconds=3600, user_id="investor_01")
    assert token is not None
    assert "." in token

    payload = verify_session_token(token, secret=VALID_TEST_SECRET)
    assert payload is not None
    assert payload["sub"] == "investor_01"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload


def test_token_signed_with_wrong_secret_rejected():
    """7. Token signed with wrong secret or tampered signature is rejected."""
    token = create_session_token(secret=VALID_TEST_SECRET, expiry_seconds=3600)
    wrong_secret = "completely_different_secret_key_32bytes_hex_ok"

    # Verification with wrong secret must return None
    payload = verify_session_token(token, secret=wrong_secret)
    assert payload is None

    # Tampered token payload
    parts = token.split(".")
    tampered_token = f"{parts[0]}tampered.{parts[1]}"
    assert verify_session_token(tampered_token, secret=VALID_TEST_SECRET) is None


def test_health_endpoint_and_logs_do_not_leak_secret(caplog):
    """8. Health endpoint, diagnostics, and application logs never leak secret values."""
    secret_canary = "super_canary_secret_1234567890abcdef"
    with patch.dict(
        os.environ,
        {
            "JWT_SECRET_KEY": secret_canary,
            "APP_AUTH_ENABLED": "true",
            "ALLOWED_ORIGINS": "http://localhost:3000",
        },
        clear=False,
    ):
        with TestClient(app) as client:
            # 1. /health
            h_resp = client.get("/health")
            assert h_resp.status_code == 200
            assert secret_canary not in h_resp.text

            # 2. /ready
            r_resp = client.get("/ready")
            assert r_resp.status_code == 200
            assert secret_canary not in r_resp.text

            # 3. /api/v1/system/diagnostics
            d_resp = client.get("/api/v1/system/diagnostics")
            assert d_resp.status_code == 200
            assert secret_canary not in d_resp.text

            # 4. Check application logs
            for record in caplog.records:
                assert secret_canary not in record.getMessage()
