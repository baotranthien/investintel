import os
import sys
from datetime import date
from fastapi.testclient import TestClient
import psycopg2
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_database_url, get_db
from database.models import Asset, Price
from main import app
from services.research.backtest import BacktestConfig, HistoricalBacktestEngine


def _client_for_session(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_system_observability_endpoint(db_session):
    with _client_for_session(db_session) as client:
        response = client.get("/api/v1/system/observability")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"HEALTHY", "DEGRADED", "UNAVAILABLE"}
    assert "components" in data
    assert data["components"]["database"]["status"] in {"HEALTHY", "DEGRADED", "UNAVAILABLE"}
    assert data["components"]["redis"]["status"] in {"HEALTHY", "NOT_CONFIGURED", "UNAVAILABLE"}
    assert data["components"]["ai_provider"]["status"] in {"HEALTHY", "NOT_CONFIGURED", "UNAVAILABLE"}
    assert "background_jobs" in data
    assert "ingestion" in data
    assert "data_freshness" in data


def test_backtest_engine_pit_and_cost_deduction(db_session):
    engine = HistoricalBacktestEngine(db_session)
    config = BacktestConfig(
        universe=["HPG", "FPT"],
        start_date=date(2023, 1, 1),
        end_date=date(2024, 1, 1),
        horizon="1M",
        initial_capital=50_000_000.0,
        transaction_cost_pct=0.0015,
        tax_pct=0.0010,
        slippage_pct=0.0010,
    )
    result = engine.run_backtest(config)

    assert result.status in {"AVAILABLE", "INSUFFICIENT_DATA"}
    assert result.look_ahead_audit["violations"] == 0
    if result.status == "AVAILABLE":
        assert result.total_fees >= 0
        assert result.total_taxes >= 0
        assert result.total_slippage >= 0
        assert len(result.equity_curve) > 0


def test_local_privacy_and_security():
    # Verify no broker secrets or live credentials required in environment
    assert os.getenv("TCBS_API_KEY") is None
    assert os.getenv("BROKER_PASSWORD") is None


def test_unreachable_configured_postgres_does_not_fall_back_to_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example/investment")

    def fail_connection(*args, **kwargs):
        raise psycopg2.OperationalError("connection unavailable")

    monkeypatch.setattr(psycopg2, "connect", fail_connection)

    with pytest.raises(RuntimeError, match="refusing to fall back to SQLite"):
        get_database_url()
