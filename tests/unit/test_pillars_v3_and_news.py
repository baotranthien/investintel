"""Regression & unit test suite for V2 residual fixes, 6 Pillars AI accuracy upgrades, and Pillar 7 news pipeline."""
from __future__ import annotations

from datetime import date

from database.models import Asset, CorporateAction, MacroAnalysisLog, Price
from services.ai.analyst import AIAnalyst
from services.ai.planner import QueryIntent, QueryPlanner
from services.ai.prompt_registry import build_chat_prompt
from services.ai.schemas import AICitation, AIClaim
from services.ai.tools import _parse_wacc_g_shock
from services.fundamentals.dividends import DividendYieldEngine
from services.news import (
    GeminiMacroNewsAnalyzer,
    MacroAnalysisValidator,
    OfficialNewsCrawler,
    SOURCE_REGISTRY,
)
from services.research.rag import LocalVectorStore
from services.valuation.builder import ValuationSnapshotBuilder
from services.valuation.engine import DCFEngine
from services.valuation.models import DCFAssumptions


def test_dividend_yield_engine_mbb_outlier_and_issuance_guard(db_session):
    """Ensure share-count outliers (>30,000) and rights issue offer prices never inflate TTM dividend yield."""
    asset = Asset(
        symbol="MBB_TEST",
        name="MBB Dividend Guard Test",
        asset_type="STOCK",
        exchange="HOSE",
        sector="BANK",
    )
    db_session.add(asset)
    db_session.flush()

    db_session.add(
        Price(
            asset_id=asset.id,
            observation_date=date(2026, 11, 15),
            raw_close=20000.0,
            adjusted_close=20000.0,
            volume=1_000_000,
            status="VALID",
        )
    )
    # 1) Stock dividend row mistakenly containing share count (1.2B)
    db_session.add(
        CorporateAction(
            symbol="MBB_TEST",
            action_date=date(2026, 7, 31),
            action_type="STOCK_DIVIDEND",
            value=1_208_249_986.0,
            notes="Trả cổ tức năm 2025, tỷ lệ 100:15",
        )
    )
    # 2) Rights offering event with 10,000 VND/share issue price in notes
    db_session.add(
        CorporateAction(
            symbol="MBB_TEST",
            action_date=date(2026, 8, 5),
            action_type="CORPORATE_EVENT",
            value=805_499_990.0,
            notes="Phát hành 805,499,990 cp cho CĐHH, giá 10000 đ/cp",
        )
    )
    # 3) Actual 1,000 VND/share cash dividend
    db_session.add(
        CorporateAction(
            symbol="MBB_TEST",
            action_date=date(2026, 6, 29),
            action_type="CASH_DIVIDEND",
            value=1000.0,
            notes="Trả cổ tức năm 2025 (1000 đ/cp)",
        )
    )
    db_session.flush()

    summary = DividendYieldEngine.calculate(db_session, "MBB_TEST", as_of=date(2026, 11, 15))
    assert summary.ttm_cash_dividend == 1000.0
    assert summary.ttm_dividend_yield == 5.0


def test_real_estate_rnav_normalization_and_capex_floor():
    """Real estate handover peaks must trigger landbank capex floor (>=10%) and BVPS-anchored RNAV normalization."""
    builder = ValuationSnapshotBuilder("VHM", "REAL_ESTATE")
    re_fund = {
        "symbol": "VHM",
        "sector": "REAL_ESTATE",
        "eps_ttm": 8000.0,
        "bvps": 45000.0,
        "shares_outstanding": 4_354_000_000,
        "revenue_ttm": 120000.0,
        "revenue_yoy": 0.25,
        "revenue_cagr_3y": 0.20,
        "operating_margin": 0.45,
        "wacc": 0.11,
        "cost_of_equity": 0.125,
        "roe": 22.0,
        "peer_pe": 10.0,
        "peer_pb": 1.3,
        "use_dynamic_assumptions": True,
    }
    dcf_assump, cost_of_equity, is_re, is_cyclical = builder.build_dcf_context(re_fund)
    assert cost_of_equity > 0
    assert is_re is True
    assert is_cyclical is True
    assert dcf_assump.capex_percent_rev is not None and dcf_assump.capex_percent_rev >= 0.10

    raw_dcf = DCFEngine.calculate(dcf_assump, shares_outstanding=re_fund["shares_outstanding"], net_debt=0.0)
    snap = builder.build(re_fund, current_price=42000.0, as_of=date(2026, 11, 15))
    dcf_method = next(m for m in snap.methods if m.method == "DCF")

    if raw_dcf.fair_value.base > re_fund["bvps"] * 1.45:
        assert dcf_method.fair_value.base <= re_fund["bvps"] * 1.45 + 1.0


def test_dcf_custom_shock_simulator_and_parser():
    """Custom WACC / terminal-growth shocks must evaluate deterministically from natural language queries."""
    dw, dg = _parse_wacc_g_shock("Nếu WACC tăng thêm 1.5% và tốc độ tăng trưởng dài hạn (g) giảm 0.5% thì giá hợp lý VNM thế nào?")
    assert dw == 1.5
    assert dg == -0.5

    assump = DCFAssumptions(
        revenue_growth_rates=[0.08] * 5,
        ebit_margins=[0.20] * 5,
        tax_rate=0.20,
        wacc=0.11,
        terminal_growth_rate=0.03,
        base_revenue=60000.0,
    )
    shock = DCFEngine.evaluate_custom_shock(
        assump,
        shares_outstanding=2_089_955_445,
        net_debt=0.0,
        wacc_delta_pct=dw,
        g_delta_pct=dg,
    )
    assert shock["valid"] is True
    assert shock["shocked_wacc_pct"] == 12.5
    assert shock["shocked_g_pct"] == 2.5
    assert shock["shocked_fair_value"] < shock["base_fair_value"]
    assert shock["delta_pct"] < 0


def test_temporal_decay_rag_prefers_2026_over_2024():
    """Hybrid RAG temporal decay must boost recent <=365d documents and annotate/decay >365d legacy filings."""
    hits = [
        {
            "document_id": "FPT-2024-LEGACY",
            "publication_date": "2024-04-10",
            "score": 0.90,
            "snippet": "Chiến lược 2024 AI Factory.",
        },
        {
            "document_id": "FPT-2026-Q3",
            "publication_date": "2026-10-30",
            "score": 0.70,
            "snippet": "Cập nhật Q3/2026 tách hợp nhất Viễn thông & AI Factory.",
        },
    ]
    decayed = LocalVectorStore._apply_temporal_decay(hits, ref_date=date(2026, 11, 15))
    assert decayed[0]["document_id"] == "FPT-2026-Q3"
    assert decayed[1]["document_id"] == "FPT-2024-LEGACY"
    assert decayed[1]["section"].startswith("[Hồ sơ lịch sử 2024]")


def test_stratified_prompt_packing_for_3_banks():
    """Stratified (metric, symbol) packing must retain NIM, CASA, NPL, and LLR for all 3 banks without starving TCB."""
    evidence = []
    # High-count noise items on VCB to attempt crowding out other metrics/symbols
    for i in range(15):
        evidence.append({
            "id": f"EN{i}",
            "metric": "operating_expense",
            "symbol": "VCB",
            "value": 1000.0 + i,
            "source": "CANONICAL_DATABASE",
            "data_origin": "CANONICAL_DATABASE",
            "freshness": "AVAILABLE",
            "claim_type": "FACT",
        })
    idx = 1
    for sym in ("VCB", "MBB", "TCB"):
        for metric, val in (("nim", 3.5), ("casa_ratio", 35.0), ("npl_ratio", 1.2), ("llr_ratio", 120.0)):
            evidence.append({
                "id": f"E{idx:03d}",
                "metric": metric,
                "symbol": sym,
                "value": val,
                "unit": "%",
                "source": "CANONICAL_DATABASE",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "claim_type": "FACT",
            })
            idx += 1

    prompt = build_chat_prompt(
        question="So sánh biên NIM, tỷ lệ CASA, nợ xấu NPL và LLR của VCB, MBB và TCB",
        context={"symbols": ["VCB", "MBB", "TCB"], "symbol": "VCB", "evidence": evidence},
    )
    for sym in ("VCB", "MBB", "TCB"):
        assert f'"{sym}"' in prompt
    for metric in ("nim", "casa_ratio", "npl_ratio", "llr_ratio"):
        assert prompt.count(f'"{metric}"') >= 3


def test_query_planner_routes_portfolio_dca_to_portfolio(db_session):
    """Q8 portfolio allocation & DCA queries must resolve to PORTFOLIO, never VN100 proxy context."""
    plan = QueryPlanner.plan_query(
        "Với số vốn 500 triệu VND và kế hoạch DCA 20 triệu/tháng trong 12 tháng tới, hệ thống đề xuất phân bổ tỷ trọng danh mục như thế nào?",
        db_session,
    )
    assert plan.symbols == ["PORTFOLIO"]
    assert plan.intent == QueryIntent.PORTFOLIO


def test_critic_verifier_strips_false_missing_data_claims():
    """2-pass Critic-Verifier must prune contradictory missing-data claims when valid citations exist."""
    citations = [
        AICitation(
            id="E001",
            claim_type="FACT",
            responsible_module="market",
            metric="revenue_commodity_correlation",
            value=0.61,
            symbol="PLX",
            freshness="AVAILABLE",
        ),
        AICitation(
            id="E002",
            claim_type="FACT",
            responsible_module="valuation",
            metric="pe",
            value=14.2,
            symbol="PLX",
            freshness="AVAILABLE",
        ),
        AICitation(
            id="E003",
            claim_type="FACT",
            responsible_module="fundamentals",
            metric="npl_ratio",
            value=1.68,
            symbol="MBB",
            freshness="AVAILABLE",
        ),
        AICitation(
            id="E004",
            claim_type="FACT",
            responsible_module="fundamentals",
            metric="llr_ratio",
            value=76.0,
            symbol="MBB",
            freshness="AVAILABLE",
        ),
        AICitation(
            id="E005",
            claim_type="FACT",
            responsible_module="fundamentals",
            metric="casa_ratio",
            value=37.8,
            symbol="MBB",
            freshness="AVAILABLE",
        ),
    ]
    claims = [
        AIClaim(claim_type="UNCERTAINTY", text="Dữ liệu tài chính và định giá cho mã PLX hiện chưa có sẵn.", citation_ids=[]),
        AIClaim(claim_type="UNCERTAINTY", text="Hiện chưa có dữ liệu tỷ lệ nợ xấu (NPL) và LLR cho mã MBB.", citation_ids=[]),
        AIClaim(claim_type="FACT", text="Tỷ lệ CASA của MBB đạt 37.8%.", citation_ids=["E005"]),
    ]

    kept, corrections = AIAnalyst._run_critic_verifier_pass(claims, citations)
    assert corrections == 2
    assert len(kept) == 1
    assert "37.8%" in kept[0].text


def test_pillar7_official_news_crawler_analyzer_and_validator(db_session):
    """Pillar 7 must assign trust hierarchy, emit structured JSON, backtest-validate, and persist MacroAnalysisLog."""
    assert SOURCE_REGISTRY["sbv.gov.vn"].trust_level == 10
    assert SOURCE_REGISTRY["vneconomy.vn"].trust_level == 8
    assert SOURCE_REGISTRY["cafef.vn"].trust_level == 7

    crawler = OfficialNewsCrawler()
    items = crawler.crawl(as_of_date=date(2026, 11, 15), fetch_live=False)
    assert len(items) >= 4
    assert any(
        "ngan-hang-nha-nuoc-mua-ngoai-te-can-thiep-post675390.antd" in item.url
        for item in items
    )

    analyzer = GeminiMacroNewsAnalyzer()
    analyzed = analyzer.analyze(items, as_of_date=date(2026, 11, 15), use_gemini=False)
    assert analyzed["date"] == "2026-11-15"
    assert len(analyzed["events"]) >= 1
    first_event = analyzed["events"][0]
    assert "stock_market_correlation" in first_event
    assert "ai_confidence_score" in first_event

    validator = MacroAnalysisValidator(db_session)
    saved = validator.validate_and_persist(analyzed, index_to_rag=False)
    assert len(saved) >= 1
    assert db_session.query(MacroAnalysisLog).count() >= 1


def test_macro_prompt_prioritizes_1730_news_fedfunds_hrc_and_crack_spread():
    """
    build_chat_prompt must retain macro_event_news, fedfunds, hrc_steel_price, and
    singapore_crack_spread even when query_symbols contains VN100 or sector tickers (HPG, BSR, PLX).
    """
    def _ev(eid: str, metric: str, sym: str, val: object, note: str = "") -> dict:
        return {
            "id": eid,
            "claim_type": "MODEL_OUTPUT" if metric == "macro_event_news" else "FACT",
            "metric": metric,
            "symbol": sym,
            "value": val,
            "source": "CANONICAL_TEST",
            "data_origin": "CANONICAL_DATABASE",
            "freshness": "AVAILABLE",
            "note": note,
        }

    # 1. Macro VN100 query (Q7)
    prompt_q7 = build_chat_prompt(
        "VN100 đang ở market regime nào, lãi suất FED và tin tức NHNN 17:30 tác động ra sao?",
        {
            "symbols": ["VN100"],
            "evidence_register": [
                _ev("M01", "market_regime", "VN100", "NEUTRAL"),
                _ev("M02", "vnm_cpi_yoy", "MARKET", 3.4),
                _ev("M03", "fedfunds", "MARKET", 4.75, "FEDFUNDS 4.75%"),
                _ev("M04", "sbv_policy_rate", "MARKET", 4.5),
                _ev("M05", "macro_event_news", "MARKET", 92.0, "NHNN mua ngoại tệ"),
            ],
        },
    )
    assert "macro_event_news" in prompt_q7
    assert "fedfunds" in prompt_q7

    # 2. Steel HPG query (Q4)
    prompt_q4 = build_chat_prompt(
        "Đánh giá HPG theo giá thép HRC và hàng tồn kho",
        {
            "symbols": ["HPG"],
            "evidence_register": [
                _ev("S01", "pe", "HPG", 14.5),
                _ev("S02", "hrc_steel_price", "HRC_STEEL", 518.5, "HRC 518.5 USD/tấn"),
                _ev("S03", "inventory", "HPG", 42000.0),
            ],
        },
    )
    assert "hrc_steel_price" in prompt_q4

    # 3. Oil BSR/PLX query (Q10)
    prompt_q10 = build_chat_prompt(
        "So sánh BSR và PLX khi giá dầu Brent và Singapore crack spread biến động, kèm tin tức vĩ mô",
        {
            "symbols": ["BSR", "PLX"],
            "evidence_register": [
                _ev("O01", "pe", "BSR", 18.2),
                _ev("O02", "pe", "PLX", 14.1),
                _ev("O03", "brent_close", "BRENT", 74.8),
                _ev("O04", "singapore_crack_spread", "CRACK_SPREAD", 14.2),
                _ev("O05", "macro_event_news", "MARKET", 85.0, "NHNN can thiệp tỷ giá"),
            ],
        },
    )
    assert "singapore_crack_spread" in prompt_q10
    assert "brent_close" in prompt_q10
    assert "macro_event_news" in prompt_q10


def test_verdict_claims_surfaces_macro_benchmarks_and_1730_news():
    """_build_investment_verdict_claims must isolate commodities by sector, ignore SEEDED_OR_UNTRACED, and dedup FEDFUNDS."""
    citations = [
        AICitation(id="E001", claim_type="FACT", responsible_module="valuation", metric="pe", value=14.5, symbol="HPG", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="roe", value=13.2, symbol="HPG", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        AICitation(id="E003", claim_type="FACT", responsible_module="macro", metric="hrc_steel_price", value=518.5, symbol="HRC_STEEL", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="Giá thép HRC: 518.5 USD/tấn."),
        AICitation(id="E004", claim_type="FACT", responsible_module="macro", metric="singapore_crack_spread", value=14.2, symbol="CRACK_SPREAD", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="Crack spread Singapore: 14.2 USD/thùng."),
        AICitation(id="E005", claim_type="MODEL_OUTPUT", responsible_module="macro", metric="macro_event_news", value=92.0, symbol="MARKET", source="sbv.gov.vn (Trust 10/10)", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="[Tin vĩ mô 17:30] NHNN mua ngoại tệ."),
        AICitation(id="E006", claim_type="FACT", responsible_module="macro", metric="FEDFUNDS", value=4.75, symbol="MARKET", source="FRED", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="Lãi suất FEDFUNDS đạt 4.75%."),
        AICitation(id="E007", claim_type="FACT", responsible_module="macro", metric="us_fed_funds_rate", value=4.75, symbol="MARKET", source="FRED", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="US Fed Funds Rate: 4.75%."),
        AICitation(id="E008", claim_type="UNCERTAINTY", responsible_module="macro", metric="brent_close", value=75.0, symbol="MARKET", source="HOSE_CSV", data_origin="SEEDED_OR_UNTRACED", freshness="AVAILABLE", note="Seeded/static or untraced input; not verified as live source evidence."),
        AICitation(id="E009", claim_type="FACT", responsible_module="macro", metric="brent_close", value=95.84, symbol="BRENT", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="Giá dầu Brent: 95.84 USD/thùng."),
    ]
    analyst = AIAnalyst.__new__(AIAnalyst)

    # 1. Steel HPG gets HRC_STEEL + 17:30 news, NOT Crack Spread or Brent
    verdict_hpg, used_hpg = analyst._build_investment_verdict_claims(
        citations=citations,
        structured_summary=None,
        extracted_symbols=["HPG"],
        existing_claims=[],
    )
    hpg_text = " ".join(c.text for c in verdict_hpg)
    assert "HRC" in hpg_text
    assert "NHNN mua ngoại tệ" in hpg_text
    assert "Crack spread" not in hpg_text
    assert {"E003", "E005"} <= used_hpg
    assert "E004" not in used_hpg
    assert "E008" not in used_hpg

    # 2. Oil BSR gets Crack Spread + canonical Brent, NEVER SEEDED_OR_UNTRACED E008 or HRC_STEEL
    bsr_cits = [
        AICitation(id="E010", claim_type="FACT", responsible_module="valuation", metric="pe", value=4.5, symbol="BSR", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        AICitation(id="E011", claim_type="FACT", responsible_module="fundamentals", metric="roe", value=35.0, symbol="BSR", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        *citations[2:],
    ]
    verdict_bsr, used_bsr = analyst._build_investment_verdict_claims(
        citations=bsr_cits,
        structured_summary=None,
        extracted_symbols=["BSR"],
        existing_claims=[],
    )
    bsr_text = " ".join(c.text for c in verdict_bsr)
    assert "Crack spread" in bsr_text
    assert "95.84" in bsr_text
    assert "Seeded/static" not in bsr_text
    assert "HRC" not in bsr_text
    assert {"E004", "E009"} <= used_bsr
    assert "E008" not in used_bsr

    # 3. Tech FPT must get NEITHER Steel nor Oil commodities
    fpt_cits = [
        AICitation(id="E020", claim_type="FACT", responsible_module="valuation", metric="pe", value=9.18, symbol="FPT", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        AICitation(id="E021", claim_type="FACT", responsible_module="fundamentals", metric="roe", value=24.2, symbol="FPT", source="CANONICAL", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE"),
        *citations[2:],
    ]
    verdict_fpt, _ = analyst._build_investment_verdict_claims(
        citations=fpt_cits,
        structured_summary=None,
        extracted_symbols=["FPT"],
        existing_claims=[],
    )
    fpt_text = " ".join(c.text for c in verdict_fpt)
    assert "HRC" not in fpt_text
    assert "Crack spread" not in fpt_text
    assert "Seeded/static" not in fpt_text

    # 4. Macro-only query (Q7) avoids duplicating FEDFUNDS when already cited in uppercase & skips alias
    macro_verdict, macro_used = analyst._build_investment_verdict_claims(
        citations=[citations[4], citations[5], citations[6]],
        structured_summary=None,
        extracted_symbols=["VN100"],
        existing_claims=[AIClaim(claim_type="FACT", text="Fed 4.75%.", citation_ids=["E006"])],
    )
    macro_text = " ".join(c.text for c in macro_verdict)
    assert "NHNN mua ngoại tệ" in macro_text
    assert "US Fed Funds Rate" not in macro_text
    assert "E007" not in macro_used


def test_comma_explicit_symbols_split_and_critic_dcf_custom():
    """QueryPlanner splits 'VCB, MBB, TCB' cleanly and critic removes false DCF sensitivity missing claims."""
    from services.ai.planner import QueryPlanner

    plan = QueryPlanner.plan_query(
        "So sánh NIM của VCB, MBB và TCB",
        session=None,
        explicit_symbol="VCB, MBB, TCB",
    )
    assert plan.symbols == ["VCB", "MBB", "TCB"]

    analyst = AIAnalyst.__new__(AIAnalyst)
    cits = [
        AICitation(id="E001", claim_type="MODEL_OUTPUT", responsible_module="valuation", metric="dcf_custom_sensitivity", value=-18.3, symbol="VNM", source="DCF", data_origin="CANONICAL_DATABASE", freshness="AVAILABLE", note="WACC +1.5%, g -0.5% -> -18.30%"),
    ]
    claims = [
        AIClaim(claim_type="FACT", text="Độ nhạy DCF của VNM chưa thể hiện chính xác sai số phần trăm theo yêu cầu.", citation_ids=["E001"]),
        AIClaim(claim_type="MODEL_OUTPUT", text="Thay đổi DCF đạt -18.30%.", citation_ids=["E001"]),
    ]
    kept, fixes = analyst._run_critic_verifier_pass(claims, cits)
    assert fixes == 1
    assert len(kept) == 1
    assert "-18.30%" in kept[0].text

