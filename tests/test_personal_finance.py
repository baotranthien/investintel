from datetime import date, timedelta
from decimal import Decimal
import os
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_db
from database.models import (
    Asset,
    DcaPlan,
    ManualPortfolioTransaction,
    PersonalPortfolio,
    PersonalPortfolioSnapshot,
    PortfolioHolding,
    PortfolioTarget,
    Price,
    WatchlistItem,
    WatchlistSnapshot,
    WatchlistThesisRevision,
)
from services.portfolio.engine import compare_snapshots
from main import app


@pytest.fixture(autouse=True)
def clear_test_personal_data(db_session):
    for model in (
        WatchlistSnapshot,
        WatchlistThesisRevision,
        WatchlistItem,
        PersonalPortfolioSnapshot,
        ManualPortfolioTransaction,
        DcaPlan,
        PortfolioTarget,
        PortfolioHolding,
        PersonalPortfolio,
    ):
        db_session.query(model).delete(synchronize_session=False)
    db_session.flush()


def _client_for_session(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _add_asset(db_session, symbol=None, sector="TECHNOLOGY"):
    symbol = symbol or f"PF{uuid4().hex[:8].upper()}"
    existing = db_session.query(Asset).filter(Asset.symbol == symbol).first()
    if existing is not None:
        return existing
    asset = Asset(symbol=symbol, name=f"Portfolio {symbol}", asset_type="STOCK", exchange="HOSE", sector=sector)
    db_session.add(asset)
    db_session.flush()
    return asset


def _post(client, route, **kwargs):
    response = client.post(route, **kwargs)
    app.dependency_overrides.clear()
    return response


def _get(client, route, **kwargs):
    response = client.get(route, **kwargs)
    app.dependency_overrides.clear()
    return response


def _patch(client, route, **kwargs):
    response = client.patch(route, **kwargs)
    app.dependency_overrides.clear()
    return response


def test_portfolio_holding_crud_and_manual_transaction_is_non_executing(db_session):
    asset = _add_asset(db_session)
    with _client_for_session(db_session) as client:
        bad = client.post("/api/v1/portfolio/holdings", json={
            "symbol": asset.symbol, "quantity": 0, "average_cost": 100, "acquisition_date": "2025-01-01",
        })
    app.dependency_overrides.clear()
    assert bad.status_code == 422

    with _client_for_session(db_session) as client:
        created = client.post("/api/v1/portfolio/holdings", json={
            "symbol": asset.symbol.lower(), "quantity": "2.5", "average_cost": "1000", "acquisition_date": "2025-01-01",
        })
    app.dependency_overrides.clear()
    assert created.status_code == 201
    holding_id = created.json()["id"]
    assert created.json()["symbol"] == asset.symbol
    assert created.json()["role"] == "UNASSIGNED"

    with _client_for_session(db_session) as client:
        duplicate = client.post("/api/v1/portfolio/holdings", json={
            "symbol": asset.symbol, "quantity": 1, "average_cost": 1000, "acquisition_date": "2025-01-01",
        })
    app.dependency_overrides.clear()
    assert duplicate.status_code == 409

    with _client_for_session(db_session) as client:
        updated = client.patch(f"/api/v1/portfolio/holdings/{holding_id}", json={"role": "CORE", "horizon": "LONG_TERM"})
    app.dependency_overrides.clear()
    assert updated.status_code == 200
    assert updated.json()["role"] == "CORE"

    with _client_for_session(db_session) as client:
        transaction = client.post("/api/v1/portfolio/transactions", json={
            "symbol": asset.symbol, "transaction_type": "BUY", "quantity": 1,
            "unit_price": 1100, "transaction_date": "2025-02-01", "notes": "Manual note",
        })
    app.dependency_overrides.clear()
    assert transaction.status_code == 201
    assert transaction.json()["entry_source"] == "MANUAL"
    assert transaction.json()["holdings_updated"] is False

    with _client_for_session(db_session) as client:
        holdings = client.get("/api/v1/portfolio/holdings")
    app.dependency_overrides.clear()
    assert holdings.status_code == 200
    assert len(holdings.json()) == 1
    assert holdings.json()[0]["quantity"] == 2.5

    with _client_for_session(db_session) as client:
        removed = client.delete(f"/api/v1/portfolio/holdings/{holding_id}")
    app.dependency_overrides.clear()
    assert removed.status_code == 204
    with _client_for_session(db_session) as client:
        empty_portfolio = client.get("/api/v1/portfolio")
    app.dependency_overrides.clear()
    assert empty_portfolio.json()["status"] == "EMPTY"


def test_portfolio_value_requires_all_prices_and_concentration_is_configured(db_session):
    first = _add_asset(db_session, sector="TECHNOLOGY")
    second = _add_asset(db_session, sector="BANK")
    with _client_for_session(db_session) as client:
        for asset in (first, second):
            response = client.post("/api/v1/portfolio/holdings", json={
                "symbol": asset.symbol, "quantity": 10, "average_cost": 100, "acquisition_date": "2025-01-01",
            })
            assert response.status_code == 201
    app.dependency_overrides.clear()

    with _client_for_session(db_session) as client:
        partial = client.get("/api/v1/portfolio")
    app.dependency_overrides.clear()
    assert partial.json()["status"] == "PARTIAL"
    assert partial.json()["summary"]["total_value"] is None
    assert all(row["current_weight"] is None for row in partial.json()["holdings"])
    assert any(warning["code"] == "MISSING_PRICE" for warning in partial.json()["concentration"]["warnings"])

    db_session.add_all([
        Price(asset_id=first.id, observation_date=date.today(), raw_close=200, source="CANONICAL_A", status="VALID"),
        Price(asset_id=second.id, observation_date=date.today(), raw_close=100, source="CANONICAL_B", status="VALID"),
    ])
    db_session.commit()
    with _client_for_session(db_session) as client:
        settings = client.patch("/api/v1/portfolio/settings", json={"single_name_limit": 0.6, "sector_limit": 0.7})
    app.dependency_overrides.clear()
    assert settings.status_code == 200
    with _client_for_session(db_session) as client:
        complete = client.get("/api/v1/portfolio")
    app.dependency_overrides.clear()
    assert complete.json()["status"] == "AVAILABLE", complete.json()
    assert complete.json()["summary"]["total_value"] == 3000
    assert complete.json()["summary"]["cost_basis"] == 2000
    assert complete.json()["summary"]["unrealized_pnl"] == 1000
    assert any(warning["code"] == "SINGLE_NAME_CONCENTRATION" for warning in complete.json()["concentration"]["warnings"])
    assert complete.json()["risk_exposure"]["value"] is None
    assert complete.json()["factor_exposure"]["value"] is None


def test_targets_dca_bounds_and_advisory_routing(db_session):
    assets = [_add_asset(db_session) for _ in range(3)]
    for asset in assets:
        db_session.add(Price(asset_id=asset.id, observation_date=date.today(), raw_close=100, source="CANONICAL", status="VALID"))
        with _client_for_session(db_session) as client:
            created = client.post("/api/v1/portfolio/holdings", json={
                "symbol": asset.symbol, "quantity": 100, "average_cost": 100, "acquisition_date": "2025-01-01",
            })
        app.dependency_overrides.clear()
        assert created.status_code == 201
    db_session.commit()

    with _client_for_session(db_session) as client:
        invalid_targets = client.put("/api/v1/portfolio/targets", json={"targets": [
            {"symbol": assets[0].symbol, "target_weight": 0.7},
            {"symbol": assets[1].symbol, "target_weight": 0.6},
        ]})
    app.dependency_overrides.clear()
    assert invalid_targets.status_code == 422

    with _client_for_session(db_session) as client:
        targets = client.put("/api/v1/portfolio/targets", json={"targets": [
            {"symbol": asset.symbol, "target_weight": 0.2} for asset in assets
        ]})
    app.dependency_overrides.clear()
    assert targets.status_code == 200
    assert abs(targets.json()["total_weight"] - 0.6) < 1e-9

    with _client_for_session(db_session) as client:
        invalid_plan = client.put("/api/v1/portfolio/dca", json={"monthly_amount": 900000, "core_pct": 0.75, "satellite_pct": 0.25})
    app.dependency_overrides.clear()
    assert invalid_plan.status_code == 422

    with _client_for_session(db_session) as client:
        plan = client.put("/api/v1/portfolio/dca", json={"monthly_amount": 350000, "core_pct": 0.75, "satellite_pct": 0.25})
    app.dependency_overrides.clear()
    body = plan.json()
    assert body["saved"] is True
    assert body["monthly_amount"] == 350000
    assert len(body["routes"]) <= 2
    assert sum(route["amount"] for route in body["routes"]) + body["unused_or_satellite_reserve"] == 350000
    assert "No orders are executed" in body["note"]


def test_watchlist_crud_thesis_audit_and_evidence_snapshot_change(db_session):
    asset = _add_asset(db_session, sector="TECHNOLOGY")
    with _client_for_session(db_session) as client:
        created = client.post("/api/v1/watchlist", json={
            "symbol": asset.symbol, "thesis": "Initial research thesis", "horizon": "LONG_TERM", "invalidation": "Evidence reverses",
        })
    app.dependency_overrides.clear()
    assert created.status_code == 201
    item_id = created.json()["id"]

    with _client_for_session(db_session) as client:
        no_reason = client.patch(f"/api/v1/watchlist/{item_id}", json={"thesis": "Changed thesis"})
    app.dependency_overrides.clear()
    assert no_reason.status_code == 422

    with _client_for_session(db_session) as client:
        changed = client.patch(f"/api/v1/watchlist/{item_id}", json={"thesis": "Changed thesis", "change_reason": "New filing evidence"})
    app.dependency_overrides.clear()
    assert changed.status_code == 200
    with _client_for_session(db_session) as client:
        history_response = client.get(f"/api/v1/watchlist/{item_id}/thesis-history")
    app.dependency_overrides.clear()
    history = history_response.json()
    assert history["revisions"][0]["change_reason"] == "New filing evidence"

    db_session.add(Price(asset_id=asset.id, observation_date=date.today() - timedelta(days=1), raw_close=100, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()
    with _client_for_session(db_session) as client:
        first_snapshot = client.post(f"/api/v1/watchlist/{item_id}/snapshot")
    app.dependency_overrides.clear()
    assert first_snapshot.status_code == 200

    db_session.add(Price(asset_id=asset.id, observation_date=date.today(), raw_close=120, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()
    with _client_for_session(db_session) as client:
        second_snapshot = client.post(f"/api/v1/watchlist/{item_id}/snapshot")
    app.dependency_overrides.clear()
    changes = second_snapshot.json()["changes"]
    assert any(change["type"] == "PRICE_CHANGE" and change["evidence"]["source"] == "CANONICAL_PRICE" for change in changes)
    assert all(change["materiality"] == "OBSERVED_UNCLASSIFIED" for change in changes)

    with _client_for_session(db_session) as client:
        removed = client.delete(f"/api/v1/watchlist/{item_id}")
    app.dependency_overrides.clear()
    assert removed.status_code == 204


def test_personal_template_is_labeled_and_portfolio_fit_keeps_scores_separate(db_session):
    assets = [
        _add_asset(db_session, "FUEVN100", "INDEX_FUND"),
        _add_asset(db_session, "FPT", "TECHNOLOGY"),
        _add_asset(db_session, "VCB", "BANK"),
        _add_asset(db_session, "MWG", "RETAIL"),
    ]
    for asset in assets:
        asset.asset_type = "ETF" if asset.symbol == "FUEVN100" else "STOCK"
    db_session.commit()
    with _client_for_session(db_session) as client:
        template_response = client.get("/api/v1/portfolio/templates")
    app.dependency_overrides.clear()
    template = template_response.json()["templates"][0]
    assert template["label"] == "Personal Starting Template / Cấu hình khởi đầu cá nhân"
    assert "not a best" in template["note"]
    with _client_for_session(db_session) as client:
        applied = client.post("/api/v1/portfolio/templates/personal-starting-template/apply")
    app.dependency_overrides.clear()
    assert applied.status_code == 200
    assert applied.json()["total_weight"] <= 1

    with _client_for_session(db_session) as client:
        holding_response = client.post("/api/v1/portfolio/holdings", json={
            "symbol": "FPT", "quantity": 1, "average_cost": 100, "acquisition_date": "2025-01-01", "role": "SATELLITE",
        })
        fit = client.get("/api/v1/portfolio/fit")
    app.dependency_overrides.clear()
    assert holding_response.status_code == 201
    fit_item = fit.json()["items"][0]
    assert fit_item["portfolio_role"] == "SATELLITE"
    assert fit_item["opportunity_score"] is None
    assert fit_item["confidence"] == "INSUFFICIENT"
    assert fit_item["risk_score"] is None
    assert fit_item["factor_overlap"] == "INSUFFICIENT_DATA"
    assert fit_item["status"] == "INSUFFICIENT_DATA"


def test_portfolio_snapshot_comparison_handles_membership_and_missing_values():
    previous = {
        "holdings": [
            {"symbol": "AAA", "current_price": 100.0, "current_weight": 0.25, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2026-09-30"},
            {"symbol": "BBB", "current_price": 100.0, "current_weight": 0.2, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2026-09-30"},
            {"symbol": "CCC", "current_price": 20.0, "current_weight": 0.1, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2026-09-30"},
            {"symbol": "DDD", "current_price": None, "current_weight": None, "price_status": "INSUFFICIENT_DATA", "price_source": None, "price_as_of": None},
        ]
    }
    current = {
        "holdings": [
            {"symbol": "EEE", "current_price": 0.0, "current_weight": None, "price_status": "INSUFFICIENT_DATA", "price_source": None, "price_as_of": None},
            {"symbol": "DDD", "current_price": 0.0, "current_weight": 0.0, "price_status": "INSUFFICIENT_DATA", "price_source": None, "price_as_of": None},
            {"symbol": "BBB", "current_price": 100.00000001, "current_weight": 0.2, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2026-10-01"},
            {"symbol": "AAA", "current_price": 110.0, "current_weight": 0.2, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2026-10-01"},
        ]
    }

    changes = compare_snapshots(previous, current)
    assert changes == compare_snapshots(previous, {"holdings": list(reversed(current["holdings"]))})
    by_key = {(item["symbol"], item["kind"]): item for item in changes}

    assert by_key[("EEE", "HOLDING_ADDED")]["direction"] == "ADDED"
    assert by_key[("CCC", "HOLDING_REMOVED")]["direction"] == "REMOVED"
    assert by_key[("AAA", "PRICE_CHANGE")]["direction"] == "INCREASED"
    assert by_key[("AAA", "ALLOCATION_DRIFT")]["direction"] == "DECREASED"
    assert by_key[("BBB", "PRICE_CHANGE")]["direction"] == "UNCHANGED"
    assert by_key[("BBB", "ALLOCATION_DRIFT")]["direction"] == "UNCHANGED"
    assert by_key[("DDD", "PRICE_CHANGE")]["before"] is None
    assert by_key[("DDD", "PRICE_CHANGE")]["after"] == 0.0
    assert by_key[("DDD", "PRICE_CHANGE")]["direction"] == "DATA_AVAILABLE"
    assert by_key[("DDD", "PRICE_CHANGE")]["status"] == "INSUFFICIENT_DATA"
    assert compare_snapshots({}, {}) == []
