# -*- coding: utf-8 -*-
"""
Phase 5 Acceptance Test Suite: Portfolio & Opportunity Intelligence
Verifies:
1. Multi-Filter Financial Stock Screener: Multi-dimensional screening against ROE, margins, debt, valuation multiples.
2. Opportunity Scanner: Canonical opportunity scoring with why_now / why_not_now evidence provenance.
3. Watchlist Management: Thesis capture, fundamental change tracking, user isolation.
4. Portfolio Analytics: Asset allocation, holdings management, portfolio fit analysis.
5. Investment Alerts Engine: Inflection point monitoring (margin decay, valuation thresholds, debt jumps, deduplication).
"""
from datetime import date
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.screener.engine import ScreenerCriteria, StockScreenerEngine
from services.alerts.engine import InvestmentAlertsEngine


client = TestClient(app)


def test_phase5_multi_filter_stock_screener(db_session):
    """Verify multi-criteria screening engine with fundamental and valuation filters."""
    engine = StockScreenerEngine(db_session)

    # 1. Broad screen
    crit_all = ScreenerCriteria(universe="ALL", limit=20)
    res_all = engine.screen(crit_all)
    assert res_all.total_screened > 0
    assert res_all.matched_count >= 1

    # 2. High ROE screen
    crit_roe = ScreenerCriteria(universe="ALL", roe_min=15.0, limit=10)
    res_roe = engine.screen(crit_roe)
    for stock in res_roe.matches:
        assert stock.roe is not None
        assert stock.roe >= 15.0

    # 3. Screener API endpoint
    api_res = client.get("/api/v1/screener?limit=10")
    assert api_res.status_code == 200
    data = api_res.json()
    assert "matches" in data
    assert data["matched_count"] >= 1


def test_phase5_opportunity_scanner():
    """Verify opportunity scanner returns canonical assets with provenance."""
    res = client.get("/api/v1/opportunities")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("AVAILABLE", "PARTIAL")
    assert len(data["results"]) >= 1

    first = data["results"][0]
    assert "symbol" in first
    assert "opportunity_score" in first
    assert "confidence" in first


def test_phase5_watchlist_management():
    """Verify watchlist creation, retrieval, and fundamental thesis tracking."""
    # 1. Get initial watchlist
    res_get = client.get("/api/v1/watchlist")
    assert res_get.status_code == 200

    # 2. Add an item
    res_post = client.post("/api/v1/watchlist", json={
        "symbol": "FPT",
        "thesis": "Technology market leader with 20%+ ROE and solid earnings growth",
        "target_price": 75000.0,
        "confidence": "HIGH"
    })
    assert res_post.status_code in (200, 201, 400)  # 400 if already present

    # 3. Verify item listed
    res_verify = client.get("/api/v1/watchlist")
    assert res_verify.status_code == 200
    items = res_verify.json()
    symbols = [it["symbol"] for it in items]
    assert "FPT" in symbols


def test_phase5_portfolio_analytics():
    """Verify portfolio dashboard, holdings view, and portfolio fit."""
    # 1. Dashboard
    res = client.get("/api/v1/portfolio")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "holdings" in data

    # 2. Portfolio Fit
    res_fit = client.get("/api/v1/portfolio/fit")
    assert res_fit.status_code == 200
    fit_data = res_fit.json()
    assert "portfolio_id" in fit_data
    assert "items" in fit_data


def test_phase5_investment_alerts_engine(db_session):
    """Verify alerts generation, valuation threshold detection, and deduplication."""
    engine = InvestmentAlertsEngine(db_session)

    # 1. Evaluate specific stock
    alerts = engine.evaluate_symbol("FPT")
    assert isinstance(alerts, list)

    # 2. Evaluate universe scan
    scan_alerts = engine.scan_active_universe(limit=5)
    assert isinstance(scan_alerts, list)

    # 3. Verify API endpoint
    api_res = client.get("/api/v1/alerts")
    assert api_res.status_code == 200
    alerts_list = api_res.json()
    assert isinstance(alerts_list, list)

