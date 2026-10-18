from datetime import date
import os
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_db
from database.models import Asset, CorporateAction, EventRecord, FinancialStatement, NormalizedIncome, Price
from services.fundamentals.repository import FinancialRepository
from main import app


def test_financial_repository_preserves_missing_values_separately_from_zero(db_session):
    symbol = f"NULL{uuid4().hex[:8].upper()}"
    asset = Asset(symbol=symbol, name="Null contract", asset_type="STOCK", exchange="HOSE")
    db_session.add(asset)
    db_session.flush()
    statement = FinancialStatement(
        asset_id=asset.id,
        symbol=symbol,
        statement_type="INCOME_STATEMENT",
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        publication_date=date(2026, 2, 1),
        source_name="TEST_SOURCE",
        status="VALID",
    )
    db_session.add(statement)
    db_session.flush()
    db_session.add(NormalizedIncome(
        statement_id=statement.id,
        symbol=symbol,
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        revenue=None,
        net_income=0,
        eps_basic=None,
    ))
    db_session.flush()

    dataset = FinancialRepository(db_session).get_financial_dataset(symbol)

    assert dataset is not None
    row = dataset["income_annual"][0]
    assert row["revenue"] is None
    assert row["eps_basic"] is None
    assert row["net_income"] == 0.0


def _client_for_session(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_research_endpoint_withholds_unsupported_engine_numbers(db_session):
    symbol = f"RSH{uuid4().hex[:7].upper()}"
    asset = Asset(symbol=symbol, name="Research contract", asset_type="STOCK", exchange="HOSE", sector="BANK")
    db_session.add(asset)
    db_session.flush()
    db_session.add(Price(
        asset_id=asset.id,
        observation_date=date.today(),
        raw_close=42_000,
        adjusted_close=42_000,
        source="TEST_SOURCE",
        status="VALID",
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"]["symbol"] == symbol
    assert payload["price"]["value"] == 42_000
    assert payload["fundamentals"]["status"] == "INSUFFICIENT_DATA"
    assert payload["valuation"]["fair_value"] is None
    assert payload["valuation"]["metrics"]["dcf"]["value"] is None
    assert all(metric["value"] is None for metric in payload["factors"]["scores"].values())
    assert payload["risk"]["overall_score"] is None
    assert len(payload["risk"]["categories"]) == 10
    assert "nim" in payload["sector_analysis"]["applicable_metrics"]
    assert "inventory" in payload["sector_analysis"]["not_applicable_metrics"]
    assert payload["status"] == "PARTIAL"


def test_research_endpoint_preserves_missing_financial_values_and_evidence(db_session):
    symbol = f"NULL{uuid4().hex[:8].upper()}"
    asset = Asset(symbol=symbol, name="Null contract", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY")
    db_session.add(asset)
    db_session.flush()
    statement = FinancialStatement(
        asset_id=asset.id,
        symbol=symbol,
        statement_type="INCOME_STATEMENT",
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        publication_date=date(2026, 2, 1),
        source_name="CANONICAL_TEST_SOURCE",
        status="VALID",
    )
    db_session.add(statement)
    db_session.flush()
    db_session.add(NormalizedIncome(
        statement_id=statement.id,
        symbol=symbol,
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        revenue=None,
        net_income=0,
        eps_basic=None,
    ))
    db_session.add(EventRecord(
        id=f"evt-{uuid4().hex}",
        title=f"{symbol} filing update",
        description="Canonical event record for contract test.",
        event_type="EARNINGS",
        materiality="RELEVANT",
        severity=20,
        countries=["VNM"],
        affected_sectors=["TECHNOLOGY"],
        sources=["https://example.test/filing"],
        published_at=__import__("datetime").datetime(2026, 2, 2),
        retrieved_at=__import__("datetime").datetime(2026, 2, 2),
    ))
    db_session.add(CorporateAction(
        symbol=symbol,
        action_date=date(2026, 3, 1),
        ex_date=date(2026, 3, 1),
        action_type="CASH_DIVIDEND",
        value=500,
        source="CANONICAL_TEST_SOURCE",
        notes="Recorded distribution",
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}", params={"as_of": "2026-09-30"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    annual = payload["fundamentals"]["history"][0]
    assert annual["revenue"] is None
    assert annual["earnings"] == 0.0
    assert annual["eps"] is None
    assert payload["fundamentals"]["sources"] == ["CANONICAL_TEST_SOURCE"]
    assert payload["events"][0]["evidence"]["claim_type"] == "FACT"
    assert any(item["kind"] == "CORPORATE_ACTION" for item in payload["timeline"])


def test_research_endpoint_respects_as_of_publication_date(db_session):
    symbol = f"PIT{uuid4().hex[:8].upper()}"
    asset = Asset(symbol=symbol, name="PIT research", asset_type="STOCK", exchange="HOSE", sector="RETAIL")
    db_session.add(asset)
    db_session.flush()
    statement = FinancialStatement(
        asset_id=asset.id,
        symbol=symbol,
        statement_type="INCOME_STATEMENT",
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        publication_date=date(2026, 3, 1),
        source_name="CANONICAL_TEST_SOURCE",
        status="VALID",
    )
    db_session.add(statement)
    db_session.flush()
    db_session.add(NormalizedIncome(
        statement_id=statement.id,
        symbol=symbol,
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        revenue=100,
        net_income=10,
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}", params={"as_of": "2026-02-28"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["fundamentals"]["status"] == "INSUFFICIENT_DATA"
    assert payload["fundamentals"]["history"] == []


def test_annual_eps_is_not_used_as_ttm_multiple(db_session):
    symbol = f"ANNUAL{uuid4().hex[:6].upper()}"
    asset = Asset(symbol=symbol, name="Annual-only data", asset_type="STOCK", exchange="HOSE", sector="RETAIL")
    db_session.add(asset)
    db_session.flush()
    db_session.add(Price(
        asset_id=asset.id,
        observation_date=date.today(),
        raw_close=20_000,
        source="CANONICAL_TEST_SOURCE",
        status="VALID",
    ))
    statement = FinancialStatement(
        asset_id=asset.id,
        symbol=symbol,
        statement_type="INCOME_STATEMENT",
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        publication_date=date(2026, 2, 1),
        source_name="CANONICAL_TEST_SOURCE",
        status="VALID",
    )
    db_session.add(statement)
    db_session.flush()
    db_session.add(NormalizedIncome(
        statement_id=statement.id,
        symbol=symbol,
        fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025,
        period_type="ANNUAL",
        revenue=100,
        net_income=10,
        eps_basic=500,
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}")
    app.dependency_overrides.clear()

    payload = response.json()
    assert payload["fundamentals"]["period"] == "ANNUAL"
    assert payload["fundamentals"]["metrics"]["eps_ttm"]["value"] is None
    assert payload["valuation"]["metrics"]["pe"]["value"] is None


def test_research_endpoint_marks_old_price_stale(db_session):
    symbol = f"STALE{uuid4().hex[:6].upper()}"
    asset = Asset(symbol=symbol, name="Stale price data", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY")
    db_session.add(asset)
    db_session.flush()
    db_session.add(Price(
        asset_id=asset.id,
        observation_date=date(2020, 1, 2),
        raw_close=100,
        source="STATIC_TEST_CSV",
        status="VALID",
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}", params={"as_of": "2026-09-30"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["price"]["status"] == "STALE"
    assert payload["data_quality"]["stale_warning"] is True
    assert payload["price"]["data_origin"] == "SEEDED_OR_UNTRACED"


def test_research_workspace_uses_four_quarter_ttm_values(db_session):
    symbol = f"TTM{uuid4().hex[:7].upper()}"
    asset = Asset(symbol=symbol, name="TTM contract", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY")
    db_session.add(asset)
    db_session.flush()
    db_session.add(Price(
        asset_id=asset.id,
        observation_date=date(2025, 12, 31),
        raw_close=200,
        source="CANONICAL_TEST_SOURCE",
        status="VALID",
    ))
    quarter_periods = [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
    for quarter_number, period_end in enumerate(quarter_periods, start=1):
        statement = FinancialStatement(
            asset_id=asset.id,
            symbol=symbol,
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=period_end,
            fiscal_quarter=quarter_number,
            fiscal_year=2025,
            period_type="QUARTERLY",
            publication_date=period_end.replace(day=min(period_end.day + 20, 28)),
            source_name="CANONICAL_TEST_SOURCE",
            status="VALID",
        )
        db_session.add(statement)
        db_session.flush()
        db_session.add(NormalizedIncome(
            statement_id=statement.id,
            symbol=symbol,
            fiscal_period_end=period_end,
            fiscal_quarter=quarter_number,
            fiscal_year=2025,
            period_type="QUARTERLY",
            revenue=100,
            net_income=10,
            eps_basic=5,
        ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get(f"/api/v1/research/{symbol}", params={"as_of": "2026-09-30"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["fundamentals"]["period"] == "TTM"
    assert payload["fundamentals"]["metrics"]["revenue"]["value"] == 400
    assert payload["fundamentals"]["metrics"]["net_income"]["value"] == 40
    assert payload["fundamentals"]["metrics"]["eps_ttm"]["value"] == 20
    assert payload["valuation"]["metrics"]["pe"]["value"] == 10


def test_historical_backtest_endpoint(db_session):
    with _client_for_session(db_session) as client:
        # Run backtest with canonical seeded data
        resp = client.post("/api/v1/research/backtest", json={
            "universe": ["HPG", "FPT"],
            "start_date": "2023-01-01",
            "end_date": "2026-10-01",
            "horizon": "1M",
            "initial_capital": 100000000.0,
            "transaction_cost_pct": 0.0015,
            "tax_pct": 0.001,
            "slippage_pct": 0.001,
        })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"AVAILABLE", "INSUFFICIENT_DATA"}
    assert "look_ahead_audit" in data
    assert data["look_ahead_audit"]["violations"] == 0
    assert "data_quality" in data
    assert "initial_capital" in data
    assert data["initial_capital"] == 100000000.0
