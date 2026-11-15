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
    assert (
        normalize_database_url(
            "postgres://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require&supa=base-pooler.x"
        )
        == "postgresql://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert (
        normalize_database_url(
            "postgres://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?pgbouncer=true&sslmode=require"
        )
        == "postgresql://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )


def test_cloud_mode_falls_back_to_postgres_url_and_strips_supa():
    with patch.dict(
        os.environ,
        {
            "CLOUD_MODE": "true",
            "DATABASE_URL": "",
            "POSTGRES_URL": "postgres://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require&supa=base-pooler.x",
        },
        clear=False,
    ):
        with patch("psycopg2.connect") as mock_connect:
            resolved = get_database_url()
            assert (
                resolved
                == "postgresql://user:pass@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
            )
            mock_connect.assert_called_once()


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
    import contextlib
    import sys

    client, _, _ = auth_client
    valid_headers = {"X-Cron-Secret": "test-cron-secret-12345"}

    if "apps.api.routers.cron" not in sys.modules and "routers.cron" not in sys.modules:
        try:
            from apps.api.routers import cron as _cron  # noqa: F401
        except ImportError:
            from routers import cron as _cron  # noqa: F401

    cron_modules = [
        sys.modules[name]
        for name in ("apps.api.routers.cron", "routers.cron")
        if name in sys.modules
    ]

    # Mock ingestion cycle across whichever module alias `apps.api.main` bound
    with contextlib.ExitStack() as stack:
        mocks = [
            stack.enter_context(patch.object(mod, "run_ingestion_cycle", new_callable=AsyncMock))
            for mod in cron_modules
        ]
        stack.enter_context(patch("services.ingestion.scheduler.run_ingestion_cycle", new_callable=AsyncMock))
        for mock_ingest in mocks:
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

    with patch.dict(os.environ, {"AI_PROVIDER_ORDER": "groq,gemini,ollama"}):
        cfg = GatewayConfig.from_env()
        assert cfg.provider_priority == ("groq", "gemini", "ollama")



def test_ai_gateway_ollama_not_assumed_in_cloud():
    gateway = AIGateway()
    # In cloud mode without OLLAMA_ENABLED=true, Ollama is unreachable
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "OLLAMA_ENABLED": "false"}):
        assert gateway.is_ollama_reachable() is False
        eligible = gateway.get_eligible_providers()
        assert "ollama" not in eligible


def test_lifespan_prewarm_runs_off_event_loop():
    import asyncio
    import threading
    from apps.api.main import lifespan

    observed_threads = []
    main_loop_thread = threading.current_thread()

    def _fake_scanner(*args, **kwargs):
        observed_threads.append(threading.current_thread())
        return {"items": []}

    real_sleep = asyncio.sleep

    async def _fast_sleep(delay, *args, **kwargs):
        await real_sleep(0)

    async def _run_lifespan():
        with (
            patch.dict(
                os.environ,
                {
                    "CLOUD_MODE": "true",
                    "ALLOW_PRODUCTION_DB_WRITE": "false",
                    "ALLOW_MARKET_DATA_SYNC": "false",
                    "APP_AUTH_ENABLED": "false",
                },
            ),
            patch("apps.api.main.asyncio.sleep", side_effect=_fast_sleep),
            patch("services.opportunity.scanner.build_opportunity_scanner", side_effect=_fake_scanner),
        ):
            saved = os.environ.pop("PYTEST_CURRENT_TEST", None)
            try:
                async with lifespan(app):
                    for _ in range(20):
                        if len(observed_threads) >= 2:
                            break
                        await real_sleep(0.02)
            finally:
                if saved is not None:
                    os.environ["PYTEST_CURRENT_TEST"] = saved

    from services.common.cache import opportunity_cache

    try:
        asyncio.run(_run_lifespan())
        assert len(observed_threads) == 2
        assert all(t is not main_loop_thread for t in observed_threads)
    finally:
        opportunity_cache.clear()


def test_financial_repository_batch_parity(db_session):
    from datetime import date, datetime
    from sqlalchemy import event
    from database.models import Asset
    from services.fundamentals.repository import FinancialRepository

    repo = FinancialRepository(db_session)
    symbols = ["BMP", "FPT", "VCB", "PLX", "UNKNOWN_XYZ"]

    for as_of in (None, date(2026, 3, 15), datetime(2026, 3, 15, 10, 0, 0)):
        batch_result = repo.get_financial_datasets_batch(symbols, as_of_date=as_of)
        assert set(batch_result.keys()) == set(symbols)
        assert batch_result["UNKNOWN_XYZ"] is None
        for sym in symbols:
            single_result = repo.get_financial_dataset(sym, as_of_date=as_of)
            assert batch_result[sym] == single_result

    assets = db_session.query(Asset).filter(Asset.symbol.in_(["BMP", "FPT", "VCB"])).all()
    assets_by_sym = {a.symbol: a for a in assets}
    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    sa_engine = db_session.get_bind().engine
    event.listen(sa_engine, "before_cursor_execute", _count_queries)
    try:
        prefetched = repo.get_financial_datasets_batch(
            ["BMP", "FPT", "VCB", "PLX"],
            assets_by_symbol=assets_by_sym,
        )
    finally:
        event.remove(sa_engine, "before_cursor_execute", _count_queries)

    assert query_count <= 8
    assert prefetched["BMP"] == repo.get_financial_dataset("BMP")


def test_market_regime_engine_batched_queries(db_session):
    from datetime import date, timedelta
    from sqlalchemy import event, or_
    from database.models import Asset, IndexMembership, Price
    from services.macro.engine import MarketRegimeEngine

    base_day = date(2026, 4, 1)
    bench = db_session.query(Asset).filter(Asset.symbol == "VN100").first()
    if not bench:
        bench = Asset(symbol="VN100", name="VN100 Index", asset_type="INDEX", exchange="HOSE", status="ACTIVE")
        db_session.add(bench)
        db_session.flush()

    for idx in range(25):
        obs = base_day + timedelta(days=idx)
        if not db_session.query(Price).filter(Price.asset_id == bench.id, Price.observation_date == obs).first():
            db_session.add(
                Price(
                    asset_id=bench.id,
                    observation_date=obs,
                    raw_close=1200.0 + idx,
                    adjusted_close=1200.0 + idx,
                    volume=1000000,
                    status="VALID",
                )
            )
    latest_day = base_day + timedelta(days=24)
    prev_day = base_day + timedelta(days=23)

    memberships = (
        db_session.query(IndexMembership)
        .filter(
            IndexMembership.index_symbol == "VN100",
            IndexMembership.start_date <= latest_day,
            or_(IndexMembership.end_date.is_(None), IndexMembership.end_date >= latest_day),
        )
        .all()
    )
    member_syms = list(dict.fromkeys(m.symbol for m in memberships if m.symbol))
    if not member_syms:
        member_syms = ["BMP", "FPT", "VCB"]
        for sym in member_syms:
            db_session.add(IndexMembership(index_symbol="VN100", symbol=sym, start_date=base_day, end_date=None))

    assets_by_sym = {
        a.symbol: a
        for a in db_session.query(Asset).filter(Asset.symbol.in_(member_syms)).all()
    }
    target_syms = member_syms[:60]
    for sym in target_syms:
        if sym not in assets_by_sym:
            asset = Asset(symbol=sym, name=sym, asset_type="STOCK", exchange="HOSE", status="ACTIVE")
            db_session.add(asset)
            assets_by_sym[sym] = asset
    db_session.flush()
    for idx, sym in enumerate(target_syms):
        asset = assets_by_sym[sym]
        if idx % 3 == 0:
            prev_px, cur_px = 100.0, 105.0
        elif idx % 3 == 1:
            prev_px, cur_px = 120.0, 118.0
        else:
            prev_px, cur_px = 90.0, 90.0
        for obs, px in ((prev_day, prev_px), (latest_day, cur_px)):
            existing = db_session.query(Price).filter(Price.asset_id == asset.id, Price.observation_date == obs).first()
            if existing:
                existing.raw_close = px
                existing.adjusted_close = px
                existing.status = "VALID"
            else:
                db_session.add(
                    Price(
                        asset_id=asset.id,
                        observation_date=obs,
                        raw_close=px,
                        adjusted_close=px,
                        volume=500000,
                        status="VALID",
                    )
                )
    db_session.flush()

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    sa_engine = db_session.get_bind().engine
    event.listen(sa_engine, "before_cursor_execute", _count_queries)
    try:
        regime = MarketRegimeEngine.determine_regime(as_of=latest_day, session=db_session, benchmark="VN100")
    finally:
        event.remove(sa_engine, "before_cursor_execute", _count_queries)

    assert regime.regime != "INSUFFICIENT_DATA"
    assert regime.covered_members == len(target_syms)
    assert query_count <= 5


def test_factor_screener_batched_queries(db_session):
    from sqlalchemy import event
    from database.connection import engine as default_engine

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    with patch.dict(os.environ, {"APP_AUTH_ENABLED": "false"}):
        with TestClient(app) as client:
            event.listen(default_engine, "before_cursor_execute", _count_queries)
            try:
                resp = client.get("/api/v1/factors/screener")
            finally:
                event.remove(default_engine, "before_cursor_execute", _count_queries)

            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] > 0
            assert len(data["results"]) == data["count"]
            assert query_count <= 15

            single_resp = client.get("/api/v1/factors/BMP")
            assert single_resp.status_code == 200
            assert single_resp.json()["symbol"] == "BMP"


def test_macro_observations_batched_queries(db_session):
    from datetime import date
    from sqlalchemy import event
    from services.macro.observations import get_latest_macro_series

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    sa_engine = db_session.get_bind().engine
    event.listen(sa_engine, "before_cursor_execute", _count_queries)
    try:
        res = get_latest_macro_series(db_session, date(2026, 11, 13))
    finally:
        event.remove(sa_engine, "before_cursor_execute", _count_queries)

    assert res.status in ("AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA")
    assert query_count <= 6


def test_peer_comparison_batched_queries(db_session):
    from datetime import date
    from sqlalchemy import event
    from services.valuation.peers import PeerComparisonEngine

    query_count = 0

    def _count_queries(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    sa_engine = db_session.get_bind().engine
    event.listen(sa_engine, "before_cursor_execute", _count_queries)
    try:
        res = PeerComparisonEngine(db_session).compare_peers("FPT", as_of=date(2026, 11, 13))
    finally:
        event.remove(sa_engine, "before_cursor_execute", _count_queries)

    assert res.target_symbol == "FPT"
    assert res.peers_evaluated >= 1
    assert query_count <= 16


def test_ai_context_bounded_queries_in_cloud_mode(db_session):
    from datetime import date
    from sqlalchemy import event
    from services.ai.tools import AITools

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa_engine = db_session.get_bind().engine
    saved_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        with patch.dict(os.environ, {"CLOUD_MODE": "true"}):
            event.listen(sa_engine, "before_cursor_execute", _capture)
            try:
                ctx = AITools.get_context(
                    "FPT",
                    date(2026, 11, 13),
                    session=db_session,
                    question="Danh gia ROE va dinh gia FPT?",
                )
            finally:
                event.remove(sa_engine, "before_cursor_execute", _capture)
    finally:
        if saved_pytest is not None:
            os.environ["PYTEST_CURRENT_TEST"] = saved_pytest

    assert ctx["symbol"] == "FPT"
    assert ctx["decision_state"] == "AVAILABLE"
    assert len(ctx.get("evidence", [])) > 0
    assert len(statements) <= 115
    inserts = [stmt for stmt in statements if stmt.lstrip().upper().startswith("INSERT")]
    assert not inserts, f"Unexpected INSERTs: {inserts}"



