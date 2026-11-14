"""
Track 1 Verification Tests — Maximum Backend Data Quality:
  1. IAS 33 Time-Weighted Average Ordinary Shares Engine & PIT Corporate Actions
  2. Dual Price Series (raw_close vs total-return adjusted_close) & Backtest Integration
  3. 3-Way Cross-Source Reconciliation (VIETCAP vs VNDIRECT vs VIETSTOCK/KBS + INTERNAL)
"""
from datetime import date
from fastapi.testclient import TestClient

from apps.api.main import app
from database.connection import get_db
from database.models import (
    Asset,
    CorporateAction,
    FinancialStatement,
    FundamentalMetric,
    NormalizedBalanceSheet,
    NormalizedIncome,
    Price,
)
from services.fundamentals.shares import IAS33WeightedSharesEngine, parse_corporate_action_parameters
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.ingestion.base import MarketDataPoint
from services.ingestion.reconciliation import MarketDataReconciliationEngine
from services.ingestion.vietstock import extract_vietstock_ratios
from services.market.adjustment import PriceAdjustmentEngine
from services.quality.reconciliation import audit_dynamic_universe
from services.research.backtest import BacktestConfig, HistoricalBacktestEngine
from services.research.workspace import build_research_workspace


def test_ias33_weighted_shares_stock_dividend_and_rights_issue():
    quarters = [
        {"fiscal_period_start": date(2025, 1, 1), "fiscal_period_end": date(2025, 3, 31), "shares_basic": None},
        {"fiscal_period_start": date(2025, 4, 1), "fiscal_period_end": date(2025, 6, 30), "shares_basic": None},
        {"fiscal_period_start": date(2025, 7, 1), "fiscal_period_end": date(2025, 9, 30), "shares_basic": None},
        {"fiscal_period_start": date(2025, 10, 1), "fiscal_period_end": date(2025, 12, 31), "shares_basic": None},
    ]
    # 20% rights issue mid-year (2025-07-02) expanding shares to 120M
    actions = [
        {
            "action_date": date(2025, 6, 20),
            "ex_date": date(2025, 7, 2),
            "action_type": "RIGHTS_ISSUE",
            "ratio": 0.20,
            "value": 10000.0,
            "notes": "Rights issue 5:1 at 10,000 VND",
        },
        # Future action beyond as_of must be excluded by PIT filter
        {
            "action_date": date(2026, 2, 1),
            "ex_date": date(2026, 2, 10),
            "action_type": "STOCK_DIVIDEND",
            "ratio": 0.50,
            "notes": "Future bonus excluded from 2025-12-31 PIT",
        },
    ]
    res = IAS33WeightedSharesEngine.compute(
        symbol="HPG",
        income_quarters=quarters,
        income_annual=[],
        period_end_shares=120_000_000,
        corporate_actions=actions,
        as_of_date=date(2025, 12, 31),
        reference_prices={date(2025, 7, 1): 28000.0},
    )
    assert res.shares_basis == "IAS33_CORPORATE_ACTION_WEIGHTED_AVG"
    assert res.is_estimate is False
    # Weighted shares strictly between pre-rights (100M * TERP bonus) and post-rights (120M)
    assert res.weighted_shares is not None
    assert 105_000_000 < res.weighted_shares < 120_000_000
    assert len(res.events_applied) == 1
    assert res.events_applied[0]["effective_date"] == "2025-07-02"


def test_ias33_audited_quarters_retrospective_split_adjustment():
    quarters = [
        {"fiscal_period_start": date(2025, 1, 1), "fiscal_period_end": date(2025, 3, 31), "shares_basic": 100_000_000},
        {"fiscal_period_start": date(2025, 4, 1), "fiscal_period_end": date(2025, 6, 30), "shares_basic": 100_000_000},
        {"fiscal_period_start": date(2025, 7, 1), "fiscal_period_end": date(2025, 9, 30), "shares_basic": 115_000_000},
        {"fiscal_period_start": date(2025, 10, 1), "fiscal_period_end": date(2025, 12, 31), "shares_basic": 115_000_000},
    ]
    # 15% stock dividend went ex on 2025-07-01 (retrospectively adjusts Q1 and Q2 per IAS 33 para 26)
    actions = [
        {
            "action_date": date(2025, 6, 15),
            "ex_date": date(2025, 7, 1),
            "action_type": "STOCK_DIVIDEND",
            "ratio": 0.15,
        }
    ]
    res = IAS33WeightedSharesEngine.compute(
        symbol="FPT",
        income_quarters=quarters,
        income_annual=[],
        period_end_shares=115_000_000,
        corporate_actions=actions,
        as_of_date=date(2026, 1, 15),
    )
    assert res.shares_basis == "IAS33_AUDITED_WEIGHTED_AVG"
    assert res.is_estimate is False
    assert abs(res.weighted_shares - 115_000_000) < 1000.0


def test_ias33_fallback_without_timeline_evidence():
    quarters = [
        {"fiscal_period_start": date(2025, 1, 1), "fiscal_period_end": date(2025, 3, 31), "revenue": 250.0, "net_income": 25.0, "net_income_parent": 25.0, "shares_basic": None},
        {"fiscal_period_start": date(2025, 4, 1), "fiscal_period_end": date(2025, 6, 30), "revenue": 250.0, "net_income": 25.0, "net_income_parent": 25.0, "shares_basic": None},
        {"fiscal_period_start": date(2025, 7, 1), "fiscal_period_end": date(2025, 9, 30), "revenue": 250.0, "net_income": 25.0, "net_income_parent": 25.0, "shares_basic": None},
        {"fiscal_period_start": date(2025, 10, 1), "fiscal_period_end": date(2025, 12, 31), "revenue": 250.0, "net_income": 25.0, "net_income_parent": 25.0, "shares_basic": None},
    ]
    snap = FundamentalSnapshotBuilder("XYZ", "TECH").build_snapshot(
        income_quarters=quarters,
        income_annual=[{"fiscal_period_end": date(2024, 12, 31), "revenue": 1000.0, "net_income_parent": 100.0}],
        balance_annual=[{"fiscal_period_end": date(2024, 12, 31), "total_equity": 500.0, "equity_parent": 500.0}],
        cashflow_annual=[],
        as_of_date=date(2026, 1, 1),
        shares_outstanding=100_000_000,
    )
    assert snap["per_share"]["is_eps_estimate"] is True
    assert snap["per_share"]["shares_basis"] == "PERIOD_END_OUTSTANDING_FALLBACK_ESTIMATE"
    assert abs(snap["per_share"]["eps_ttm"] - 1000.0) < 0.01


def test_price_adjustment_engine_and_backtest_dual_series(db_session):
    asset = Asset(symbol="ACME", name="Acme Corp", asset_type="STOCK", exchange="HOSE", sector="INDUSTRIALS", status="ACTIVE")
    db_session.add(asset)
    idx = db_session.query(Asset).filter(Asset.symbol == "VNINDEX").first()
    if not idx:
        idx = Asset(symbol="VNINDEX", name="VN-Index", asset_type="INDEX", exchange="HOSE", sector="INDEX", status="ACTIVE")
        db_session.add(idx)
    db_session.flush()

    raw_bars = [
        Price(asset_id=asset.id, observation_date=date(2025, 5, 1), raw_close=100_000.0, adjusted_close=100_000.0, status="VALID"),
        Price(asset_id=asset.id, observation_date=date(2025, 5, 2), raw_close=100_000.0, adjusted_close=100_000.0, status="VALID"),
        # Ex-dividend/bonus date 2025-05-05: 25% stock dividend + 2,000 VND cash -> raw drops proportionally
        Price(asset_id=asset.id, observation_date=date(2025, 5, 5), raw_close=80_000.0, adjusted_close=80_000.0, status="VALID"),
        Price(asset_id=asset.id, observation_date=date(2025, 6, 5), raw_close=88_000.0, adjusted_close=88_000.0, status="VALID"),
    ]
    bm_bars = [
        Price(asset_id=idx.id, observation_date=date(2025, 5, 1), raw_close=1200.0, adjusted_close=1200.0, status="VALID"),
        Price(asset_id=idx.id, observation_date=date(2025, 5, 2), raw_close=1210.0, adjusted_close=1210.0, status="VALID"),
        Price(asset_id=idx.id, observation_date=date(2025, 5, 5), raw_close=1220.0, adjusted_close=1220.0, status="VALID"),
        Price(asset_id=idx.id, observation_date=date(2025, 6, 5), raw_close=1260.0, adjusted_close=1260.0, status="VALID"),
    ]
    ca = CorporateAction(
        symbol="ACME",
        action_date=date(2025, 4, 25),
        ex_date=date(2025, 5, 5),
        action_type="STOCK_DIVIDEND",
        ratio=0.25,
        source="TEST_EXCHANGE",
    )
    db_session.add_all(raw_bars + bm_bars + [ca])
    db_session.commit()

    # Before adjustment: audit must detect unadjusted pre-ex bars
    pre_audit = PriceAdjustmentEngine.audit_price_series("ACME", raw_bars, [ca], as_of=date(2025, 6, 5))
    assert pre_audit.status == "UNADJUSTED_ACTION_DETECTED"
    assert len(pre_audit.unadjusted_action_gaps) == 2

    # Run backtest on RAW vs ADJUSTED before and after recompute
    res_raw = HistoricalBacktestEngine(db_session).run_backtest(
        BacktestConfig(universe=["ACME"], start_date=date(2025, 5, 1), end_date=date(2025, 6, 5), price_basis="RAW", benchmark="VNINDEX")
    )
    assert res_raw.total_return < 0  # Unadjusted raw drop from 100k -> 88k looks negative

    recompute_summary = PriceAdjustmentEngine.recompute_asset_adjusted_prices(db_session, "ACME", as_of=date(2025, 6, 5), commit=True)
    assert recompute_summary["bars_evaluated"] == 4
    assert recompute_summary["updated_rows"] == 2

    # Verify raw_close was NEVER overwritten while adjusted_close on 2025-05-01 became 80,000
    b0 = db_session.query(Price).filter(Price.asset_id == asset.id, Price.observation_date == date(2025, 5, 1)).one()
    assert b0.raw_close == 100_000.0
    assert abs(b0.adjusted_close - 80_000.0) < 0.01

    res_adj = HistoricalBacktestEngine(db_session).run_backtest(
        BacktestConfig(universe=["ACME"], start_date=date(2025, 5, 1), end_date=date(2025, 6, 5), price_basis="ADJUSTED", benchmark="VNINDEX")
    )
    assert res_adj.total_return > 0.05  # +10% total return (80k -> 88k adjusted)
    assert res_adj.data_quality["price_basis"] == "ADJUSTED"
    assert res_adj.data_quality["benchmark_mode"] == "INDEX_SERIES:VNINDEX"
    assert res_adj.data_quality["dual_series_audit"]["ACME"]["status"] == "CLEAN_DUAL_SERIES"


def test_three_way_candle_and_ratio_reconciliation():
    engine = MarketDataReconciliationEngine()
    series = {
        "VIETCAP": [
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 19), close=90000.0, volume=100000),
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 20), close=91000.0, volume=120000),
        ],
        "VNDIRECT": [
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 19), close=90050.0, volume=100500),
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 20), close=91000.0, volume=120100),
        ],
        "VIETSTOCK": [
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 19), close=90000.0, volume=100100),
            MarketDataPoint(symbol="VCB", observation_date=date(2026, 10, 20), close=75000.0, volume=120000),  # Outlier spike
        ],
    }
    candle_report = engine.reconcile_three_way_candles("VCB", series)
    assert candle_report.status == "TWO_OF_THREE_CONSENSUS"
    assert candle_report.three_way_consensus_count == 1
    assert candle_report.two_of_three_consensus_count == 1
    assert candle_report.outlier_counts_by_provider["VIETSTOCK"] == 1
    assert abs(candle_report.consensus_close_by_date["2026-10-20"] - 91000.0) < 1.0

    # Test ratio quorum when VNDIRECT is missing P/B while VIETCAP + VIETSTOCK + INTERNAL agree
    vs_ratios = extract_vietstock_ratios({"PE": 12.1, "PB": 2.45, "ROE": 21.5})
    assert vs_ratios["pb"] == 2.45
    ratio_rep = engine.reconcile_three_way_ratios(
        "VCB",
        {
            "VNDIRECT": {"pe": 12.0, "pb": None, "roe": 21.4},
            "VIETCAP": {"pe": 12.05, "pb": 2.42, "roe": 21.6},
            "VIETSTOCK": vs_ratios,
            "INTERNAL": {"pe": 12.02, "pb": 2.44, "roe": 21.5},
        },
        as_of=date(2026, 10, 19),
    )
    assert ratio_rep.metrics["pb"].consensus_status == "THREE_WAY_CONSENSUS"
    assert "VIETCAP" in ratio_rep.metrics["pb"].agreeing_providers
    assert "VIETSTOCK" in ratio_rep.metrics["pb"].agreeing_providers
    assert "VNDIRECT" in ratio_rep.metrics["pb"].missing_providers


def test_dynamic_universe_and_api_three_way_routes(db_session):
    asset = Asset(symbol="TRK1", name="Track 1 Corp", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY", status="ACTIVE")
    db_session.add(asset)
    db_session.flush()

    db_session.add(Price(
        asset_id=asset.id, observation_date=date(2025, 12, 30),
        raw_close=100_000.0, adjusted_close=100_000.0, status="VALID", source="VIETCAP",
    ))

    # Add 4 quarterly statements + BS + OUTSTANDING_SHARES + VIETCAP_PB + CorporateAction
    for q_idx, (m_start, m_end, d_end) in enumerate([(1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31)], start=1):
        fs = FinancialStatement(
            asset_id=asset.id, symbol="TRK1", statement_type="INCOME_STATEMENT",
            fiscal_year=2025, fiscal_quarter=q_idx, period_type="QUARTERLY",
            fiscal_period_start=date(2025, m_start, 1), fiscal_period_end=date(2025, m_end, d_end),
            statement_date=date(2025, m_end, d_end), publication_date=date(2025, m_end, d_end),
            consolidation="CONSOLIDATED", source_name="VIETCAP_IQ", currency="VND",
            unit_scale="BILLION_VND", version=1, status="VALID",
        )
        db_session.add(fs)
        db_session.flush()
        db_session.add(NormalizedIncome(
            statement_id=fs.id, symbol="TRK1", fiscal_period_end=date(2025, m_end, d_end),
            fiscal_year=2025, fiscal_quarter=q_idx, period_type="QUARTERLY",
            revenue=15000.0, net_income=2000.0, net_income_parent=1800.0,
        ))

    bs_fs = FinancialStatement(
        asset_id=asset.id, symbol="TRK1", statement_type="BALANCE_SHEET",
        fiscal_year=2025, fiscal_quarter=4, period_type="ANNUAL",
        fiscal_period_start=date(2025, 1, 1), fiscal_period_end=date(2025, 12, 31),
        statement_date=date(2025, 12, 31), publication_date=date(2025, 12, 31),
        consolidation="CONSOLIDATED", source_name="VIETCAP_IQ", currency="VND",
        unit_scale="BILLION_VND", version=1, status="VALID",
    )
    db_session.add(bs_fs)
    db_session.flush()
    db_session.add(NormalizedBalanceSheet(
        statement_id=bs_fs.id, symbol="TRK1", fiscal_period_end=date(2025, 12, 31),
        fiscal_year=2025, fiscal_quarter=None, period_type="ANNUAL",
        total_equity=36000.0, equity_parent=36000.0,
    ))
    db_session.add_all([
        FundamentalMetric(
            symbol="TRK1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="OUTSTANDING_SHARES", metric_category="SHARE", metric_name="Shares",
            calculation_version="v1", value=1_440_000_000.0, unit="SHARES",
            as_of_publication_date=date(2025, 12, 31),
        ),
        FundamentalMetric(
            symbol="TRK1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="VIETCAP_PB", metric_category="VALUATION", metric_name="Vietcap P/B",
            calculation_version="v1", value=4.0, unit="multiple",
            as_of_publication_date=date(2025, 12, 31),
        ),
        CorporateAction(
            symbol="TRK1", action_date=date(2025, 6, 10), ex_date=date(2025, 6, 20),
            action_type="STOCK_DIVIDEND", ratio=0.15, source="HOSE_OFFICIAL",
        ),
    ])
    db_session.commit()

    ws = build_research_workspace(db_session, "TRK1", as_of=date(2026, 1, 10))
    assert ws is not None
    # IAS 33 corporate-action timeline eliminates period-end estimate fallback!
    eps_metric = ws.fundamentals["metrics"]["eps_ttm"]
    is_est = eps_metric["is_estimate"] if isinstance(eps_metric, dict) else eps_metric.is_estimate
    eps_val = eps_metric["value"] if isinstance(eps_metric, dict) else eps_metric.value
    assert is_est is False
    assert abs(eps_val - 5000.0) < 1.0

    audit = audit_dynamic_universe(db_session, as_of=date(2026, 1, 10))
    assert audit["reconciliation"]["pe_metric"]["strict_ttm_eps_count"] >= 1
    assert audit["reconciliation"]["pb_secondary_resolved_count"] >= 1

    # Verify API routes via isolated session override
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        r1 = client.get("/api/v1/data/price-adjustment-audit/TRK1?as_of=2026-01-10")
        assert r1.status_code == 200
        assert r1.json()["status"] == "CLEAN_DUAL_SERIES"

        r2 = client.get("/api/v1/data/reconciliation/three-way/TRK1?as_of=2026-01-10")
        assert r2.status_code == 200
        assert r2.json()["metrics"]["pb"]["values_by_provider"]["VIETCAP"] == 4.0
    finally:
        app.dependency_overrides.clear()


def test_corporate_action_parser_cash_dividend_and_1_for_1_stock_dividend():
    p_cash_dot = parse_corporate_action_parameters({
        "action_type": "CASH_DIVIDEND",
        "ex_date": date(2025, 8, 1),
        "notes": "Trả cổ tức tiền mặt đợt 1 năm 2025: 1.500 đ/cp",
    })
    assert p_cash_dot["cash_dividend_per_share"] == 1500.0

    p_cash_comma = parse_corporate_action_parameters({
        "action_type": "CASH_DIVIDEND",
        "ex_date": date(2025, 8, 1),
        "notes": "2,000 đồng/cổ phiếu",
    })
    assert p_cash_comma["cash_dividend_per_share"] == 2000.0

    p_1_for_1 = parse_corporate_action_parameters({
        "action_type": "STOCK_DIVIDEND",
        "ex_date": date(2025, 9, 1),
        "ratio": 1.0,
        "notes": "Phát hành cổ phiếu trả cổ tức",
    })
    assert p_1_for_1["share_multiplier"] == 2.0


def test_ias33_self_checkpoint_monday_rights_and_post_window_resource_action():
    quarters = [
        {"fiscal_period_start": date(2025, 1, 1), "fiscal_period_end": date(2025, 3, 31), "shares_basic": None},
        {"fiscal_period_start": date(2025, 4, 1), "fiscal_period_end": date(2025, 6, 30), "shares_basic": None},
        {"fiscal_period_start": date(2025, 7, 1), "fiscal_period_end": date(2025, 9, 30), "shares_basic": None},
        {"fiscal_period_start": date(2025, 10, 1), "fiscal_period_end": date(2025, 12, 31), "shares_basic": None},
    ]
    # Window-end only checkpoint must NOT self-validate into is_estimate=False
    res_end_only = IAS33WeightedSharesEngine.compute(
        symbol="SELFCHK",
        income_quarters=quarters,
        income_annual=[],
        period_end_shares=100_000_000,
        shares_history=[{"effective_date": date(2025, 12, 31), "value": 100_000_000, "metric_id": "OUTSTANDING_SHARES"}],
        as_of_date=date(2026, 2, 1),
    )
    assert res_end_only.is_estimate is True
    assert res_end_only.diagnostic_reason == "WEIGHTED_AVERAGE_UNAVAILABLE_FALLBACK_TO_PERIOD_END_OUTSTANDING"

    # Monday ex-date picks Friday reference price; post-window issuance is undone before FY window
    res_monday_rights = IAS33WeightedSharesEngine.compute(
        symbol="MONR",
        income_quarters=quarters,
        income_annual=[],
        period_end_shares=120_000_000,  # Observed 2026-03-31 AFTER 20% post-window issuance
        shares_history=[{"effective_date": date(2026, 3, 31), "value": 120_000_000, "metric_id": "OUTSTANDING_SHARES"}],
        corporate_actions=[
            {
                # 2025-07-07 is a Monday -> Friday prior close was 2025-07-04 (30,000)
                "action_type": "RIGHTS_ISSUE",
                "ex_date": date(2025, 7, 7),
                "ratio": 0.25,
                "value": 10_000.0,
                "source": "HOSE",
            },
            {
                "action_type": "SHARE_ISSUANCE",
                "ex_date": date(2026, 2, 15),
                "ratio": 0.20,
                "source": "HOSE",
            },
        ],
        as_of_date=date(2026, 4, 15),
        reference_prices={date(2025, 7, 4): 30_000.0},
    )
    assert abs(res_monday_rights.period_end_shares - 100_000_000.0) < 1.0
    rights_ev = [e for e in res_monday_rights.events_applied if e["action_type"] == "RIGHTS_ISSUE"][0]
    assert rights_ev["bonus_factor"] > 1.1  # TERP = (30k + 0.25*10k)/1.25 = 26k -> 30k/26k = 1.153846


def test_stale_adjustment_descending_metrics_and_quorum_cliques(db_session):
    sym = "STALE1"
    asset = Asset(symbol=sym, name="Stale Co", asset_type="STOCK", exchange="HOSE", sector="INDUSTRIALS", status="ACTIVE")
    db_session.add(asset)
    db_session.flush()

    bar_old = Price(
        asset_id=asset.id, observation_date=date(2025, 1, 10),
        raw_close=100_000.0, adjusted_close=80_000.0, adjustment_factor=0.8, status="VALID",
    )
    bar_new = Price(
        asset_id=asset.id, observation_date=date(2025, 8, 1),
        raw_close=65_000.0, adjusted_close=65_000.0, adjustment_factor=1.0, status="VALID",
    )
    # Two splits totaling factor 0.8 * 0.8 = 0.64 -> bar_old stored at 0.8 is stale!
    ca1 = CorporateAction(symbol=sym, action_date=date(2025, 2, 1), ex_date=date(2025, 2, 10), action_type="STOCK_DIVIDEND", ratio=0.25, source="HOSE")
    ca2 = CorporateAction(symbol=sym, action_date=date(2025, 7, 1), ex_date=date(2025, 7, 10), action_type="STOCK_DIVIDEND", ratio=0.25, source="HOSE")
    db_session.add_all([bar_old, bar_new, ca1, ca2])
    # Descending FundamentalMetric order: older (2024) must NOT overwrite newer (2025)!
    db_session.add_all([
        FundamentalMetric(symbol=sym, fiscal_period_end=date(2024, 12, 31), period_type="TTM", metric_id="VIETCAP_PB", metric_category="VALUATION", metric_name="PB", calculation_version="v1", value=9.9, unit="multiple"),
        FundamentalMetric(symbol=sym, fiscal_period_end=date(2025, 12, 31), period_type="TTM", metric_id="VIETCAP_PB", metric_category="VALUATION", metric_name="PB", calculation_version="v1", value=2.1, unit="multiple"),
        FundamentalMetric(symbol=sym, fiscal_period_end=date(2024, 12, 31), period_type="TTM", metric_id="VIETSTOCK_PB", metric_category="VALUATION", metric_name="PB", calculation_version="v1", value=9.9, unit="multiple"),
        FundamentalMetric(symbol=sym, fiscal_period_end=date(2025, 12, 31), period_type="TTM", metric_id="VIETSTOCK_PB", metric_category="VALUATION", metric_name="PB", calculation_version="v1", value=2.1, unit="multiple"),
    ])
    db_session.commit()

    audit_stale = PriceAdjustmentEngine.audit_price_series(sym, [bar_old, bar_new], [ca1, ca2], as_of=date(2025, 8, 5))
    assert audit_stale.status == "UNADJUSTED_ACTION_DETECTED"
    assert audit_stale.unadjusted_action_gaps[0]["expected_factor"] == 0.64

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        r = TestClient(app).get(f"/api/v1/data/reconciliation/three-way/{sym}?as_of=2025-12-31")
        assert r.status_code == 200
        assert r.json()["metrics"]["pb"]["values_by_provider"]["VIETCAP"] == 2.1
    finally:
        app.dependency_overrides.clear()

    # Non-clique transitive chain (100, 104.5, 109.2 with 5% tol -> A & C diverge 9.2%!)
    engine = MarketDataReconciliationEngine()
    q_chain = engine._solve_quorum({"A": 100.0, "B": 104.5, "C": 109.2}, ["A", "B", "C"], tol_match=0.05, tol_major=0.10)
    assert q_chain[0] == "THREE_WAY_DIVERGENCE"
    assert q_chain[1] is None

    # Disjoint tie 2 vs 2 across 4 providers
    q_tie = engine._solve_quorum({"A": 10.0, "B": 10.0, "C": 20.0, "D": 20.0}, ["A", "B", "C", "D"], tol_match=0.05, tol_major=0.10)
    assert q_tie[0] == "THREE_WAY_DIVERGENCE"
    assert q_tie[1] is None

    # Pure 2-source candles must not inflate three_way_consensus_count
    two_src = engine.reconcile_three_way_candles(
        sym,
        {
            "VNDIRECT": [MarketDataPoint(symbol=sym, observation_date=date(2025, 1, 2), close=10.0, volume=100.0)],
            "VIETCAP": [MarketDataPoint(symbol=sym, observation_date=date(2025, 1, 2), close=10.0, volume=100.0)],
        },
    )
    assert two_src.three_way_consensus_count == 0
    assert two_src.status == "TWO_SOURCE_AGREEMENT"


def test_backtest_carries_forward_missing_bars_and_index_benchmark(db_session):
    a1 = Asset(symbol="CF1", name="Carry1", asset_type="STOCK", exchange="HOSE", sector="TECH", status="ACTIVE")
    a2 = Asset(symbol="CF2", name="Carry2", asset_type="STOCK", exchange="HOSE", sector="TECH", status="ACTIVE")
    db_session.add_all([a1, a2])
    idx = db_session.query(Asset).filter(Asset.symbol == "VNINDEX").first()
    if not idx:
        idx = Asset(symbol="VNINDEX", name="VN-Index", asset_type="INDEX", exchange="HOSE", sector="INDEX", status="ACTIVE")
        db_session.add(idx)
    db_session.flush()

    db_session.add_all([
        Price(asset_id=a1.id, observation_date=date(2025, 11, 3), raw_close=10_000.0, adjusted_close=10_000.0, status="VALID"),
        # CF1 missing on 2025-11-04 (halted/suspended), resumes flat on 2025-11-05
        Price(asset_id=a1.id, observation_date=date(2025, 11, 5), raw_close=10_000.0, adjusted_close=10_000.0, status="VALID"),
        Price(asset_id=a2.id, observation_date=date(2025, 11, 3), raw_close=20_000.0, adjusted_close=20_000.0, status="VALID"),
        Price(asset_id=a2.id, observation_date=date(2025, 11, 4), raw_close=20_000.0, adjusted_close=20_000.0, status="VALID"),
        Price(asset_id=a2.id, observation_date=date(2025, 11, 5), raw_close=20_000.0, adjusted_close=20_000.0, status="VALID"),
        Price(asset_id=idx.id, observation_date=date(2025, 11, 3), raw_close=1200.0, adjusted_close=1200.0, status="VALID"),
        # VNINDEX missing 2025-11-04 -> carries forward 1200 instead of jumping to EQUAL_WEIGHT proxy
        Price(asset_id=idx.id, observation_date=date(2025, 11, 5), raw_close=1200.0, adjusted_close=1200.0, status="VALID"),
    ])
    db_session.commit()

    bt = HistoricalBacktestEngine(db_session).run_backtest(
        BacktestConfig(
            universe=["CF1", "CF2"],
            start_date=date(2025, 11, 3),
            end_date=date(2025, 11, 5),
            benchmark="VNINDEX",
            transaction_cost_pct=0.0,
            tax_pct=0.0,
            slippage_pct=0.0,
        )
    )
    assert len(bt.equity_curve) == 3
    assert bt.max_drawdown == 0.0
    assert all(pt.benchmark_value == bt.initial_capital for pt in bt.equity_curve)
