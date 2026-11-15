# -*- coding: utf-8 -*-
"""
Unit & Integration Tests for Stage 2-3 Enhancements and P0 AI/Valuation Fixes:
1. Universe symbol disambiguation (blocking DCA/FED/HRC false positives while preserving explicit marker extraction).
2. N-symbol stratified evidence budgeting & dynamic N-column comparison_table generation.
3. Cyclical commodity peak damping + DCF 3x3 WACC/g sensitivity matrix (P10/P50/P90) + BMP structural preservation.
4. Cross-sectional factor profile helper & SQLite fallback behavior.
5. Market dashboard foreign_flow integration (AVAILABLE vs NOT_CONFIGURED).
6. Dividend bilingual/structured deduplication across VN/EN corporate actions.
7. AI Earnings Quality Gate blocking BUY verdicts when CFO/NI < 0.30x.
8. Walk-forward out-of-sample PIT signal calibration (IC, RankIC, Hit Rate, Brier Score).
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from database.models import (
    Asset,
    AssetDecisionSnapshot,
    CorporateAction,
    MacroObservation,
    MarketFlowDaily,
    Price,
)
from services.ai.analyst import AIAnalyst
from services.ai.planner import QueryIntent, QueryPlanner
from services.ai.prompt_registry import build_chat_prompt
from services.ai.schemas import AICitation
from services.ai.tools import AITools
from services.factors.engine import FactorEngine, _z_to_score
from services.fundamentals.dividends import DividendYieldEngine
from services.market.dashboard import build_market_dashboard
from services.research.backtest import HistoricalBacktestEngine
from services.universe.registry import UniverseRegistry
from services.valuation.builder import ValuationSnapshotBuilder
from services.valuation.engine import DCFEngine
from services.valuation.models import DCFAssumptions


def test_symbol_extraction_blocks_dca_fed_hrc_and_keeps_explicit_marker(db_session: Session):
    q = "Giả sử có 50 triệu giải ngân DCA theo FED khi giá HRC biến động cho VCB, MBB, TCB?"
    syms = UniverseRegistry.extract_all_symbols_from_text(q, db_session)
    assert "DCA" not in syms
    assert "FED" not in syms
    assert "HRC" not in syms
    assert syms == ["VCB", "MBB", "TCB"]

    unknown_syms = UniverseRegistry.extract_all_symbols_from_text("Phân tích mã ZZZTEST giúp tôi", db_session)
    assert "ZZZTEST" in unknown_syms


def test_portfolio_dca_query_routing_and_macro_context(db_session: Session):
    plan = QueryPlanner.plan_query(
        "Giả sử hôm nay giải ngân DCA 50 triệu VND vào cổ phiếu ngân hàng hay công nghệ?",
        db_session,
    )
    assert plan.intent == QueryIntent.PORTFOLIO
    assert plan.symbols == ["VN100"]

    macro_ctx = AITools.get_context(
        "MARKET",
        as_of=date(2026, 11, 13),
        session=db_session,
        question="Chính sách FED, DGS10 và tỷ giá USD/VND hôm nay như thế nào?",
    )
    analyst = AIAnalyst()
    citations = analyst._citations(macro_ctx)
    summary, _ = analyst._build_structured_data_summary(citations, macro_ctx, ["MARKET"])
    assert summary is not None
    assert "macro" in summary or len(macro_ctx.get("evidence", [])) >= 1


def test_multi_symbol_stratified_prompt_and_three_column_table():
    prompt_ctx = {
        "symbol": "VCB",
        "symbols": ["VCB", "MBB", "TCB"],
        "as_of_date": "2026-11-13",
        "evidence_register": [
            {
                "id": f"E{idx}_{metric}",
                "responsible_module": "bank_metrics",
                "symbol": sym,
                "metric": metric,
                "value": val,
                "unit": "%",
                "claim_type": "FACT",
                "source": "VIETCAP",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
            }
            for idx, (sym, nim, npl, roe) in enumerate(
                [("VCB", 3.1, 0.9, 19.5), ("MBB", 4.2, 1.5, 22.1), ("TCB", 4.0, 1.2, 16.8)],
                start=1,
            )
            for metric, val in [("nim", nim), ("npl_ratio", npl), ("roe", roe)]
        ],
    }
    prompt = build_chat_prompt("So sánh NIM, NPL và ROE của VCB, MBB, TCB?", prompt_ctx)
    for sym in ("VCB", "MBB", "TCB"):
        assert sym in prompt

    citations = [AICitation(**item) for item in prompt_ctx["evidence_register"]]
    summary, _ = AIAnalyst()._build_structured_data_summary(citations, prompt_ctx, ["VCB", "MBB", "TCB"])
    tbl = summary.get("comparison_table")
    assert tbl is not None
    assert tbl["symbols"] == ["VCB", "MBB", "TCB"]
    assert any(row["metric"] == "nim" and set(row["values"].keys()) == {"VCB", "MBB", "TCB"} for row in tbl["rows"])


def test_dcf_sensitivity_matrix_and_cyclical_damping_discrimination():
    assump = DCFAssumptions(
        revenue_growth_rates=[0.12, 0.11, 0.10, 0.09, 0.08],
        ebit_margins=[0.20] * 5,
        tax_rate=0.20,
        wacc=0.12,
        terminal_growth_rate=0.03,
        base_revenue=10000.0,
        capex_percent_rev=0.04,
    )
    sens = DCFEngine.calculate_sensitivity_matrix(assump, shares_outstanding=1_000_000_000, net_debt=0.0)
    assert len(sens["grid"]) == 9
    assert sens["p10"] <= sens["p50"] <= sens["p90"]

    cyclical_snap = ValuationSnapshotBuilder("BSR", "OIL_GAS").build(
        {
            "eps_ttm": 2000.0,
            "bvps": 18000.0,
            "shares_outstanding": 3_100_000_000,
            "revenue_ttm": 120000.0,
            "operating_margin": 0.22,
            "revenue_yoy": 0.30,
            "wacc": 0.12,
            "use_dynamic_assumptions": True,
        },
        current_price=25000.0,
        as_of=date(2026, 11, 13),
    )
    assert any("CYCLICAL_PEAK_DAMPING" in w for w in cyclical_snap.warnings)
    assert len(cyclical_snap.scenarios) == 3

    structural_snap = ValuationSnapshotBuilder("BMP", "MATERIALS").build(
        {
            "eps_ttm": 12710.0,
            "bvps": 38740.0,
            "shares_outstanding": 81_860_000,
            "revenue_ttm": 5156.0,
            "net_debt": -658.26,
            "operating_margin": 0.2521,
            "revenue_yoy": -0.1123,
            "wacc": 0.1171,
            "use_dynamic_assumptions": True,
        },
        current_price=110000.0,
        as_of=date(2026, 11, 2),
    )
    assert not any("CYCLICAL_PEAK_DAMPING" in w for w in structural_snap.warnings)


def test_cross_sectional_factor_z_score_and_sqlite_fallback(db_session: Session):
    assert _z_to_score(0.0) == 50.0
    assert _z_to_score(2.0, invert=True) == 14.0
    prof = FactorEngine().calculate_cross_sectional_profile(
        "FPT",
        date(2026, 11, 13),
        session=db_session,
        fundamentals={"roe": 25.0, "revenue_growth": 20.0, "pe": 12.0},
    )
    assert 0.0 <= prof.quality.score <= 100.0
    assert 0.0 <= prof.value.score <= 100.0


def test_market_dashboard_foreign_flow_modes(db_session: Session):
    db_session.query(MarketFlowDaily).delete()
    db_session.query(MacroObservation).filter(MacroObservation.series_id == "HOSE_FOREIGN_NET_FLOW").delete()
    db_session.flush()

    dash_empty = build_market_dashboard(db_session, as_of=date(2026, 11, 13))
    assert dash_empty.foreign_flow.status == "NOT_CONFIGURED"

    db_session.add(
        MarketFlowDaily(
            symbol="FPT",
            observation_date=date(2026, 11, 13),
            foreign_buy_value=120_000_000_000.0,
            foreign_sell_value=80_000_000_000.0,
            foreign_net_value=40_000_000_000.0,
            source="VPS_TEST",
        )
    )
    db_session.flush()

    dash_live = build_market_dashboard(db_session, as_of=date(2026, 11, 13))
    assert dash_live.foreign_flow.status == "AVAILABLE"
    assert dash_live.foreign_flow.value == 40.0
    assert dash_live.foreign_flow.details["stocks_covered"] == 1
    assert dash_live.foreign_flow.details["top_net_buy"][0]["symbol"] == "FPT"


def test_dividend_bilingual_dedup_prefers_structured_row(db_session: Session):
    sym = "DIVTST"
    asset = Asset(symbol=sym, name="Dividend Test Corp", asset_type="STOCK", exchange="HOSE", sector="CONSUMER")
    db_session.add(asset)
    db_session.flush()
    db_session.add(
        Price(
            asset_id=asset.id,
            observation_date=date(2026, 11, 13),
            raw_close=50_000.0,
            adjusted_close=50_000.0,
            adjustment_factor=1.0,
            volume=100_000.0,
            status="VALID",
            source="TEST",
        )
    )
    db_session.add_all([
        CorporateAction(
            symbol=sym,
            action_type="CASH_DIVIDEND",
            action_date=date(2026, 11, 10),
            value=None,
            currency="VND",
            notes="Tạm ứng cổ tức đợt 1/2026: 2500 đ/cp",
            source="TEST_NOTE",
        ),
        CorporateAction(
            symbol=sym,
            action_type="CASH_DIVIDEND",
            action_date=date(2026, 11, 11),
            ex_date=date(2026, 11, 10),
            payment_date=date(2026, 11, 25),
            value=2500.0,
            currency="VND",
            notes="First Dividend payment 2026: 2500 VND/share",
            source="TEST_STRUCTURED",
        ),
    ])
    db_session.flush()

    summary = DividendYieldEngine.calculate(db_session, sym, as_of=date(2026, 11, 13))
    assert len(summary.payments) == 1
    assert summary.ttm_cash_dividend == 2500.0
    assert summary.data_status == "AVAILABLE"


def test_ai_earnings_quality_gate_blocks_buy_on_low_cfo_to_ni():
    analyst = AIAnalyst()
    citations = [
        AICitation(id="E1", claim_type="FACT", responsible_module="market", metric="price", value=50000.0, symbol="TST", source="TEST", data_origin="CANONICAL"),
        AICitation(id="E2", claim_type="FACT", responsible_module="fundamentals", metric="pe", value=8.5, symbol="TST", source="TEST", data_origin="CANONICAL"),
        AICitation(id="E3", claim_type="FACT", responsible_module="fundamentals", metric="roe", value=20.0, symbol="TST", source="TEST", data_origin="CANONICAL"),
        AICitation(id="E4", claim_type="MODEL_OUTPUT", responsible_module="valuation", metric="margin_of_safety", value=25.0, symbol="TST", source="TEST", data_origin="CANONICAL"),
        AICitation(id="E5", claim_type="MODEL_OUTPUT", responsible_module="opportunity", metric="opportunity_score", value=75.0, symbol="TST", source="TEST", data_origin="CANONICAL"),
        AICitation(id="E6", claim_type="FACT", responsible_module="cashflow", metric="cfo_to_ni", value=0.12, symbol="TST", source="TEST", data_origin="CANONICAL"),
    ]
    claims, _ = analyst._build_investment_verdict_claims(citations, None, ["TST"])
    verdict_texts = [c.text for c in claims if "KẾT LUẬN & KHUYẾN NGHỊ" in c.text]
    assert verdict_texts
    assert not any("KHẢ QUAN — NÊN ĐẦU TƯ" in t for t in verdict_texts)
    assert any("CFO/LN ròng" in t for t in verdict_texts)


def test_walk_forward_signal_calibration_ic_and_pit_gate(db_session: Session):
    empty_cal = HistoricalBacktestEngine(db_session).evaluate_signal_calibration(date(2026, 11, 13), horizon_days=20)
    assert empty_cal["status"] == "INSUFFICIENT_DATA"

    base_d = date(2025, 2, 1)
    for idx in range(6):
        sym = f"CAL{idx}"
        asset = Asset(symbol=sym, name=f"Cal Asset {idx}", asset_type="STOCK", exchange="HOSE", sector="TECH")
        db_session.add(asset)
        db_session.flush()
        p0 = 20_000.0
        p1 = 20_000.0 * (1.0 + (idx - 1) * 0.04)
        db_session.add_all([
            Price(asset_id=asset.id, observation_date=base_d, raw_close=p0, adjusted_close=p0, status="VALID", source="TEST"),
            Price(asset_id=asset.id, observation_date=base_d + timedelta(days=25), raw_close=p1, adjusted_close=p1, status="VALID", source="TEST"),
            AssetDecisionSnapshot(
                asset_id=asset.id,
                snapshot_data={
                    "facts": {
                        "as_of_date": base_d.isoformat(),
                        "modules": {"opportunity": {"score": 30.0 + idx * 12.0}},
                    }
                },
            ),
        ])
    db_session.flush()

    cal = HistoricalBacktestEngine(db_session).evaluate_signal_calibration(date(2026, 11, 13), horizon_days=20)
    assert cal["status"] == "AVAILABLE"
    assert cal["sample_size"] >= 6
    assert cal["ic_pearson"] > 0.7
    assert cal["rank_ic_spearman"] > 0.7
    assert cal["hit_rate"] >= 0.65
