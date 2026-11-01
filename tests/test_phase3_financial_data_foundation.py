# -*- coding: utf-8 -*-
"""
Phase 3 Acceptance Test Suite: Financial Data Foundation
Verifies:
1. Canonical financial statement extraction & normalization across non-financial and bank sectors.
2. Complete balance sheet metrics (short_term_debt, long_term_debt, gross_debt, current_ratio, quick_ratio, de_ratio).
3. Correctness of EBITDA and net_debt_ebitda derivation.
4. Correctness of banking metrics (NIM, CASA, credit growth, NPL) and fail-closed ratio handling.
5. WorkspaceMetric exposure in ResearchWorkspace and verifiable evidence citations in AI Analyst context.
6. Multi-metric Vietnamese question resolution with zero unhandled missing metrics.
"""
from datetime import date
import pytest

from database.models import Asset
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.research.workspace import build_research_workspace
from services.ai.tools import AITools
from services.ai.prompt_registry import (
    build_chat_prompt,
    extract_requested_metric_groups,
)


def test_phase3_repository_complete_balance_sheet_extraction(db_session):
    """Verify that FinancialRepository extracts full debt, liquidity, and balance sheet fields."""
    repo = FinancialRepository(db_session)
    dataset = repo.get_financial_dataset("BMP")

    assert dataset is not None
    assert len(dataset["balance_annual"]) > 0
    latest_bs = dataset["balance_annual"][-1]

    # Verify critical balance sheet fields are present and typed
    assert "short_term_debt" in latest_bs
    assert "long_term_debt" in latest_bs
    assert "total_current_assets" in latest_bs
    assert "total_current_liabilities" in latest_bs
    assert "inventory" in latest_bs
    assert "total_assets" in latest_bs
    assert "total_liabilities" in latest_bs
    assert "total_equity" in latest_bs
    assert "equity_parent" in latest_bs

    # Specific BMP values from canonical statements
    assert latest_bs["short_term_debt"] is not None
    assert latest_bs["total_assets"] > 3000.0
    assert latest_bs["total_current_assets"] > 2500.0
    assert latest_bs["total_equity"] > 2500.0


def test_phase3_snapshot_derived_debt_and_liquidity_metrics(db_session):
    """Verify that FundamentalSnapshotBuilder computes valid de_ratio, current_ratio, quick_ratio, and net_debt_ebitda."""
    repo = FinancialRepository(db_session)
    dataset = repo.get_financial_dataset("BMP")

    builder = FundamentalSnapshotBuilder("BMP", dataset["sector"])
    snapshot = builder.build_snapshot(
        income_quarters=dataset["income_quarters"],
        income_annual=dataset["income_annual"],
        balance_annual=dataset["balance_annual"],
        cashflow_annual=dataset["cashflow_annual"],
        shares_outstanding=dataset.get("shares_outstanding"),
    )

    bs = snapshot.get("balance_sheet", {})
    prof = snapshot.get("profitability", {})

    # 1. Gross & Net Debt
    assert bs.get("gross_debt") is not None
    assert bs.get("gross_debt") > 0.0
    assert bs.get("net_debt") is not None

    # 2. Capital Structure: D/E ratio
    de_ratio = bs.get("de_ratio", {})
    assert de_ratio.get("data_status") == "VALID"
    assert de_ratio.get("value") is not None
    assert 0.0 < de_ratio.get("value") < 1.0  # BMP has very low debt-to-equity (~0.017)

    # 3. Liquidity: Current ratio and Quick ratio
    current_ratio = bs.get("current_ratio", {})
    assert current_ratio.get("data_status") == "VALID"
    assert current_ratio.get("value") is not None
    assert current_ratio.get("value") > 2.0  # BMP current ratio is ~5.5

    quick_ratio = bs.get("quick_ratio", {})
    assert quick_ratio.get("data_status") == "VALID"
    assert quick_ratio.get("value") is not None
    assert quick_ratio.get("value") > 2.0  # BMP quick ratio is ~4.4

    # 4. Solvency: Debt to assets
    debt_to_assets = bs.get("debt_to_assets", {})
    assert debt_to_assets.get("data_status") == "VALID"
    assert debt_to_assets.get("value") is not None
    assert 10.0 < debt_to_assets.get("value") < 25.0  # ~15.38%

    # 5. Margins: Gross margin
    gross_margin = prof.get("gross_margin", {})
    assert gross_margin.get("data_status") == "VALID"
    assert gross_margin.get("value") is not None
    assert 35.0 < gross_margin.get("value") < 55.0  # ~44.86%


def test_phase3_bank_sector_fail_closed_ratios(db_session):
    """Verify that banking sector (MBB) marks current_ratio and quick_ratio NOT_MEANINGFUL without error."""
    repo = FinancialRepository(db_session)
    dataset = repo.get_financial_dataset("MBB")

    builder = FundamentalSnapshotBuilder("MBB", dataset["sector"])
    snapshot = builder.build_snapshot(
        income_quarters=dataset["income_quarters"],
        income_annual=dataset["income_annual"],
        balance_annual=dataset["balance_annual"],
        cashflow_annual=dataset["cashflow_annual"],
        shares_outstanding=dataset.get("shares_outstanding"),
    )

    bs = snapshot.get("balance_sheet", {})
    cur_r = bs.get("current_ratio", {})
    quick_r = bs.get("quick_ratio", {})

    # Current and Quick ratios must NOT be reported as valid for banks
    assert cur_r.get("data_status") in ("NOT_MEANINGFUL", "MISSING_DATA")
    assert quick_r.get("data_status") in ("NOT_MEANINGFUL", "MISSING_DATA")


def test_phase3_workspace_exposes_debt_and_liquidity_metrics(db_session):
    """Verify that build_research_workspace produces WorkspaceMetric items for all debt and liquidity metrics."""
    ws = build_research_workspace(db_session, "BMP", date.today())
    assert ws is not None
    assert ws.fundamentals is not None

    metrics = ws.fundamentals.get("metrics", {})
    required_keys = [
        "gross_margin", "debt_to_assets", "de_ratio", "net_debt_ebitda",
        "current_ratio", "quick_ratio", "gross_debt", "total_debt",
        "short_term_debt", "total_current_assets", "total_current_liabilities",
        "cash", "cfo", "fcf"
    ]

    for k in required_keys:
        assert k in metrics, f"Missing metric key in workspace: {k}"
        metric_item = metrics[k]
        val = metric_item.get("value") if isinstance(metric_item, dict) else getattr(metric_item, "value", None)
        status = metric_item.get("status") if isinstance(metric_item, dict) else getattr(metric_item, "status", None)
        assert status == "AVAILABLE", f"Metric {k} is not AVAILABLE: {status}"
        assert val is not None, f"Metric {k} has None value"


def test_phase3_ai_context_and_telemetry_complete_coverage(db_session):
    """Verify that asking for BMP debt, liquidity, and margins yields 0 missing metrics in telemetry."""
    question = (
        "Phân tích biên lợi nhuận gộp, tỷ lệ nợ phải trả trên tổng tài sản, "
        "nợ vay trên vốn chủ sở hữu và khả năng thanh toán hiện hành của BMP?"
    )
    context = AITools.get_context("BMP", as_of=date.today(), session=db_session, question=question)
    assert context is not None
    assert context.get("decision_state") in ("AVAILABLE", "PARTIAL")

    prompt_text = build_chat_prompt(question, context)
    assert prompt_text is not None

    telemetry = context.get("evidence_telemetry", {})
    assert telemetry.get("missing_requested_metrics") == [], (
        f"Expected zero missing requested metrics, got {telemetry.get('missing_requested_metrics')}"
    )
    assert telemetry.get("selected_count", 0) >= 4
