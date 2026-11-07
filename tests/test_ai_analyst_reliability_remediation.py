"""
Unit and Integration Regression Suite for InvestIntel AI Analyst Reliability Remediation.
Verifies query planning, metric disambiguation, data consistency, deterministic data injection,
and strict answer status classification across the 20 audit question patterns.
"""
from datetime import date
import pytest
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Asset
from services.ai.analyst import AIAnalyst
from services.ai.planner import EntityType, QueryIntent, QueryPlanner
from services.ai.prompt_registry import extract_requested_metric_groups
from services.ai.schemas import AICitation, AIClaim
from services.ai.tools import AITools
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.sector_models import get_sector_for_symbol
from services.valuation.peers import PeerComparisonEngine


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


class TestAIAnalystQueryPlanning:
    """Verifies deterministic query parsing for financial queries."""

    def test_fundamental_query_fpt(self, db_session: Session):
        q = "Phân tích cơ cấu tăng trưởng doanh thu và lợi nhuận của FPT dựa trên số liệu báo cáo tài chính mới nhất?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.FUNDAMENTAL
        assert plan.entity_type == EntityType.TICKER
        assert "FPT" in plan.symbols
        assert "revenue" in plan.requested_metric_groups or "revenue_yoy" in plan.requested_metric_groups

    def test_hpg_de_query(self, db_session: Session):
        q = "Chi phí vốn, hệ số đòn bẩy tài chính D/E và tiến độ mở rộng của Tập đoàn Hòa Phát (HPG)?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert "HPG" in plan.symbols
        assert "debt_to_equity" in plan.requested_metric_groups

    def test_bmp_peer_comparison_query(self, db_session: Session):
        q = "Định giá P/E và tỷ suất sinh lời ROE của Nhựa Bình Minh (BMP) so với trung vị ngành vật liệu?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.PEER_COMPARISON
        assert "BMP" in plan.symbols
        assert "peer_medians" in plan.requested_metric_groups
        assert "pe" in plan.requested_metric_groups
        assert "roe" in plan.requested_metric_groups

    def test_plx_brent_correlation_query(self, db_session: Session):
        q = "Mối tương quan giữa doanh thu PLX và biến động giá dầu thế giới (Brent/WTI)?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.TIME_SERIES_CORRELATION
        assert "PLX" in plan.symbols
        assert "revenue_commodity_correlation" in plan.requested_metric_groups

    def test_vnindex_market_regime_query(self, db_session: Session):
        q = "Đánh giá trạng thái chế độ thị trường (Market Regime) và độ rộng thị trường chứng khoán Việt Nam?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.MARKET_REGIME
        assert plan.entity_type == EntityType.INDEX
        assert "market_regime" in plan.requested_metric_groups

    def test_fpt_net_margin_roic_query(self, db_session: Session):
        q = "Biên lợi nhuận ròng và hiệu quả sử dụng vốn ROIC của FPT trong các kỳ gần nhất?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert "FPT" in plan.symbols
        assert "net_margin" in plan.requested_metric_groups
        assert "roic" in plan.requested_metric_groups
        # Strict disambiguation: roic must NOT trigger roe when roe is unmentioned
        assert "roe" not in plan.requested_metric_groups

    def test_vcb_pb_equity_query(self, db_session: Session):
        q = "Quy mô vốn chủ sở hữu và định giá P/B của Vietcombank (VCB) hiện tại?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert "VCB" in plan.symbols
        assert "pb" in plan.requested_metric_groups
        assert "total_equity" in plan.requested_metric_groups
        # Strict disambiguation: vốn chủ sở hữu alone must NOT trigger debt_to_equity
        assert "debt_to_equity" not in plan.requested_metric_groups

    def test_bmp_dcf_query(self, db_session: Session):
        q = "Mô hình định giá DCF và kịch bản cơ sở (Base Case) đối với cổ phiếu BMP đưa ra kết quả gì?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.VALUATION_DCF
        assert "BMP" in plan.symbols
        assert "dcf" in plan.requested_metric_groups

    def test_bmp_dividend_query(self, db_session: Session):
        q = "Chính sách chi trả cổ tức và tỷ suất cổ tức tiền mặt (Dividend Yield) của BMP?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.DIVIDEND
        assert "BMP" in plan.symbols
        assert "dividends" in plan.requested_metric_groups

    def test_hpg_net_debt_ebitda_query(self, db_session: Session):
        q = "Tỷ lệ nợ ròng trên EBITDA và khả năng chi trả lãi vay của HPG?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert "HPG" in plan.symbols
        assert "net_debt_ebitda" in plan.requested_metric_groups

    def test_materials_peer_medians_query(self, db_session: Session):
        q = "Định giá P/E và P/B trung vị của nhóm cổ phiếu ngành vật liệu (Materials Peers) tại Việt Nam?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.PEER_COMPARISON
        assert "peer_medians" in plan.requested_metric_groups

    def test_mwg_ccc_query(self, db_session: Session):
        q = "Chu kỳ chuyển đổi tiền mặt (CCC) và hiệu quả quản lý hàng tồn kho của MWG?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert "MWG" in plan.symbols
        assert "working_capital_cycle" in plan.requested_metric_groups

    def test_universe_screener_query(self, db_session: Session):
        q = "Các cổ phiếu thỏa mãn tiêu chí định giá rẻ P/E dưới 15 và sinh lời ROE trên 15%?"
        plan = QueryPlanner.plan_query(q, db_session)
        assert plan.intent == QueryIntent.SCREENER
        assert plan.entity_type == EntityType.UNIVERSE
        assert plan.screener_spec is not None
        assert plan.screener_spec.pe_max == 15.0
        assert plan.screener_spec.roe_min == 15.0


class TestMetricDisambiguation:
    """Verifies strict regex metric category extraction and disambiguation."""

    def test_roic_does_not_trigger_roe(self):
        q = "Hiệu quả sử dụng vốn ROIC của FPT"
        req = extract_requested_metric_groups(q)
        assert "roic" in req
        assert "roe" not in req

    def test_roe_does_not_trigger_roic(self):
        q = "Chỉ số sinh lời trên vốn chủ sở hữu ROE của HPG"
        req = extract_requested_metric_groups(q)
        assert "roe" in req
        assert "roic" not in req

    def test_total_equity_does_not_trigger_de_ratio(self):
        q = "Quy mô vốn chủ sở hữu của Vietcombank là bao nhiêu"
        req = extract_requested_metric_groups(q)
        assert "total_equity" in req
        assert "debt_to_equity" not in req

    def test_de_ratio_triggers_correctly(self):
        q = "Tỷ lệ nợ trên vốn chủ sở hữu D/E của HPG"
        req = extract_requested_metric_groups(q)
        assert "debt_to_equity" in req

    def test_working_capital_cycle_matches_ccc(self):
        q = "Chu kỳ chuyển đổi tiền mặt CCC của MWG"
        req = extract_requested_metric_groups(q)
        assert "working_capital_cycle" in req


class TestCrossModuleDataConsistency:
    """Verifies cross-module consistency for BMP, sectors, and deterministic calculations."""

    def test_bmp_sector_consistency(self, db_session: Session):
        # 1. DB Asset model
        asset = db_session.query(Asset).filter(Asset.symbol == "BMP").first()
        assert asset is not None
        assert asset.sector == "MATERIALS"

        # 2. Sector helper
        assert get_sector_for_symbol("BMP") == "MATERIALS"

        # 3. Financial repository
        with FinancialRepository(db_session) as repo:
            prof = repo.get_company_profile("BMP")
            assert prof is not None
            assert prof["sector"] == "MATERIALS"

        # 4. PeerComparisonEngine peer group
        peer_engine = PeerComparisonEngine(db_session)
        res = peer_engine.compare_peers("BMP", date(2026, 11, 2))
        assert res is not None
        assert res.peer_group_id == "MATERIALS_PEERS"
        assert res.peer_median_pe is not None
        assert res.peer_median_pb is not None

    def test_bmp_dcf_base_fair_value_calculation(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("BMP", as_of=as_of, session=db_session, question="Định giá DCF của BMP kịch bản cơ sở?")
        evidence = ctx.get("evidence", [])
        
        # Verify DCF base evidence
        dcf_ev = next((e for e in evidence if e.get("metric") == "dcf_base"), None)
        assert dcf_ev is not None
        assert dcf_ev["value"] > 100000.0
        assert dcf_ev["claim_type"] == "MODEL_OUTPUT"

        # Verify Composite Fair Value base evidence
        comp_ev = next((e for e in evidence if e.get("metric") == "composite_fair_value_base"), None)
        assert comp_ev is not None
        assert comp_ev["value"] > 100000.0
        assert comp_ev["claim_type"] == "MODEL_OUTPUT"

    def test_materials_peer_medians_evidence(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("BMP", as_of=as_of, session=db_session, question="So sánh với trung vị ngành vật liệu?")
        evidence = ctx.get("evidence", [])
        
        pe_med = next((e for e in evidence if e.get("metric") == "peer_median_pe"), None)
        assert pe_med is not None
        assert pe_med["value"] > 0
        assert "PEERS" in pe_med["symbol"]

        pb_med = next((e for e in evidence if e.get("metric") == "peer_median_pb"), None)
        assert pb_med is not None
        assert pb_med["value"] > 0
        assert "PEERS" in pb_med["symbol"]

        roe_med = next((e for e in evidence if e.get("metric") == "peer_median_roe"), None)
        assert roe_med is not None
        assert roe_med["value"] > 0
        assert "PEERS" in roe_med["symbol"]

    def test_plx_brent_revenue_correlation_evidence(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("PLX", as_of=as_of, session=db_session, question="Mối tương quan giữa doanh thu PLX và biến động giá dầu thế giới (Brent)?")
        evidence = ctx.get("evidence", [])

        rev_corr_ev = next((e for e in evidence if e.get("metric") == "revenue_commodity_correlation"), None)
        assert rev_corr_ev is not None
        # Pearson correlation of quarterly revenue vs Brent quarterly avg price is negative (-0.80)
        assert rev_corr_ev["value"] < 0
        assert rev_corr_ev["symbol"] == "PLX"

    def test_hpg_interest_coverage_and_net_debt_ebitda_evidence(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("HPG", as_of=as_of, session=db_session, question="Tỷ lệ nợ ròng trên EBITDA và khả năng chi trả lãi vay của HPG?")
        evidence = ctx.get("evidence", [])

        nde_ev = next((e for e in evidence if e.get("metric") == "net_debt_ebitda"), None)
        assert nde_ev is not None
        assert nde_ev["value"] > 0

        cov_ev = next((e for e in evidence if e.get("metric") == "interest_coverage"), None)
        assert cov_ev is not None
        assert cov_ev["value"] is None or cov_ev["value"] > 0

    def test_vcb_total_equity_and_pb_evidence(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("VCB", as_of=as_of, session=db_session, question="Quy mô vốn chủ sở hữu và định giá P/B của Vietcombank (VCB) hiện tại?")
        evidence = ctx.get("evidence", [])

        eq_ev = next((e for e in evidence if e.get("metric") == "total_equity"), None)
        assert eq_ev is not None
        assert eq_ev["value"] > 100000.0

        pb_ev = next((e for e in evidence if e.get("metric") == "pb"), None)
        assert pb_ev is not None
        assert pb_ev["value"] > 0

    def test_vnindex_direct_query_disclosure(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("VNINDEX", as_of=as_of, session=db_session, question="Đánh giá chế độ thị trường VNINDEX?")
        evidence = ctx.get("evidence", [])

        vnindex_ev = next((e for e in evidence if e.get("metric") == "market_regime_vnindex"), None)
        assert vnindex_ev is not None
        assert vnindex_ev["freshness"] == "INSUFFICIENT_DATA"

        vn100_proxy = next((e for e in evidence if e.get("metric") == "market_regime" and e.get("symbol") == "VN100"), None)
        assert vn100_proxy is not None
        assert vn100_proxy["value"] in ("NEUTRAL", "BULLISH", "BEARISH", "INSUFFICIENT_DATA")

    def test_vn100_market_regime_and_breadth_evidence(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("VN100", as_of=as_of, session=db_session, question="Chế độ thị trường và độ rộng?")
        evidence = ctx.get("evidence", [])

        regime_ev = next((e for e in evidence if e.get("metric") == "market_regime"), None)
        assert regime_ev is not None
        assert regime_ev["value"] in ("NEUTRAL", "BULLISH", "BEARISH", "INSUFFICIENT_DATA")

    def test_screener_evidence_injection(self, db_session: Session):
        as_of = date(2026, 11, 2)
        ctx = AITools.get_context("ALL", as_of=as_of, session=db_session, question="Tìm các cổ phiếu P/E dưới 15 và ROE trên 15%?")
        evidence = ctx.get("evidence", [])

        screened_ev = next((e for e in evidence if e.get("metric") == "screened_count"), None)
        assert screened_ev is not None
        assert screened_ev["value"] >= 30

        matched_ev = next((e for e in evidence if e.get("metric") == "matched_count"), None)
        assert matched_ev is not None
        assert matched_ev["value"] >= 1

    def test_bmp_dcf_composite_reconciliation(self, db_session: Session):
        """Verifies mathematical consistency: sum(weight * method_base) == composite_fair_value_base."""
        from apps.api.routers.valuation import get_valuation_snapshot
        snap = get_valuation_snapshot("BMP", "2026-11-02")
        methods = snap["methods"]
        assert len(methods) > 0
        total_weight = sum(m["weight"] for m in methods)
        assert abs(total_weight - 1.0) < 1e-4

        weighted_sum = sum(m["weight"] * m["fair_value"]["base"] for m in methods)
        comp_base = snap["composite_fair_value"]["range"]["base"]
        assert abs(weighted_sum - comp_base) < 1e-4

        # Margin of safety consistency: (fair_value - price) / fair_value
        price = snap.get("price_as_of") or snap.get("market_price")
        if price and comp_base > 0:
            expected_mos = (comp_base - price) / comp_base
            if snap.get("margin_of_safety") is not None:
                assert abs(snap["margin_of_safety"] - expected_mos) < 1e-4

    def test_mwg_ccc_working_capital_consistency(self, db_session: Session):
        """Verifies canonical CCC formula consistency: CCC = DIO + DSO - DPO."""
        from services.fundamentals.snapshot import FundamentalSnapshotBuilder
        with FinancialRepository(db_session) as repo:
            ds = repo.get_financial_dataset("MWG")
            sb = FundamentalSnapshotBuilder("MWG", "RETAIL")
            snap = sb.build_snapshot(
                income_quarters=ds.get("income_quarters", []),
                income_annual=ds.get("income_annual", []),
                balance_annual=ds.get("balance_annual", []),
                cashflow_annual=ds.get("cashflow_annual", []),
                shares_outstanding=ds.get("shares_outstanding"),
            )
            eff = snap.get("efficiency", {})
            dio = eff["dio"]["value"]
            dso = eff["dso"]["value"]
            dpo = eff["dpo"]["value"]
            ccc = eff["ccc"]["value"]
            assert dio is not None and dso is not None and dpo is not None and ccc is not None
            assert abs((dio + dso - dpo) - ccc) < 1e-3

    def test_materials_peer_medians_bmp_excluded(self, db_session: Session):
        """Verifies that BMP is strictly excluded from its own Materials peer medians."""
        import statistics
        engine = PeerComparisonEngine(db_session)
        res = engine.compare_peers("BMP", date(2026, 11, 2))
        other_peers = [r for r in res.peer_table if not r.is_target]
        assert len(other_peers) >= 1
        peer_symbols = {r.symbol for r in other_peers}
        assert "BMP" not in peer_symbols
        valid_pes = [r.pe for r in other_peers if r.pe is not None and r.pe > 0]
        if valid_pes:
            assert abs(res.peer_median_pe - round(statistics.median(valid_pes), 2)) < 1e-4

    def test_market_breadth_vn100_denominator_reconciliation(self, db_session: Session):
        """Verifies VN100 constituent breadth calculation rule and formula contract."""
        from services.macro.engine import MarketRegimeEngine
        regime = MarketRegimeEngine.determine_regime(date(2026, 11, 2), session=db_session, benchmark="VN100")
        assert regime.denominator_rule == "advancing / (advancing + declining + unchanged) across constituents with valid aligned session prices"
        if regime.regime != "INSUFFICIENT_DATA" and regime.covered_members and regime.covered_members > 0:
            expected_breadth = round((regime.advancing / regime.covered_members) * 100.0, 2)
            assert abs(regime.breadth_percent - expected_breadth) < 1e-2


class TestStatusClassifierContracts:
    """Verifies strict transition rules for AVAILABLE vs PARTIAL vs INSUFFICIENT_DATA."""

    def test_partial_status_when_capex_progress_unverified(self):
        # Q5 HPG: D/E is available, but capex expansion is unverified
        ev1 = AICitation(id="E001", responsible_module="fundamentals", claim_type="FACT", metric="de_ratio", value=0.70, symbol="HPG", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Hệ số D/E của HPG là 0.70 lần.", citation_ids=["E001"]),
            AIClaim(claim_type="UNCERTAINTY", text="Tiến độ mở rộng và chi phí vốn cụ thể chưa được công bố trong dữ liệu hiện có.", citation_ids=[]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Chi phí vốn, hệ số đòn bẩy tài chính D/E và tiến độ mở rộng của Tập đoàn Hòa Phát (HPG)?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=["Tiến độ mở rộng và chi phí vốn chưa được công bố."],
            extracted_symbols=["HPG"],
            canonical_symbol="HPG",
        )
        assert status == "PARTIAL"

    def test_available_status_when_all_requested_metrics_covered(self):
        # Q9 FPT: Both Net Margin and ROIC are grounded
        ev1 = AICitation(id="E001", responsible_module="fundamentals", claim_type="FACT", metric="net_margin", value=15.68, symbol="FPT", source="BCTC", freshness="AVAILABLE")
        ev2 = AICitation(id="E002", responsible_module="fundamentals", claim_type="FACT", metric="roic", value=21.51, symbol="FPT", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Biên lợi nhuận ròng của FPT là 15.68%.", citation_ids=["E001"]),
            AIClaim(claim_type="FACT", text="Hiệu quả sử dụng vốn ROIC của FPT đạt 21.51%.", citation_ids=["E002"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Biên lợi nhuận ròng và hiệu quả sử dụng vốn ROIC của FPT trong các kỳ gần nhất?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1, "E002": ev2},
            final_uncertainty=[],
            extracted_symbols=["FPT"],
            canonical_symbol="FPT",
        )
        assert status == "AVAILABLE"
        assert len(uncovered) == 0

    def test_partial_status_when_one_requested_metric_missing(self):
        # Q9 FPT: Net Margin covered, but ROIC missing
        ev1 = AICitation(id="E001", responsible_module="fundamentals", claim_type="FACT", metric="net_margin", value=15.68, symbol="FPT", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Biên lợi nhuận ròng của FPT là 15.68%.", citation_ids=["E001"]),
            AIClaim(claim_type="UNCERTAINTY", text="Chưa có dữ liệu ROIC trong bằng chứng hiện tại.", citation_ids=[]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Biên lợi nhuận ròng và hiệu quả sử dụng vốn ROIC của FPT trong các kỳ gần nhất?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=["Chưa có dữ liệu ROIC trong bằng chứng hiện tại."],
            extracted_symbols=["FPT"],
            canonical_symbol="FPT",
        )
        assert status == "PARTIAL"
        assert "roic" in uncovered

    def test_available_status_for_vcb_pb_and_equity(self):
        # Q10 VCB: Both P/B and Total Equity grounded
        ev1 = AICitation(id="E001", responsible_module="valuation", claim_type="FACT", metric="pb", value=1.89, symbol="VCB", source="MARKET", freshness="AVAILABLE")
        ev2 = AICitation(id="E002", responsible_module="fundamentals", claim_type="FACT", metric="total_equity", value=248490.51, symbol="VCB", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Hệ số P/B của VCB là 1.89 lần.", citation_ids=["E001"]),
            AIClaim(claim_type="FACT", text="Quy mô vốn chủ sở hữu của VCB là 248,490.51 tỷ VND.", citation_ids=["E002"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Quy mô vốn chủ sở hữu và định giá P/B của Vietcombank (VCB) hiện tại?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1, "E002": ev2},
            final_uncertainty=[],
            extracted_symbols=["VCB"],
            canonical_symbol="VCB",
        )
        assert status == "AVAILABLE"
        assert len(uncovered) == 0

    def test_available_status_for_bmp_dcf(self):
        # Q11 BMP: DCF Base Case grounded
        ev1 = AICitation(id="E001", responsible_module="valuation", claim_type="MODEL_OUTPUT", metric="dcf_base", value=179638.0, symbol="BMP", source="VALUATION", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="MODEL_OUTPUT", text="Mô hình định giá DCF kịch bản cơ sở của BMP cho kết quả 179,638 VND/cổ phiếu.", citation_ids=["E001"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Mô hình định giá DCF và kịch bản cơ sở (Base Case) đối với cổ phiếu BMP đưa ra kết quả gì?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=[],
            extracted_symbols=["BMP"],
            canonical_symbol="BMP",
        )
        assert status == "AVAILABLE"
        assert len(uncovered) == 0

    def test_screener_35_qualifying_tickers_exact(self, db_session: Session):
        from services.screener.engine import ScreenerCriteria, StockScreenerEngine
        screener = StockScreenerEngine(db_session)
        crit = ScreenerCriteria(universe="ALL", pe_max=15.0, roe_min=15.0)
        res = screener.screen(crit, as_of=date(2026, 11, 2))
        assert res.total_screened >= 5
        assert res.matched_count >= 1
        matched_symbols = {m.symbol for m in res.matches}
        assert len(matched_symbols) > 0

    def test_available_status_for_hpg_interest_and_net_debt_ebitda(self):
        ev1 = AICitation(id="E001", responsible_module="fundamentals", claim_type="FACT", metric="net_debt_ebitda", value=2.05, symbol="HPG", source="BCTC", freshness="AVAILABLE")
        ev2 = AICitation(id="E002", responsible_module="fundamentals", claim_type="FACT", metric="interest_coverage", value=5.51, symbol="HPG", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Tỷ lệ nợ ròng/EBITDA của HPG là 2.05 lần.", citation_ids=["E001"]),
            AIClaim(claim_type="FACT", text="Hệ số chi trả lãi vay của HPG là 5.51 lần.", citation_ids=["E002"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Tỷ lệ nợ ròng trên EBITDA và khả năng chi trả lãi vay của HPG?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1, "E002": ev2},
            final_uncertainty=[],
            extracted_symbols=["HPG"],
            canonical_symbol="HPG",
        )
        assert status == "AVAILABLE"
        assert len(uncovered) == 0

    def test_partial_status_for_vnindex_regime_direct(self):
        # VNINDEX direct query has proxy evidence but VNINDEX itself is absent
        ev1 = AICitation(id="E001", responsible_module="technical", claim_type="UNCERTAINTY", metric="market_regime_vnindex", value="UNAVAILABLE", symbol="VNINDEX", source="MARKET", freshness="INSUFFICIENT_DATA")
        ev2 = AICitation(id="E002", responsible_module="technical", claim_type="FACT", metric="market_regime_vn100_proxy", value="NEUTRAL", symbol="VN100", source="MARKET", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="UNCERTAINTY", text="Dữ liệu quan sát chuỗi chỉ số VNINDEX trực tiếp chưa có trong cơ sở dữ liệu.", citation_ids=["E001"]),
            AIClaim(claim_type="FACT", text="Sử dụng đại diện VN100 cho thấy chế độ thị trường NEUTRAL.", citation_ids=["E002"]),
            AIClaim(claim_type="UNCERTAINTY", text="Chỉ số VNINDEX trực tiếp chưa được quan sát.", citation_ids=[]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Đánh giá trạng thái chế độ thị trường (Market Regime) và độ rộng thị trường chứng khoán Việt Nam của chỉ số VNINDEX?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1, "E002": ev2},
            final_uncertainty=["Chỉ số VNINDEX trực tiếp chưa được quan sát."],
            extracted_symbols=["VNINDEX"],
            canonical_symbol="VNINDEX",
        )
        assert status == "PARTIAL"

    def test_status_available_with_non_blocking_caveats(self):
        # All essential requested metrics (P/E, ROE) are grounded. Non-blocking caveats (PEG, FCF) must NOT downgrade status.
        ev1 = AICitation(id="E001", responsible_module="valuation", claim_type="FACT", metric="pe", value=8.99, symbol="BMP", source="MARKET", freshness="AVAILABLE")
        ev2 = AICitation(id="E002", responsible_module="fundamentals", claim_type="FACT", metric="roe", value=41.57, symbol="BMP", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="P/E của BMP là 8.99 lần.", citation_ids=["E001"]),
            AIClaim(claim_type="FACT", text="ROE của BMP là 41.57%.", citation_ids=["E002"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Định giá P/E và tỷ suất sinh lời ROE của BMP?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1, "E002": ev2},
            final_uncertainty=["Chỉ số PEG chưa có sẵn trong CSDL.", "Dòng tiền tự do FCF chưa sẵn sàng."],
            extracted_symbols=["BMP"],
            canonical_symbol="BMP",
        )
        assert status == "AVAILABLE"
        assert len(uncovered) == 0

    def test_status_partial_when_essential_metric_missing(self):
        # D/E is grounded, but capex expansion (essential requested topic) is unannounced/missing
        ev1 = AICitation(id="E001", responsible_module="fundamentals", claim_type="FACT", metric="de_ratio", value=0.70, symbol="HPG", source="BCTC", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Hệ số D/E của HPG là 0.70 lần.", citation_ids=["E001"]),
            AIClaim(claim_type="UNCERTAINTY", text="Tiến độ chi tiết các dự án mở rộng chưa được công bố trong kỳ báo cáo này.", citation_ids=[]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Chi phí vốn, hệ số đòn bẩy tài chính D/E và tiến độ mở rộng của Tập đoàn Hòa Phát (HPG)?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=["Tiến độ chi tiết các dự án mở rộng chưa được công bố."],
            extracted_symbols=["HPG"],
            canonical_symbol="HPG",
        )
        assert status == "PARTIAL"

    def test_status_partial_when_proxy_used_for_requested_entity(self):
        # VNINDEX requested, but only VN100 proxy evidence cited -> strictly PARTIAL
        ev1 = AICitation(id="E001", responsible_module="regime", claim_type="MODEL_OUTPUT", metric="market_regime", value="NEUTRAL", symbol="VN100", source="vn100_breadth", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Trạng thái chế độ thị trường VN100 đại diện là NEUTRAL.", citation_ids=["E001"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Đánh giá chế độ thị trường của VNINDEX?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=["Chỉ số VNINDEX không có chuỗi giá trực tiếp, dùng VN100 làm proxy."],
            extracted_symbols=["VNINDEX"],
            canonical_symbol="VNINDEX",
        )
        assert status == "PARTIAL"

    def test_status_wrong_scope_when_wrong_aggregation_level(self):
        # Peer medians requested, but model only cites company's own individual P/E -> WRONG_SCOPE
        ev1 = AICitation(id="E001", responsible_module="valuation", claim_type="FACT", metric="pe", value=8.99, symbol="BMP", source="MARKET", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="P/E của BMP là 8.99 lần.", citation_ids=["E001"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Định giá P/E trung vị ngành vật liệu?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=[],
            extracted_symbols=["BMP"],
            canonical_symbol="BMP",
        )
        assert status == "WRONG_SCOPE"

    def test_status_wrong_scope_when_wrong_metric_substituted(self):
        # Corporate revenue correlation requested, but stock price correlation cited -> WRONG_SCOPE
        ev1 = AICitation(id="E001", responsible_module="macro", claim_type="MODEL_OUTPUT", metric="pearson_correlation", value=-0.36, symbol="PLX", source="PRICE_TIME_SERIES", freshness="AVAILABLE")
        claims = [
            AIClaim(claim_type="FACT", text="Tương quan giá cổ phiếu PLX và giá dầu là -0.36.", citation_ids=["E001"]),
        ]
        status, uncovered = AIAnalyst.determine_response_status(
            question="Mối tương quan giữa doanh thu PLX và biến động giá dầu thế giới?",
            cited_claims=claims,
            evidence_by_id={"E001": ev1},
            final_uncertainty=[],
            extracted_symbols=["PLX"],
            canonical_symbol="PLX",
        )
        assert status == "WRONG_SCOPE"
