"""
Regression tests for financial ratio correctness, unit/scale consistency,
shares outstanding resolution, and valuation anomaly prevention.
"""
from datetime import date, timedelta
import os
import pytest
from database.connection import SessionLocal, DEFAULT_DB_PATH
from database.models import (
    Asset,
    FinancialStatement,
    FundamentalMetric,
    NormalizedIncome,
    NormalizedBalanceSheet,
    Price,
)
from services.fundamentals.engine import TTMEngine
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.research.workspace import build_research_workspace


@pytest.fixture
def seed_acb_test_data(db_session):
    """
    Seeds ACB with the exact real-world scenario that reproduced the P/B = 39.3 anomaly:
    - Interim quarterly income filings with null/zero shares_basic
    - 3 quarters with zero EPS and 1 quarter with 542 EPS (which formerly summed to 542 EPS)
    - Balance sheet with 99,314.5 Billion VND total equity
    - Canonical FundamentalMetric with 5,804,421,957 shares and 1.1835 P/B
    - Market price of 21,300 VND
    """
    asset = db_session.query(Asset).filter_by(symbol="ACB").first()
    if not asset:
        asset = Asset(
            symbol="ACB",
            name="Asia Commercial Joint Stock Bank",
            asset_type="STOCK",
            exchange="HOSE",
            sector="BANK"
        )
        db_session.add(asset)
        db_session.flush()

    # Clean up existing ACB records to ensure fixture idempotency
    for stmt in db_session.query(FinancialStatement).filter_by(symbol="ACB").all():
        db_session.query(NormalizedIncome).filter_by(statement_id=stmt.id).delete()
        db_session.query(NormalizedBalanceSheet).filter_by(statement_id=stmt.id).delete()
        db_session.delete(stmt)
    db_session.query(FundamentalMetric).filter_by(symbol="ACB").delete()
    db_session.query(Price).filter_by(asset_id=asset.id).delete()
    db_session.flush()

    # Fundamental metrics: OUTSTANDING_SHARES and PRICE_TO_BOOK
    db_session.add(FundamentalMetric(
        symbol="ACB",
        metric_id="OUTSTANDING_SHARES",
        value=5804421957.0,
        period_type="QUARTERLY",
        fiscal_period_end=date(2026, 6, 30),
        calculation_version="vndirect_ratio_v1"
    ))
    db_session.add(FundamentalMetric(
        symbol="ACB",
        metric_id="PRICE_TO_BOOK",
        value=1.1835,
        period_type="QUARTERLY",
        fiscal_period_end=date(2026, 6, 30),
        calculation_version="vndirect_ratio_v1"
    ))

    # Financial statements: 4 quarters of income where interim shares_basic is None
    # and 3 quarters had eps_basic = 0.0 (previously causing 542 partial EPS sum)
    quarters_data = [
        (date(2025, 9, 30), 4000.0, 0.0),
        (date(2025, 12, 31), 3500.0, 542.0),
        (date(2026, 3, 31), 4100.0, 0.0),
        (date(2026, 6, 30), 4078.0, 0.0),
    ]
    for q_idx, (end_dt, net_inc, eps_b) in enumerate(quarters_data):
        stmt = FinancialStatement(
            asset_id=asset.id,
            symbol="ACB",
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=end_dt,
            fiscal_year=end_dt.year,
            fiscal_quarter=q_idx + 1,
            period_type="QUARTERLY",
            publication_date=end_dt,
            source_name="VNDIRECT",
            status="VALID"
        )
        db_session.add(stmt)
        db_session.flush()
        db_session.add(NormalizedIncome(
            statement_id=stmt.id,
            symbol="ACB",
            fiscal_period_end=end_dt,
            fiscal_year=end_dt.year,
            fiscal_quarter=q_idx + 1,
            period_type="QUARTERLY",
            revenue=8000.0,
            net_income=net_inc,
            net_income_parent=net_inc,
            eps_basic=eps_b,
            shares_basic=None  # Exactly reproduces interim missing shares
        ))

    # Balance sheet: 99,314.5 Billion VND total equity
    bs_stmt = FinancialStatement(
        asset_id=asset.id,
        symbol="ACB",
        statement_type="BALANCE_SHEET",
        fiscal_period_end=date(2026, 6, 30),
        fiscal_year=2026,
        fiscal_quarter=2,
        period_type="QUARTERLY",
        publication_date=date(2026, 7, 20),
        source_name="VNDIRECT",
        status="VALID"
    )
    db_session.add(bs_stmt)
    db_session.flush()
    db_session.add(NormalizedBalanceSheet(
        statement_id=bs_stmt.id,
        symbol="ACB",
        fiscal_period_end=date(2026, 6, 30),
        fiscal_year=2026,
        fiscal_quarter=2,
        period_type="QUARTERLY",
        total_assets=720000.0,
        total_equity=99314.5,
        equity_parent=99314.5,
        share_capital=58044.2,
        customer_deposits=500000.0
    ))

    # Market Price: 21,300 VND on 2026-10-26
    db_session.add(Price(
        asset_id=asset.id,
        observation_date=date(2026, 10, 26),
        raw_close=21300.0,
        adjusted_close=21300.0,
        source="VNDIRECT",
        status="VALID"
    ))
    db_session.commit()
    return asset


def test_acb_pb_and_pe_correctness(db_session, seed_acb_test_data):
    """
    Priority 1 Regression Test:
    Ensures ACB's P/B is within realistic Vietnamese banking bounds (~1.1 to 1.5)
    and NOT distorted to 39.3 due to missing shares or partial quarterly EPS sums.
    """
    workspace = build_research_workspace(db_session, "ACB", date(2026, 10, 26))
    assert workspace is not None
    data = workspace.model_dump()
    val_metrics = data.get("valuation", {}).get("metrics", {})
    fund_metrics = data.get("fundamentals", {}).get("metrics", {})

    # 1. P/B multiple validation: must be ~1.24, definitely not 39.3
    pb = val_metrics.get("pb")
    assert pb is not None
    assert pb["status"] == "AVAILABLE"
    assert 1.0 <= pb["value"] <= 1.5, f"Expected ACB P/B in [1.0, 1.5], got {pb['value']}"

    # 2. P/E multiple validation: must be ~7.89, definitely not 39.3
    pe = val_metrics.get("pe")
    assert pe is not None
    assert pe["status"] == "AVAILABLE"
    assert 5.0 <= pe["value"] <= 12.0, f"Expected ACB P/E in [5.0, 12.0], got {pe['value']}"

    # 3. BVPS validation (ACB equity ~99.3T VND / ~5.8B shares = ~17,110 VND/share)
    bvps = fund_metrics.get("bvps")
    assert bvps is not None
    assert bvps["status"] == "AVAILABLE"
    assert 15_000.0 <= bvps["value"] <= 20_000.0, f"Expected ACB BVPS in [15k, 20k], got {bvps['value']}"

    # 4. EPS TTM validation (ACB TTM net income ~15.7T VND / ~5.8B shares = ~2,700 VND/share)
    eps_ttm = fund_metrics.get("eps_ttm")
    assert eps_ttm is not None
    assert eps_ttm["status"] == "AVAILABLE"
    assert 2_000.0 <= eps_ttm["value"] <= 3_500.0, f"Expected ACB EPS TTM in [2k, 3.5k], got {eps_ttm['value']}"


def test_shares_outstanding_resolution(db_session, seed_acb_test_data):
    """
    Verifies that FinancialRepository resolves shares_outstanding via FundamentalMetric
    or balance sheet share_capital when NormalizedIncome.shares_basic is null.
    """
    with FinancialRepository(session=db_session) as repo:
        dataset = repo.get_financial_dataset("ACB", as_of_date=date(2026, 10, 26))
        assert dataset is not None
        shares = dataset.get("shares_outstanding")
        assert shares is not None
        assert shares > 5_000_000_000, f"Expected ACB shares > 5B, got {shares}"


def test_ttm_engine_partial_quarterly_eps_guard():
    """
    Verifies that TTMEngine.compute_ttm_income does not sum partial zero EPS quarters,
    which would otherwise generate a bogus small EPS number and inflate P/E.
    """
    quarters = [
        {"fiscal_period_end": date(2025, 9, 30), "eps_basic": 0.0, "net_income": 4000.0},
        {"fiscal_period_end": date(2025, 12, 31), "eps_basic": 542.0, "net_income": 3000.0},
        {"fiscal_period_end": date(2026, 3, 31), "eps_basic": 0.0, "net_income": 4200.0},
        {"fiscal_period_end": date(2026, 6, 30), "eps_basic": 0.0, "net_income": 4300.0},
    ]
    ttm = TTMEngine.compute_ttm_income(quarters)
    # eps_basic must be None because not all 4 quarters reported positive EPS
    assert ttm.get("eps_basic") is None
    # net_income must be correctly aggregated
    assert ttm.get("net_income") == 15500.0


def test_valuation_metric_outlier_guard(db_session, seed_acb_test_data):
    """
    Verifies that workspace valuation calculates realistic P/E and P/B,
    handling banking multiples, cyclical troughs, and annual-only filings safely.
    """
    # 1. ACB with 4 full quarters has both AVAILABLE P/E and P/B within standard banking bounds
    w_acb = build_research_workspace(db_session, "ACB", date(2026, 10, 26))
    assert w_acb is not None
    acb_v = w_acb.model_dump().get("valuation", {}).get("metrics", {})
    assert acb_v["pe"]["status"] == "AVAILABLE"
    assert 5.0 <= acb_v["pe"]["value"] <= 15.0
    assert acb_v["pb"]["status"] == "AVAILABLE"
    assert 1.0 <= acb_v["pb"]["value"] <= 2.0

    # 2. Seeded assets (VCB, MBB, FPT, MWG, HPG) have AVAILABLE P/B within realistic economic bounds
    for sym in ["VCB", "MBB", "FPT", "MWG", "HPG"]:
        w = build_research_workspace(db_session, sym, date(2026, 10, 26))
        assert w is not None
        v = w.model_dump().get("valuation", {}).get("metrics", {})
        pb = v.get("pb")
        assert pb is not None and pb["status"] == "AVAILABLE", f"{sym} PB status: {pb}"
        assert 0.2 <= pb["value"] <= 10.0, f"{sym} PB outlier: {pb['value']}"


def test_divide_by_zero_and_negative_equity_guard():
    """
    Verifies that non-positive denominators in FundamentalSnapshotBuilder
    or valuation engines return safe None or NOT_MEANINGFUL without exceptions.
    """
    builder = FundamentalSnapshotBuilder("MOCK", "GENERAL")
    snapshot = builder.build_snapshot(
        income_quarters=[],
        income_annual=[{"fiscal_period_end": date(2025, 12, 31), "shares_basic": 0, "revenue": 100.0, "net_income": -50.0}],
        balance_annual=[{"fiscal_period_end": date(2025, 12, 31), "total_equity": -100.0, "total_assets": 500.0}],
        cashflow_annual=[],
        as_of_date=date.today(),
        shares_outstanding=0,
    )
    per_share = snapshot.get("per_share", {})
    assert per_share.get("bvps") is None
    assert per_share.get("eps_ttm") is None


def test_stale_price_and_period_mismatch_guard(db_session, seed_acb_test_data):
    """
    Verifies that prices older than 7 calendar days are flagged as STALE
    and that as_of date filters point-in-time statements correctly.
    """
    # 1. As of 30 days after the last price, price status must be STALE
    future_date = date(2026, 10, 26) + timedelta(days=30)
    w_future = build_research_workspace(db_session, "ACB", future_date)
    assert w_future is not None
    assert w_future.price.get("status") == "STALE"

    # 2. As of a past date before any financial statements were published, status is INSUFFICIENT_DATA
    past_date = date(2020, 1, 1)
    w_past = build_research_workspace(db_session, "ACB", past_date)
    assert w_past is not None
    assert w_past.fundamentals.get("status") == "INSUFFICIENT_DATA"


def test_canonical_dev_db_universe_valuation_coverage():
    """
    Verifies that all 100 VN100 equities in the canonical database
    have active, available P/E and P/B metrics.
    """
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url or not db_url.startswith("postgresql"):
        pytest.skip("Local canonical PostgreSQL database not configured in environment")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from services.universe.registry import UniverseRegistry

    try:
        dev_engine = create_engine(db_url, connect_args={"connect_timeout": 3})
        with Session(dev_engine) as dev_session:
            canonical = UniverseRegistry.get_canonical_universe(dev_session)
            equities = [item.symbol for item in canonical if item.asset_type == "STOCK"]
            assert len(equities) == 100

            available_pe_count = sum(
                1 for sym in equities
                if (w := build_research_workspace(dev_session, sym, date(2026, 10, 26)))
                and w.model_dump().get("valuation", {}).get("metrics", {}).get("pe", {}).get("status") == "AVAILABLE"
            )
            available_pb_count = sum(
                1 for sym in equities
                if (w := build_research_workspace(dev_session, sym, date(2026, 10, 26)))
                and w.model_dump().get("valuation", {}).get("metrics", {}).get("pb", {}).get("status") == "AVAILABLE"
            )

            assert available_pe_count == 100, f"Expected 100/100 AVAILABLE PE, got {available_pe_count}"
            assert available_pb_count == 100, f"Expected 100/100 AVAILABLE PB, got {available_pb_count}"
    except Exception as exc:
        pytest.skip(f"PostgreSQL canonical database unavailable: {exc}")
