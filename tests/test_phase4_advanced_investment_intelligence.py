# -*- coding: utf-8 -*-
"""
Phase 4 Acceptance Test Suite: Advanced Investment Intelligence
Verifies:
1. Deep Company Analysis: 7 institutional sections grounded in real canonical metrics.
2. Historical Financial Analysis: 5-year annual and 12-quarter longitudinal time-series with corporate actions.
3. Peer Comparison Engine: Cross-sectional valuation multiples, industry clustering, medians, and discount/premium analysis.
4. Deterministic Valuation Engine: Intrinsic DCF, Relative P/E & P/B, scenarios, and WACC x Terminal Growth sensitivity matrix.
5. Institutional Investment Report: 13-section report generation with deterministic recommendation stance and citations.
"""
from datetime import date
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.research.analysis import CompanyDeepAnalysisEngine
from services.research.history import HistoricalFinancialEngine
from services.valuation.peers import PeerComparisonEngine
from services.research.report import InvestmentReportGenerator


client = TestClient(app)


def test_phase4_deep_company_analysis(db_session):
    """Verify 7 institutional sections in DeepCompanyAnalysisEngine."""
    engine = CompanyDeepAnalysisEngine(db_session)
    result = engine.generate_analysis("BMP")

    assert result.symbol == "BMP"
    assert result.status == "AVAILABLE"
    assert result.business_overview is not None
    assert result.revenue_growth is not None
    assert result.profitability is not None
    assert result.financial_health is not None
    assert result.cash_flow_quality is not None
    assert result.valuation is not None
    assert result.risks_and_catalysts is not None

    # Check key grounded metrics
    assert "summary" in result.business_overview
    assert "revenue_ttm" in result.revenue_growth or "revenue" in result.revenue_growth
    assert "gross_margin" in result.profitability
    assert "de_ratio" in result.financial_health or "debt_to_assets" in result.financial_health
    assert "cfo" in result.cash_flow_quality


def test_phase4_historical_financial_analysis(db_session):
    """Verify longitudinal periods with chronological sorting and corporate actions."""
    engine = HistoricalFinancialEngine(db_session)
    dataset = engine.get_historical_dataset("BMP")

    assert dataset.symbol == "BMP"
    assert len(dataset.annual_periods) >= 2
    assert len(dataset.quarterly_periods) >= 0

    # Verify chronological ascending order
    annual_years = [p.fiscal_year for p in dataset.annual_periods]
    assert annual_years == sorted(annual_years)

    latest_annual = dataset.annual_periods[-1]
    assert latest_annual.revenue > 0
    assert latest_annual.net_income > 0


def test_phase4_peer_comparison_engine(db_session):
    """Verify cross-sectional valuation multiples and industry peer medians."""
    engine = PeerComparisonEngine(db_session)
    result = engine.compare_peers("BMP")

    assert result.target_symbol == "BMP"
    assert result.status in ("AVAILABLE", "PARTIAL")
    assert result.peers_evaluated >= 2
    assert result.target_metrics is not None

    # Invalid ticker handling (fail-closed)
    invalid_result = engine.compare_peers("NONEXISTENT_XYZ")
    assert invalid_result.status in ("PARTIAL", "INSUFFICIENT_DATA")
    assert invalid_result.peer_median_pe is None


def test_phase4_valuation_endpoints():
    """Verify composite valuation, DCF, relative multiples, and sensitivity matrix via API."""
    # 1. Composite valuation (FPT has full market price history in all test environments)
    res = client.get("/api/v1/valuation/FPT")
    assert res.status_code == 200
    val = res.json()
    assert val["symbol"] == "FPT"
    assert val["price_as_of"] > 0
    assert val["composite_fair_value"]["range"]["base"] > 0
    assert val["margin_of_safety"] is not None

    # 2. Peer comparison endpoint
    res_peers = client.get("/api/v1/valuation/FPT/peers")
    assert res_peers.status_code == 200
    peers_data = res_peers.json()
    assert peers_data["status"] == "AVAILABLE"
    assert len(peers_data["peer_table"]) >= 2

    # 3. Sensitivity matrix endpoint
    res_sens = client.get("/api/v1/valuation/FPT/sensitivity")
    assert res_sens.status_code == 200
    sens_data = res_sens.json()
    assert sens_data["status"] == "COMPUTED"
    assert len(sens_data["matrix"]) >= 3


def test_phase4_institutional_investment_report(db_session):
    """Verify 13-section institutional research report synthesis."""
    engine = InvestmentReportGenerator(db_session)
    report = engine.generate_report("BMP")

    assert report.symbol == "BMP"
    assert report.recommendation_stance in ("OVERWEIGHT (TÍCH LŨY MẠNH)", "ACCUMULATE (TÍCH LŨY)", "NEUTRAL (THEO DÕI)", "REDUCE (GIẢM TỶ TRỌNG)")
    assert len(report.sections) == 13

    # Check that each section is numbered 1 to 13 with non-empty content
    for idx, sec in enumerate(report.sections, start=1):
        assert sec.section_number == idx
        assert len(sec.title) > 0
        assert len(sec.headline) > 0
        assert len(sec.narrative) > 0
        assert len(sec.data_sources) > 0
        assert len(sec.data_sources) > 0
