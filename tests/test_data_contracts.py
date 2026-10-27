"""
Test Suite for InvestIntel Data Contracts Layer (Phases 2, 3, 4, 6, 7).

Ensures:
1. Price geometry, adjustment semantics, and provenance.
2. Share resolution by purpose (prevents LISTED_SHARES overriding OUTSTANDING_SHARES).
3. TTM quarterly continuity (rejection of duplicate, partial, discontinuous periods).
4. Valuation ratio zero-false-pass (no silent masking of outliers, bank EV/EBITDA blocked).
5. Invalidation graph propagation from upstream inputs to AI evidence.
"""
from datetime import date
import pytest
from pydantic import ValidationError

from services.contracts.semantic_types import (
    PriceSemantics,
    ShareType,
    StatementPeriodType,
    VerificationLevel,
    PriceContract,
)
from services.contracts.validators import (
    validate_price_payload,
    resolve_shares_by_purpose,
    validate_quarterly_continuity,
    validate_valuation_ratio,
)
from services.contracts.invalidation import (
    DataDependencyGraph,
    DependencyNodeType,
    NodeState,
)
from services.fundamentals.engine import TTMEngine


# ============================================================================
# 1. Price Contract Tests
# ============================================================================

def test_price_contract_valid_payload():
    payload = {
        "symbol": "FPT",
        "observation_date": "2026-03-27",
        "open": 110000.0,
        "high": 115000.0,
        "low": 109000.0,
        "close": 112000.0,
        "adjusted_close": 112000.0,
        "volume": 2500000,
        "provider": "VNDIRECT",
    }
    contract = validate_price_payload(payload)
    assert contract.symbol == "FPT"
    assert contract.raw_close == 112000.0
    assert contract.price_semantics == PriceSemantics.RAW_UNADJUSTED


def test_price_contract_rejects_inverted_geometry():
    payload = {
        "symbol": "HPG",
        "observation_date": "2026-03-27",
        "open": 28000.0,
        "high": 27000.0,  # Invalid: high < low
        "low": 29000.0,
        "close": 28500.0,
    }
    with pytest.raises(ValidationError, match="High cannot be less than Low"):
        validate_price_payload(payload)


def test_price_contract_rejects_non_positive_close():
    payload = {
        "symbol": "VCB",
        "observation_date": "2026-03-27",
        "close": -100.0,
    }
    with pytest.raises(ValidationError, match="raw_close must be strictly positive"):
        validate_price_payload(payload)


def test_price_contract_preserves_dividend_adjusted_semantics():
    payload = {
        "symbol": "VNM",
        "observation_date": "2026-03-27",
        "close": 68000.0,
        "is_adjusted_series": True,
        "provider": "LOTUS",
    }
    contract = validate_price_payload(payload)
    assert contract.price_semantics == PriceSemantics.DIVIDEND_ADJUSTED


# ============================================================================
# 2. Share Resolution Tests (Regression Prevention)
# ============================================================================

def test_share_resolution_outstanding_overrides_newer_listed():
    """
    CRITICAL REGRESSION: A newer LISTED_SHARES record must NOT override a valid
    OUTSTANDING_SHARES record for valuation purposes.
    """
    records = [
        {
            "symbol": "FPT",
            "metric_id": "LISTED_SHARES",
            "value": 1_200_000_000,
            "fiscal_period_end": date(2026, 3, 1),
            "source_authority": "EXCHANGE",
        },
        {
            "symbol": "FPT",
            "metric_id": "OUTSTANDING_SHARES",
            "value": 1_460_000_000,
            "fiscal_period_end": date(2025, 12, 31),
            "source_authority": "AUDITED_REPORT",
        },
    ]

    res = resolve_shares_by_purpose(records, purpose="market_valuation")
    assert res is not None
    assert res.share_count == 1_460_000_000
    assert res.share_type == ShareType.OUTSTANDING_CURRENT
    assert res.source_metric_id == "OUTSTANDING_SHARES"
    assert not res.conflict_detected


def test_share_resolution_conflicting_shares_detected():
    """Detects conflicting values for OUTSTANDING_SHARES on same period."""
    records = [
        {
            "symbol": "HPG",
            "metric_id": "OUTSTANDING_SHARES",
            "value": 5_800_000_000,
            "fiscal_period_end": date(2025, 12, 31),
        },
        {
            "symbol": "HPG",
            "metric_id": "OUTSTANDING_SHARES",
            "value": 6_400_000_000,
            "fiscal_period_end": date(2025, 12, 31),
        },
    ]
    res = resolve_shares_by_purpose(records, purpose="market_valuation")
    assert res is not None
    assert res.conflict_detected is True
    assert res.verification_level == VerificationLevel.CONFLICTING_DATA


def test_share_resolution_charter_capital_fallback_labeled_as_estimate():
    """Deriving shares from charter capital is explicitly an estimate."""
    res = resolve_shares_by_purpose([], purpose="market_valuation", bal_share_capital=10_000_000_000)
    assert res is not None
    assert res.is_estimate is True
    assert res.share_type == ShareType.CHARTER_CAPITAL_ESTIMATE
    assert res.verification_level == VerificationLevel.MATHEMATICALLY_CALCULATED


# ============================================================================
# 3. TTM Continuity & Period Normalization Tests
# ============================================================================

def test_validate_quarterly_continuity_four_consecutive():
    quarters = [
        {"fiscal_year": 2025, "fiscal_quarter": 1, "fiscal_period_end": date(2025, 3, 31)},
        {"fiscal_year": 2025, "fiscal_quarter": 2, "fiscal_period_end": date(2025, 6, 30)},
        {"fiscal_year": 2025, "fiscal_quarter": 3, "fiscal_period_end": date(2025, 9, 30)},
        {"fiscal_year": 2025, "fiscal_quarter": 4, "fiscal_period_end": date(2025, 12, 31)},
    ]
    valid, reason, last_4 = validate_quarterly_continuity(quarters)
    assert valid is True
    assert reason == "OK"
    assert len(last_4) == 4


def test_validate_quarterly_continuity_rejects_insufficient_quarters():
    quarters = [
        {"fiscal_year": 2025, "fiscal_quarter": 1, "fiscal_period_end": date(2025, 3, 31)},
        {"fiscal_year": 2025, "fiscal_quarter": 2, "fiscal_period_end": date(2025, 6, 30)},
    ]
    valid, reason, _ = validate_quarterly_continuity(quarters)
    assert valid is False
    assert "need 4" in reason


def test_validate_quarterly_continuity_rejects_duplicate_quarters():
    quarters = [
        {"fiscal_year": 2025, "fiscal_quarter": 1, "fiscal_period_end": date(2025, 3, 31)},
        {"fiscal_year": 2025, "fiscal_quarter": 2, "fiscal_period_end": date(2025, 6, 30)},
        {"fiscal_year": 2025, "fiscal_quarter": 3, "fiscal_period_end": date(2025, 9, 30)},
        {"fiscal_year": 2025, "fiscal_quarter": 3, "fiscal_period_end": date(2025, 9, 30)},  # Duplicate
    ]
    valid, reason, _ = validate_quarterly_continuity(quarters)
    assert valid is False
    assert "Duplicate" in reason


def test_validate_quarterly_continuity_rejects_discontinuous_quarters():
    quarters = [
        {"fiscal_year": 2025, "fiscal_quarter": 1, "fiscal_period_end": date(2025, 3, 31)},
        {"fiscal_year": 2025, "fiscal_quarter": 2, "fiscal_period_end": date(2025, 6, 30)},
        {"fiscal_year": 2025, "fiscal_quarter": 3, "fiscal_period_end": date(2025, 9, 30)},
        {"fiscal_year": 2026, "fiscal_quarter": 2, "fiscal_period_end": date(2026, 6, 30)},  # Gap: missing 2025 Q4 / 2026 Q1
    ]
    valid, reason, _ = validate_quarterly_continuity(quarters)
    assert valid is False
    assert "Discontinuous" in reason


def test_ttm_engine_rejects_partial_sums():
    """
    CRITICAL: TTMEngine must NOT sum partial quarters (e.g. 3 quarters)
    into a 12-month TTM flow item!
    """
    quarters = [
        {"revenue": 100.0, "net_income": 20.0, "fiscal_period_end": date(2025, 3, 31)},
        {"revenue": 120.0, "net_income": 25.0, "fiscal_period_end": date(2025, 6, 30)},
        {"revenue": 110.0, "net_income": 22.0, "fiscal_period_end": date(2025, 9, 30)},
        {"revenue": None, "net_income": None, "fiscal_period_end": date(2025, 12, 31)},  # 4th quarter missing revenue/income
    ]
    ttm = TTMEngine.compute_ttm_income(quarters)
    # Must be None, NOT sum(100+120+110) = 330!
    assert ttm.get("revenue") is None
    assert ttm.get("net_income") is None


# ============================================================================
# 4. Valuation Multiples & Outlier Zero-False-Pass Tests
# ============================================================================

def test_valuation_ratio_outlier_not_masked_into_fallback():
    """
    CRITICAL: Outlier ratio (e.g. price 100,000 / EPS 10 = PE 10,000)
    must NOT be masked into fallback_val (e.g. 15.0).
    It must be reported as CONFLICTING_DATA with diagnostic reasoning.
    """
    result = validate_valuation_ratio(
        price=100000.0,
        denominator=10.0,
        metric_id="pe",
        fallback_val=15.0,
    )
    assert result.is_outlier is True
    assert result.value == 10000.0
    assert result.verification_level == VerificationLevel.CONFLICTING_DATA
    assert result.status == "CONFLICTING_DATA"
    assert "outlier" in result.diagnostic_note.lower()


def test_valuation_ratio_blocks_ev_ebitda_for_banks():
    """Blocks EV/EBITDA calculation for banking sector."""
    result = validate_valuation_ratio(
        price=90000.0,
        denominator=5000.0,
        metric_id="ev_ebitda",
        sector="BANK",
    )
    assert result.status == "NOT_APPLICABLE"
    assert result.verification_level == VerificationLevel.NOT_APPLICABLE
    assert "banking" in result.diagnostic_note.lower()


def test_valuation_ratio_handles_negative_denominator():
    result = validate_valuation_ratio(
        price=50000.0,
        denominator=-2000.0,
        metric_id="pe",
    )
    assert result.status == "NOT_MEANINGFUL"
    assert result.verification_level == VerificationLevel.NOT_APPLICABLE


# ============================================================================
# 5. Dependency Invalidation Graph Tests
# ============================================================================

def test_dependency_invalidation_propagation():
    graph = DataDependencyGraph()

    # Initially valid
    assert graph.is_publishable("FPT", DependencyNodeType.AI_ANALYSIS)[0] is True

    # Invalidate upstream INCOME_STATEMENT
    event = graph.invalidate_dependents(
        symbol="FPT",
        trigger_input=DependencyNodeType.INCOME_STATEMENT,
        reason="Audited restatement for Q3 2025 received.",
    )

    # Downstream metrics must be invalidated
    assert DependencyNodeType.TTM_INCOME in event.invalidated_nodes
    assert DependencyNodeType.EPS_TTM in event.invalidated_nodes
    assert DependencyNodeType.PE_RATIO in event.invalidated_nodes
    assert DependencyNodeType.AI_EVIDENCE in event.invalidated_nodes
    assert DependencyNodeType.AI_ANALYSIS in event.invalidated_nodes

    # AI_ANALYSIS and PE_RATIO cannot be published
    can_pub_ai, reason_ai = graph.is_publishable("FPT", DependencyNodeType.AI_ANALYSIS)
    assert can_pub_ai is False
    assert "INVALIDATED" in reason_ai

    can_pub_pe, reason_pe = graph.is_publishable("FPT", DependencyNodeType.PE_RATIO)
    assert can_pub_pe is False
    assert "INVALIDATED" in reason_pe
