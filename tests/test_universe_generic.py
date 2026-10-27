"""
Phase 10: Universe-Generic Financial Correctness, Invariants, and Dynamic Auditing Tests.

Proves that:
1. Arbitrary new symbols (equities, ETFs, indices) dynamically enter audits and calculations
   without editing audit code or maintaining symbol whitelists.
2. Invariants (shares priority, TTM continuity, fail-closed negative denominators, price geometry)
   hold uniformly for any security.
3. Invalidation graph tracks upstream changes and blocks publishing invalidated derived metrics.
"""
from datetime import date
import pytest
from sqlalchemy.orm import Session

from database.models import (
    Asset,
    Price,
    FinancialStatement,
    NormalizedIncome,
    NormalizedBalanceSheet,
    FundamentalMetric,
)
from services.contracts.invalidation import invalidation_graph, DependencyNodeType, NodeState
from services.fundamentals.engine import TTMEngine
from services.fundamentals.repository import FinancialRepository
from services.quality.reconciliation import audit_dynamic_universe
from services.research.workspace import build_research_workspace


def test_synthetic_new_equity_dynamic_audit(db_session: Session):
    """
    Creating a brand-new synthetic equity not in any whitelist automatically enters
    the dynamic audit, verifies 4 quarters of continuous TTM, computes exact EPS/PE/PB,
    and assigns the appropriate validation tier.
    """
    sym = "SYNTH999"
    # 1. Register canonical asset
    asset = Asset(
        symbol=sym,
        name="Synthetic Tech Corporation",
        asset_type="STOCK",
        exchange="HOSE",
        sector="TECHNOLOGY",
        status="ACTIVE",
    )
    db_session.add(asset)
    db_session.flush()

    # 2. Add canonical price (30,000 VND)
    price = Price(
        asset_id=asset.id,
        observation_date=date(2026, 10, 24),
        raw_open=29500.0,
        raw_high=30500.0,
        raw_low=29000.0,
        raw_close=30000.0,
        adjusted_close=30000.0,
        adjustment_factor=1.0,
        volume=1_000_000.0,
        source="MOCK_PROVIDER",
        status="VALID",
    )
    db_session.add(price)

    # 3. Add 4 non-overlapping consecutive quarters of financial statements
    quarters = [
        (date(2025, 12, 31), 2025, 4, 50.0),   # 50B VND net income
        (date(2026, 3, 31), 2026, 1, 60.0),    # 60B VND net income
        (date(2026, 6, 30), 2026, 2, 70.0),    # 70B VND net income
        (date(2026, 9, 30), 2026, 3, 80.0),    # 80B VND net income
    ]
    for fend, fyear, fq, ni_billions in quarters:
        stmt = FinancialStatement(
            asset_id=asset.id,
            symbol=sym,
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=fend,
            fiscal_year=fyear,
            fiscal_quarter=fq,
            period_type="QUARTERLY",
            statement_date=fend,
            publication_date=fend,
            consolidation="CONSOLIDATED",
            currency="VND",
            unit_scale="BILLION_VND",
            version=1,
            status="VALID",
        )
        db_session.add(stmt)
        db_session.flush()
        db_session.add(
            NormalizedIncome(
                statement_id=stmt.id,
                symbol=sym,
                fiscal_period_end=fend,
                fiscal_year=fyear,
                fiscal_quarter=fq,
                period_type="QUARTERLY",
                revenue=ni_billions * 5.0,
                net_income=ni_billions,
            )
        )

    # Latest balance sheet with 1,500 Billion VND equity
    bs_stmt = FinancialStatement(
        asset_id=asset.id,
        symbol=sym,
        statement_type="BALANCE_SHEET",
        fiscal_period_end=date(2026, 9, 30),
        fiscal_year=2026,
        fiscal_quarter=3,
        period_type="QUARTERLY",
        statement_date=date(2026, 9, 30),
        publication_date=date(2026, 9, 30),
        currency="VND",
        unit_scale="BILLION_VND",
        version=1,
        status="VALID",
    )
    db_session.add(bs_stmt)
    db_session.flush()
    db_session.add(
        NormalizedBalanceSheet(
            statement_id=bs_stmt.id,
            symbol=sym,
            fiscal_period_end=date(2026, 9, 30),
            fiscal_year=2026,
            fiscal_quarter=3,
            period_type="QUARTERLY",
            total_assets=3000.0,
            total_equity=1500.0,
        )
    )

    # 4. Add shares outstanding: 100,000,000 shares
    db_session.add(
        FundamentalMetric(
            symbol=sym,
            metric_id="OUTSTANDING_SHARES",
            value=100_000_000.0,
            fiscal_period_end=date(2026, 9, 30),
            period_type="QUARTERLY",
            calculation_version="verified_outstanding_v1",
        )
    )
    db_session.commit()

    # 5. Run the generic dynamic audit
    audit = audit_dynamic_universe(db_session, as_of=date(2026, 10, 24))

    # Assert total equities count increased dynamically
    assert audit["universe_summary"]["total_active_equities"] >= 31
    recon = audit["reconciliation"]

    # Verify that SYNTH999 entered the mathematical calculation cohort
    all_cohorts = (
        recon["mathematically_calculated_cohort"]
        + recon["source_reconciled_cohort"]
        + recon["independently_verified_cohort"]
        + recon["conflicting_cohort"]
        + recon["insufficient_cohort"]
    )
    assert sym in all_cohorts, f"{sym} must be discovered and audited dynamically"
    assert sym in recon["mathematically_calculated_cohort"] or sym in recon["source_reconciled_cohort"]

    # 6. Verify via workspace that exact ratios match formula
    ws = build_research_workspace(db_session, sym, as_of=date(2026, 10, 24))
    pe_m = ws.valuation["metrics"]["pe"]
    pb_m = ws.valuation["metrics"]["pb"]

    pe_val = pe_m.get("value") if isinstance(pe_m, dict) else pe_m.value
    pe_status = pe_m.get("status") if isinstance(pe_m, dict) else pe_m.status
    pe_v_level = pe_m.get("verification_level") if isinstance(pe_m, dict) else pe_m.verification_level

    pb_val = pb_m.get("value") if isinstance(pb_m, dict) else pb_m.value
    pb_status = pb_m.get("status") if isinstance(pb_m, dict) else pb_m.status
    pb_v_level = pb_m.get("verification_level") if isinstance(pb_m, dict) else pb_m.verification_level

    # EPS TTM = (50+60+70+80) * 1e9 / 100M = 2,600 VND/share
    # P/E = 30,000 / 2,600 = 11.54
    assert pe_val == pytest.approx(11.54, abs=0.02)
    assert pe_status == "AVAILABLE"
    assert pe_v_level == "MATHEMATICALLY_CALCULATED"

    # BVPS = 1,500 * 1e9 / 100M = 15,000 VND/share
    # P/B = 30,000 / 15,000 = 2.0
    assert pb_val == pytest.approx(2.0, abs=0.01)
    assert pb_status == "AVAILABLE"
    assert pb_v_level == "MATHEMATICALLY_CALCULATED"


def test_synthetic_etf_contract_validation(db_session: Session):
    """
    An ETF asset automatically receives ETF-specific contracts (price geometry, volume)
    and is never penalized for lacking corporate financial statements.
    """
    sym = "ETF999"
    asset = Asset(
        symbol=sym,
        name="Synthetic Diamond ETF",
        asset_type="ETF",
        exchange="HOSE",
        status="ACTIVE",
    )
    db_session.add(asset)
    db_session.flush()

    price = Price(
        asset_id=asset.id,
        observation_date=date(2026, 10, 24),
        raw_open=21000.0,
        raw_high=21500.0,
        raw_low=20800.0,
        raw_close=21200.0,
        adjusted_close=21200.0,
        adjustment_factor=1.0,
        volume=500_000.0,
        source="MOCK_ETF",
        status="VALID",
    )
    db_session.add(price)
    db_session.commit()

    audit = audit_dynamic_universe(db_session, as_of=date(2026, 10, 24))
    assert audit["universe_summary"]["total_active_etfs"] >= 2
    etf_records = [item for item in audit["non_equity_assets"] if item["symbol"] == sym]
    assert len(etf_records) == 1
    etf_item = etf_records[0]
    assert etf_item["asset_type"] == "ETF"
    assert etf_item["price_present"] is True
    assert etf_item["geometry_valid"] is True


def test_synthetic_index_contract_validation(db_session: Session):
    """
    An Index asset automatically receives Index-specific contracts (candle completeness, freshness).
    """
    sym = "IDX999"
    asset = Asset(
        symbol=sym,
        name="Synthetic Tech Index",
        asset_type="INDEX",
        exchange="HOSE",
        status="ACTIVE",
    )
    db_session.add(asset)
    db_session.flush()

    price = Price(
        asset_id=asset.id,
        observation_date=date(2026, 10, 24),
        raw_open=1200.0,
        raw_high=1215.0,
        raw_low=1195.0,
        raw_close=1210.0,
        adjusted_close=1210.0,
        adjustment_factor=1.0,
        volume=10_000_000.0,
        source="MOCK_INDEX",
        status="VALID",
    )
    db_session.add(price)
    db_session.commit()

    audit = audit_dynamic_universe(db_session, as_of=date(2026, 10, 24))
    assert audit["universe_summary"]["total_active_indices"] >= 4
    idx_records = [item for item in audit["non_equity_assets"] if item["symbol"] == sym]
    assert len(idx_records) == 1
    idx_item = idx_records[0]
    assert idx_item["asset_type"] == "INDEX"
    assert idx_item["price_present"] is True
    assert idx_item["geometry_valid"] is True


def test_negative_earnings_fail_closed_for_arbitrary_symbol(db_session: Session):
    """
    If a company suffers losses (net income < 0), P/E must be NOT_MEANINGFUL / NOT_APPLICABLE.
    A positive provider fallback must NEVER mask the negative denominator or claim verification.
    """
    sym = "LOSS888"
    asset = Asset(
        symbol=sym,
        name="Loss-making Industrial Corp",
        asset_type="STOCK",
        exchange="HOSE",
        sector="MATERIALS",
        status="ACTIVE",
    )
    db_session.add(asset)
    db_session.flush()

    price = Price(
        asset_id=asset.id,
        observation_date=date(2026, 10, 24),
        raw_close=15000.0,
        adjusted_close=15000.0,
        adjustment_factor=1.0,
        status="VALID",
    )
    db_session.add(price)

    # 4 quarters of losses
    for i, fend in enumerate([date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30)]):
        stmt = FinancialStatement(
            asset_id=asset.id,
            symbol=sym,
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=fend,
            fiscal_year=2025 if i == 0 else 2026,
            fiscal_quarter=4 if i == 0 else i,
            period_type="QUARTERLY",
            statement_date=fend,
            publication_date=fend,
            consolidation="CONSOLIDATED",
            currency="VND",
            unit_scale="BILLION_VND",
            version=1,
            status="VALID",
        )
        db_session.add(stmt)
        db_session.flush()
        db_session.add(
            NormalizedIncome(
                statement_id=stmt.id,
                symbol=sym,
                fiscal_period_end=fend,
                fiscal_year=2025 if i == 0 else 2026,
                fiscal_quarter=4 if i == 0 else i,
                period_type="QUARTERLY",
                revenue=100.0,
                net_income=-25.0,  # Each quarter loses 25B VND -> TTM = -100B VND
            )
        )

    # Seed shares: 50M shares
    db_session.add(
        FundamentalMetric(
            symbol=sym,
            metric_id="OUTSTANDING_SHARES",
            value=50_000_000.0,
            fiscal_period_end=date(2026, 9, 30),
            period_type="QUARTERLY",
            calculation_version="verified_outstanding_v1",
        )
    )

    # Seed a provider fallback P/E (e.g. 18.5) which should be IGNORED
    db_session.add(
        FundamentalMetric(
            symbol=sym,
            metric_id="PRICE_TO_EARNINGS",
            value=18.5,
            fiscal_period_end=date(2026, 9, 30),
            period_type="QUARTERLY",
            calculation_version="provider_fallback_v1",
        )
    )
    db_session.commit()

    workspace = build_research_workspace(db_session, sym, as_of=date(2026, 10, 24))
    pe_metric = workspace.valuation["metrics"]["pe"]

    pe_val = pe_metric.get("value") if isinstance(pe_metric, dict) else pe_metric.value
    pe_status = pe_metric.get("status") if isinstance(pe_metric, dict) else pe_metric.status
    pe_v_level = pe_metric.get("verification_level") if isinstance(pe_metric, dict) else pe_metric.verification_level

    # Invariant: Negative earnings cannot produce a positive P/E or claim verification
    assert pe_val is None, f"P/E must be None for loss-making company, got {pe_val}"
    assert pe_status == "NOT_MEANINGFUL"
    assert pe_v_level == "NOT_APPLICABLE"


def test_ttm_continuity_blocks_gap_quarter():
    """
    Arbitrary quarterly sequences with missing quarters must fail TTM continuity
    and never sum disjoint quarters to claim an official TTM.
    """
    # Missing Q3 between Q2 and Q4
    disjoint_quarters = [
        {"fiscal_period_end": date(2025, 12, 31), "fiscal_year": 2025, "fiscal_quarter": 4, "net_income": 30.0},
        {"fiscal_period_end": date(2026, 3, 31), "fiscal_year": 2026, "fiscal_quarter": 1, "net_income": 35.0},
        {"fiscal_period_end": date(2026, 6, 30), "fiscal_year": 2026, "fiscal_quarter": 2, "net_income": 40.0},
        {"fiscal_period_end": date(2026, 12, 31), "fiscal_year": 2026, "fiscal_quarter": 4, "net_income": 50.0},
    ]

    valid, reason = TTMEngine.validate_quarter_coverage(disjoint_quarters)
    assert valid is False, "Quarterly sequence with missing Q3 must fail continuity check"
    assert "non-consecutive" in reason.lower() or "continuity" in reason.lower() or "missing" in reason.lower() or "gap" in reason.lower()


def test_invalidation_graph_cross_layer_lifecycle():
    """
    Verifies that invalidating an upstream price for an arbitrary symbol
    correctly propagates invalidation downstream to PE_RATIO, AI_EVIDENCE, and AI_ANALYSIS,
    and blocks publication until recalculated.
    """
    sym = "INV555"

    # Initially mark all relevant nodes valid
    for node in [
        DependencyNodeType.ADJUSTED_PRICE,
        DependencyNodeType.EPS_TTM,
        DependencyNodeType.BVPS,
        DependencyNodeType.ROE,
        DependencyNodeType.ROA,
        DependencyNodeType.MARKET_CAP,
        DependencyNodeType.PE_RATIO,
        DependencyNodeType.PB_RATIO,
        DependencyNodeType.DECISION_CONTEXT,
        DependencyNodeType.AI_EVIDENCE,
        DependencyNodeType.AI_ANALYSIS,
    ]:
        invalidation_graph.set_node_state(sym, node, NodeState.VALID)

    can_pub, _ = invalidation_graph.is_publishable(sym, DependencyNodeType.PE_RATIO)
    assert can_pub is True

    # Upstream change occurs (e.g. price adjustment or corporate action)
    event = invalidation_graph.invalidate_dependents(
        symbol=sym,
        trigger_input=DependencyNodeType.ADJUSTED_PRICE,
        reason="Corporate action split adjustment",
    )

    assert DependencyNodeType.PE_RATIO in event.invalidated_nodes
    assert DependencyNodeType.AI_ANALYSIS in event.invalidated_nodes

    # Publication is blocked
    can_pub_after, reason = invalidation_graph.is_publishable(sym, DependencyNodeType.PE_RATIO)
    assert can_pub_after is False
    assert "INVALIDATED" in reason

    # After fresh recalculation, state is restored to VALID
    invalidation_graph.set_node_state(sym, DependencyNodeType.ADJUSTED_PRICE, NodeState.VALID)
    invalidation_graph.set_node_state(sym, DependencyNodeType.PE_RATIO, NodeState.VALID)

    can_pub_restored, _ = invalidation_graph.is_publishable(sym, DependencyNodeType.PE_RATIO)
    assert can_pub_restored is True


def test_invalidation_graph_statement_restatement_triggers_ttm_and_pe():
    """
    Verifies that restating an income statement triggers downstream invalidation of
    TTM_INCOME, EPS_TTM, PE_RATIO, AI_EVIDENCE, and AI_ANALYSIS, blocking publication.
    """
    sym = "RESTATE777"
    for node in [
        DependencyNodeType.INCOME_STATEMENT,
        DependencyNodeType.TTM_INCOME,
        DependencyNodeType.EPS_TTM,
        DependencyNodeType.PE_RATIO,
        DependencyNodeType.AI_EVIDENCE,
        DependencyNodeType.AI_ANALYSIS,
    ]:
        invalidation_graph.set_node_state(sym, node, NodeState.VALID)

    # Statement restatement event
    event = invalidation_graph.invalidate_dependents(
        symbol=sym,
        trigger_input=DependencyNodeType.INCOME_STATEMENT,
        reason="Audited Q4 statement restates full-year revenue and net income",
    )

    assert DependencyNodeType.TTM_INCOME in event.invalidated_nodes
    assert DependencyNodeType.EPS_TTM in event.invalidated_nodes
    assert DependencyNodeType.PE_RATIO in event.invalidated_nodes
    assert DependencyNodeType.AI_ANALYSIS in event.invalidated_nodes

    # Publication is strictly blocked
    can_pub, reason = invalidation_graph.is_publishable(sym, DependencyNodeType.PE_RATIO)
    assert can_pub is False
    assert "INVALIDATED" in reason


def test_invalidation_corporate_action_with_recovery():
    """
    Verifies that a corporate action split/dividend invalidates both adjusted prices and
    share counts, and that mid-way failure leaves nodes in non-publishable state until full retry.
    """
    sym = "SPLIT888"
    for node in [
        DependencyNodeType.CORPORATE_ACTION,
        DependencyNodeType.ADJUSTED_PRICE,
        DependencyNodeType.SHARE_COUNT,
        DependencyNodeType.MARKET_CAP,
        DependencyNodeType.PE_RATIO,
        DependencyNodeType.PB_RATIO,
    ]:
        invalidation_graph.set_node_state(sym, node, NodeState.VALID)

    event = invalidation_graph.invalidate_dependents(
        symbol=sym,
        trigger_input=DependencyNodeType.CORPORATE_ACTION,
        reason="2:1 Stock Split",
    )

    assert DependencyNodeType.ADJUSTED_PRICE in event.invalidated_nodes
    assert DependencyNodeType.SHARE_COUNT in event.invalidated_nodes
    assert DependencyNodeType.MARKET_CAP in event.invalidated_nodes
    assert DependencyNodeType.PE_RATIO in event.invalidated_nodes
    assert DependencyNodeType.PB_RATIO in event.invalidated_nodes

    # Simulate mid-way failure: ADJUSTED_PRICE is recomputed, but SHARE_COUNT computation failed
    invalidation_graph.set_node_state(sym, DependencyNodeType.ADJUSTED_PRICE, NodeState.VALID)
    invalidation_graph.set_node_state(sym, DependencyNodeType.SHARE_COUNT, NodeState.PENDING_RECOMPUTE)

    # Market Cap must still be blocked because SHARE_COUNT is not VALID!
    can_pub_mcap, mcap_reason = invalidation_graph.is_publishable(sym, DependencyNodeType.MARKET_CAP)
    assert can_pub_mcap is False

    # Retry succeeds: SHARE_COUNT and MARKET_CAP both recomputed
    invalidation_graph.set_node_state(sym, DependencyNodeType.SHARE_COUNT, NodeState.VALID)
    invalidation_graph.set_node_state(sym, DependencyNodeType.MARKET_CAP, NodeState.VALID)

    can_pub_mcap_retry, _ = invalidation_graph.is_publishable(sym, DependencyNodeType.MARKET_CAP)
    assert can_pub_mcap_retry is True

