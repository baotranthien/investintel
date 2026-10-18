from datetime import date, timedelta
import os
import sys
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_db
from database.models import Asset, PersonalPortfolioSnapshot, Price, WatchlistItem
from routers.decision import router as decision_router
from services.decision.engine import (
    build_decision_context,
    build_portfolio_decision_view,
    capture_asset_decision_snapshot,
)
from services.portfolio.engine import PORTFOLIO_ID, ensure_portfolio


def _seed_asset(db_session, symbol=None, sector="TECHNOLOGY"):
    symbol = (symbol or f"DEC{uuid4().hex[:6].upper()}").upper()
    asset = db_session.query(Asset).filter(Asset.symbol == symbol).first()
    if asset is None:
        asset = Asset(symbol=symbol, name=f"{symbol} Corp", asset_type="STOCK", exchange="HOSE", sector=sector, status="ACTIVE")
        db_session.add(asset)
        db_session.flush()
    return asset


def test_decision_context_includes_change_reasoning_and_scenarios(db_session):
    asset = _seed_asset(db_session, "DECISION_FPT", "TECHNOLOGY")
    db_session.query(Price).filter(Price.asset_id == asset.id).delete(synchronize_session=False)
    synthetic_date = date(2035, 1, 2)
    db_session.add(Price(asset_id=asset.id, observation_date=synthetic_date, raw_close=100.0, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()

    context = build_decision_context(db_session, asset.symbol, date.today())

    assert "what_changed" in context
    assert "why_now" in context
    assert "why_not_now" in context
    assert "what_would_make_me_wrong" in context
    assert "scenario" in context
    assert set(context["scenario"]).issuperset({"bear", "base", "bull"})
    assert isinstance(context["evidence"], list)
    assert context["evidence"]
    assert context["timeline"]
    assert context["explainability"]["valuation"]["status"] in {"AVAILABLE", "INSUFFICIENT_DATA"}
    assert set(context["explainability"]).issuperset({
        "valuation", "quality", "growth", "value", "momentum", "dividend",
        "macro", "risk", "events", "opportunity", "confidence", "portfolio_fit", "portfolio_overlap",
    })
    assert set(context["snapshot"]["modules"]).issuperset({
        "fundamentals", "valuation", "factors", "macro", "regime", "risk",
        "events", "opportunity", "portfolio_fit", "portfolio",
    })
    assert context["snapshot"]["modules"]["regime"]["benchmark"]["data_origin"] in {"SEEDED_OR_UNTRACED", "STATIC_OR_SEEDED", "LINEAGED_INGESTION", None}
    assert any(item["data_origin"] == "SEEDED_OR_UNTRACED" for item in context["evidence"] if item["responsible_module"] == "events")
    assert all("claim_type" in claim for claim in context["why_now"] + context["why_not_now"])
    assert not any(claim["responsible_module"] == "events" for claim in context["why_now"])
    assert context["what_would_make_me_wrong"] == []
    assert all(context["scenario"][case]["status"] == "INSUFFICIENT_DATA" for case in ("bear", "base", "bull"))
    assert all(not context["scenario"][case]["assumptions"] for case in ("bear", "base", "bull"))
    assert all(context["scenario"][case]["claim_type"] == "UNCERTAINTY" for case in ("bear", "base", "bull"))

    db_session.add(WatchlistItem(asset_id=asset.id, invalidation="Quarterly revenue falls below the user's documented threshold."))
    db_session.commit()
    updated_context = build_decision_context(db_session, asset.symbol, date.today())
    assert updated_context["what_would_make_me_wrong"] == [{
        "type": "USER_DEFINED",
        "claim_type": "HYPOTHESIS",
        "condition": "Quarterly revenue falls below the user's documented threshold.",
        "source": "watchlist_item.invalidation",
        "evidence": [{
            "claim_type": "UNCERTAINTY",
            "source": "watchlist_item.invalidation",
            "data_origin": "USER_ENTERED_THESIS",
            "note": "User-entered invalidation rule; not independently verified by the data engines.",
        }],
    }]


def test_decision_snapshots_report_measured_price_changes(db_session):
    asset = _seed_asset(db_session, sector="TECHNOLOGY")
    db_session.query(Price).filter(Price.asset_id == asset.id).delete(synchronize_session=False)
    first_date = date(2035, 1, 2)
    db_session.add(Price(asset_id=asset.id, observation_date=first_date, raw_close=100.0, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()

    first_snapshot = capture_asset_decision_snapshot(db_session, asset.symbol, first_date)
    assert first_snapshot is not None
    db_session.commit()

    next_date = first_date + timedelta(days=1)
    db_session.add(Price(asset_id=asset.id, observation_date=next_date, raw_close=110.0, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()
    second_snapshot = capture_asset_decision_snapshot(db_session, asset.symbol, next_date)
    assert second_snapshot is not None
    db_session.commit()

    context = build_decision_context(db_session, asset.symbol, next_date)
    price_change = next(change for change in context["what_changed"] if change["metric"] == "price.value")
    assert price_change["before"] == 100.0
    assert price_change["after"] == 110.0
    assert price_change["magnitude"] == {"absolute": 10.0, "relative_pct": 10.0}
    assert price_change["responsible_module"] == "price"
    assert price_change["source"] == "CANONICAL_PRICE"
    assert price_change["date"] == next_date.isoformat()
    assert price_change["evidence"]
    assert price_change["evidence"][0]["data_origin"] == "SEEDED_OR_UNTRACED"


def test_decision_snapshot_api_contract(db_session):
    asset = _seed_asset(db_session, sector="TECHNOLOGY")
    db_session.commit()
    app = FastAPI()
    app.include_router(decision_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    captured = client.post(f"/api/v1/decision/{asset.symbol}/snapshot?as_of=2035-01-02")
    assert captured.status_code == 201
    assert captured.json()["symbol"] == asset.symbol
    assert captured.json()["as_of_date"] == "2035-01-02"

    context = client.get(f"/api/v1/decision/{asset.symbol}?as_of=2035-01-02")
    assert context.status_code == 200
    assert context.json()["snapshot"]["as_of_date"] == "2035-01-02"

    portfolio_context = client.get("/api/v1/portfolio/decision?as_of=2035-01-02")
    assert portfolio_context.status_code == 200
    assert "portfolio_changes" in portfolio_context.json()
    assert "opportunity_changes" in portfolio_context.json()
    assert "risk_changes" in portfolio_context.json()
    assert "portfolio_fit_changes" in portfolio_context.json()


def test_portfolio_decision_view_reports_drift_and_concentration(db_session):
    first = _seed_asset(db_session, "DECISION_FPT", "TECHNOLOGY")
    second = _seed_asset(db_session, "DECISION_VCB", "BANK")
    db_session.query(Price).filter(Price.asset_id.in_([first.id, second.id])).delete(synchronize_session=False)
    synthetic_base = date(2035, 2, 1)
    for offset, asset in enumerate((first, second)):
        db_session.add(Price(asset_id=asset.id, observation_date=synthetic_base - timedelta(days=offset), raw_close=100.0, source="CANONICAL_PRICE", status="VALID"))
    db_session.commit()

    view = build_portfolio_decision_view(db_session, date.today())

    assert "decision_state" in view
    assert "allocation_drift" in view
    assert "concentration" in view
    assert "opportunity_changes" in view
    assert "risk_changes" in view
    assert isinstance(view["allocation_drift"], list)
    assert all("claim_type" in item and "evidence" in item for item in view["allocation_drift"])
    assert all(item["claim_type"] == "UNCERTAINTY" for item in view["evidence"])
    assert isinstance(view["scenario"], dict)
    assert set(view["scenario"]).issuperset({"bear", "base", "bull"})


def test_portfolio_decision_view_compares_persisted_holdings_snapshots(db_session):
    ensure_portfolio(db_session)
    db_session.add_all([
        PersonalPortfolioSnapshot(portfolio_id=PORTFOLIO_ID, snapshot_data={
            "as_of_date": "2035-01-01",
            "status": "AVAILABLE",
            "holdings": [{"symbol": "AAA", "current_price": 100.0, "current_weight": 1.0, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2035-01-01"}],
        }),
        PersonalPortfolioSnapshot(portfolio_id=PORTFOLIO_ID, snapshot_data={
            "as_of_date": "2035-01-02",
            "status": "AVAILABLE",
            "holdings": [
                {"symbol": "AAA", "current_price": 110.0, "current_weight": 0.8, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2035-01-02"},
                {"symbol": "BBB", "current_price": 50.0, "current_weight": 0.2, "price_status": "AVAILABLE", "price_source": "CANONICAL", "price_as_of": "2035-01-02"},
            ],
        }),
        PersonalPortfolioSnapshot(portfolio_id=PORTFOLIO_ID, snapshot_data={
            "as_of_date": "2036-01-01",
            "status": "AVAILABLE",
            "holdings": [{"symbol": "AAA", "current_price": 999.0, "current_weight": 1.0, "price_status": "AVAILABLE", "price_source": "FUTURE", "price_as_of": "2036-01-01"}],
        }),
    ])
    db_session.commit()

    view = build_portfolio_decision_view(db_session, date(2035, 1, 2))
    by_key = {(item["symbol"], item["kind"]): item for item in view["portfolio_changes"]}

    assert by_key[("AAA", "PRICE_CHANGE")]["direction"] == "INCREASED"
    assert by_key[("AAA", "PRICE_CHANGE")]["after"] == 110.0
    assert by_key[("AAA", "PRICE_CHANGE")]["claim_type"] == "MODEL_OUTPUT"
    assert by_key[("BBB", "HOLDING_ADDED")]["claim_type"] == "FACT"
    assert by_key[("AAA", "ALLOCATION_DRIFT")]["direction"] == "DECREASED"
    assert by_key[("BBB", "HOLDING_ADDED")]["direction"] == "ADDED"
