from datetime import date, datetime, timedelta, timezone
import os
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

from database.connection import get_db
from database.models import Asset, IndexMembership, MacroSeries, Price
from services.macro.engine import MarketRegimeEngine

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))
from main import app


def _client_for_session(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_market_regime_does_not_infer_neutral_from_unrelated_price_count(db_session):
    asset = Asset(
        symbol=f"REGIME_{uuid4().hex[:10].upper()}",
        name="Regime count-only test",
        asset_type="STOCK",
        exchange="HOSE",
    )
    db_session.add(asset)
    db_session.flush()
    latest_date = date(1900, 1, 31)
    db_session.add_all([
        Price(
            asset_id=asset.id,
            observation_date=latest_date - timedelta(days=offset),
            raw_close=100.0 + offset,
            adjusted_close=100.0 + offset,
            source="TEST_ONLY",
            status="VALID",
        )
        for offset in range(20)
    ])
    db_session.commit()

    regime = MarketRegimeEngine.determine_regime(latest_date, session=db_session)

    assert regime.regime == "INSUFFICIENT_DATA"
    assert regime.confidence == 0.0


def test_market_dashboard_api_returns_honest_missing_metrics(db_session):
    with _client_for_session(db_session) as client:
        response = client.get("/api/v1/market/dashboard")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert {item["symbol"] for item in payload["indexes"]} == {"VN30", "VN100", "VN300"}
    assert payload["status"] in {"AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"}
    assert all(item["metric"]["status"] in {"AVAILABLE", "STALE", "INSUFFICIENT_DATA"} for item in payload["indexes"])
    assert payload["market_regime"]["regime"] in {"EXPANSION", "RECOVERY", "NEUTRAL", "RISK_OFF", "INSUFFICIENT_DATA"}
    assert payload["breadth"]["value"] is None or payload["breadth"]["source"]
    assert payload["foreign_flow"]["status"] == "NOT_CONFIGURED"
    assert payload["events_status"] in {"AVAILABLE", "INSUFFICIENT_DATA"}


def test_macro_api_marks_registered_series_without_observations_insufficient(db_session):
    db_session.add(MacroSeries(
        id=f"EMPTY_{uuid4().hex[:8]}", name="Registered empty series", provider="TEST",
        frequency="MONTHLY", unit="INDEX",
    ))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get("/api/v1/macro/observations/latest")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    registered = [item for group in payload["regions"].values() for item in group]
    assert any(
        item["series_id"].startswith("EMPTY_")
        and item["status"] == "INSUFFICIENT_DATA"
        and item["value"] is None
        and item["data_origin"] == "REGISTERED_SERIES"
        for item in registered
    )


def test_opportunity_api_hides_engine_baseline_and_reports_unavailable_filters(db_session):
    symbol = f"SCN_{uuid4().hex[:8].upper()}"
    test_sector = f"SCANNER_TEST_{uuid4().hex[:6].upper()}"
    db_session.add(Asset(symbol=symbol, name="Scanner contract", asset_type="STOCK", exchange="HOSE", sector=test_sector))
    db_session.commit()

    with _client_for_session(db_session) as client:
        response = client.get("/api/v1/opportunities", params={"score_min": 0, "sector": test_sector})

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INSUFFICIENT_DATA"
    assert payload["total_assets"] == 1
    assert "score: all candidates currently have INSUFFICIENT_DATA" in payload["unavailable_filters"]
    assert payload["results"] == []

    with _client_for_session(db_session) as client:
        unfiltered = client.get("/api/v1/opportunities", params={"sector": test_sector})
    app.dependency_overrides.clear()
    item = unfiltered.json()["results"][0]
    assert item["opportunity_score"] is None
    assert item["confidence"] == "INSUFFICIENT"
    assert item["risk_score"] is None
    assert item["valuation_status"] == "INSUFFICIENT_DATA"
    assert item["why_now"] == []
    assert item["why_not_now"][0]["direction"] == "UNCERTAINTY"
    assert "INSUFFICIENT_DATA" in item["why_not_now"][0]["description"]
    assert item["factor_summary"] is None


def test_opportunity_api_validates_score_filter_range(db_session):
    with _client_for_session(db_session) as client:
        response = client.get("/api/v1/opportunities", params={"score_min": 101})
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_market_regime_uses_vn100_index_momentum_and_published_constituents(db_session):
    benchmark_date = date(2010, 1, 1) + timedelta(days=uuid4().int % 1460)
    index = db_session.query(Asset).filter(Asset.symbol == "VN100").first()
    if index is None:
        index = Asset(symbol="VN100", name="VN100", asset_type="INDEX", exchange="HOSE")
        db_session.add(index)
    members = [
        Asset(symbol=f"BR{index_number}{uuid4().hex[:5].upper()}", name="Breadth member", asset_type="STOCK", exchange="HOSE")
        for index_number in range(12)
    ]
    db_session.add_all([index, *members])
    db_session.flush()
    index_prices = [
        Price(
            asset_id=index.id,
            observation_date=benchmark_date - timedelta(days=20 - offset),
            raw_close=100.0 + offset,
            adjusted_close=100.0 + offset,
            source="TEST_FIXTURE",
            status="VALID",
        )
        for offset in range(21)
    ]
    breadth_prices = []
    memberships = []
    for member in members:
        memberships.append(IndexMembership(
            index_symbol="VN100", symbol=member.symbol,
            start_date=benchmark_date, end_date=benchmark_date,
            published_at=datetime.combine(benchmark_date, datetime.min.time(), tzinfo=timezone.utc),
            is_active=True,
        ))
        breadth_prices.extend([
            Price(asset_id=member.id, observation_date=benchmark_date - timedelta(days=1), raw_close=100, adjusted_close=100, status="VALID"),
            Price(asset_id=member.id, observation_date=benchmark_date, raw_close=102, adjusted_close=102, status="VALID"),
        ])
    db_session.add_all([*index_prices, *breadth_prices, *memberships])
    db_session.commit()

    regime = MarketRegimeEngine.determine_regime(benchmark_date, session=db_session)

    assert regime.regime == "EXPANSION"
    assert regime.momentum_20d is not None and regime.momentum_20d > 0
    assert regime.breadth_percent == 100.0
    assert regime.advancing == len(members)
    published_memberships = [
        membership for membership in db_session.query(IndexMembership).filter(
            IndexMembership.index_symbol == "VN100",
            IndexMembership.start_date <= benchmark_date,
            IndexMembership.end_date.is_(None) | (IndexMembership.end_date >= benchmark_date),
        ).all()
        if membership.published_at is None or membership.published_at.date() <= benchmark_date
    ]
    assert regime.data_coverage == round(len(members) / len(published_memberships), 3)
    assert regime.model_version == "vn100_price_breadth_v1"