"""
SYSTEM AUDIT - Automated Test Suite
Tests Phase 2-5 logic correctness, data integrity, and guard rails.
Run from repository root: pytest tests/api/ -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from datetime import date


# =========================================================================
# Phase 3: Valuation Engine Tests
# =========================================================================

class TestDCFEngine:
    def test_dcf_returns_range_with_bear_lt_base_lt_bull(self):
        from services.valuation.engine import DCFEngine
        from services.valuation.models import DCFAssumptions
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10, 0.09, 0.08, 0.07, 0.06],
            ebit_margins=[0.20, 0.20, 0.20, 0.20, 0.20],
            tax_rate=0.20,
            wacc=0.12,
            terminal_growth_rate=0.03,
            base_revenue=50_000.0
        )
        result = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=5_000)
        fv = result.fair_value
        assert fv.bear <= fv.base <= fv.bull, "Bear must be <= Base <= Bull"

    def test_dcf_missing_revenue_returns_insufficient_data(self):
        from services.valuation.engine import DCFEngine
        from services.valuation.models import DCFAssumptions
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10],
            ebit_margins=[0.20],
            tax_rate=0.20,
            wacc=0.12,
            terminal_growth_rate=0.03,
            base_revenue=None # Missing revenue
        )
        result = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=0)
        assert result.applicability == "NOT_APPLICABLE"
        assert any("INSUFFICIENT_DATA" in w for w in result.warnings)

    def test_dcf_raises_on_wacc_equals_terminal_growth(self):
        """WACC <= terminal_growth must be handled gracefully (not crash)."""
        from services.valuation.engine import DCFEngine
        from services.valuation.models import DCFAssumptions
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10],
            ebit_margins=[0.20],
            tax_rate=0.20,
            wacc=0.03,  # Same as terminal growth
            terminal_growth_rate=0.03,
            base_revenue=50_000.0
        )
        # Should NOT raise — must handle edge case
        result = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=0)
        assert result.fair_value.base >= 0

    def test_relative_valuation_negative_eps_returns_not_applicable(self):
        """Negative EPS must make P/E N/A."""
        from services.valuation.engine import RelativeValuationEngine
        result = RelativeValuationEngine.calculate(
            metric_name="P/E",
            company_metric_value=0,
            peer_median=15.0,
            historical_median=14.0,
            company_fundamental_driver=-100.0  # NEGATIVE EPS
        )
        assert result.applicability == "NOT_APPLICABLE"

    def test_residual_income_bear_lt_base_lt_bull(self):
        from services.valuation.engine import ResidualIncomeEngine
        result = ResidualIncomeEngine.calculate(bvps=20_000, roe=0.18, cost_of_equity=0.12, growth=0.05)
        fv = result.fair_value
        assert fv.bear <= fv.base <= fv.bull

    def test_residual_income_ke_gt_g_sanity(self):
        """If cost_of_equity <= growth, TV can be 0 but should not crash."""
        from services.valuation.engine import ResidualIncomeEngine
        result = ResidualIncomeEngine.calculate(bvps=20_000, roe=0.18, cost_of_equity=0.04, growth=0.05)
        assert result.fair_value.base >= 0


# =========================================================================
# Phase 4: Risk Engine Tests
# =========================================================================

class TestRiskEngine:
    def test_high_de_ratio_increases_financial_risk(self):
        from services.risk.engine import RiskEngine
        high_debt = RiskEngine.calculate_profile("TST", {"de_ratio": 4.0}, {}, date.today())
        low_debt = RiskEngine.calculate_profile("TST", {"de_ratio": 0.2}, {}, date.today())
        assert high_debt.financial_risk.score > low_debt.financial_risk.score

    def test_empty_fundamentals_returns_stub_label(self):
        from services.risk.engine import RiskEngine
        result = RiskEngine.calculate_profile("TST", {}, {}, date.today())
        # All STUB_DATA labels should be present
        assert "STUB_DATA" in result.data_risk.drivers[0]

    def test_total_risk_is_average_of_categories(self):
        from services.risk.engine import RiskEngine
        result = RiskEngine.calculate_profile("TST", {}, {}, date.today())
        cats = [result.market_risk, result.business_risk, result.financial_risk,
                result.valuation_risk, result.liquidity_risk, result.macro_risk,
                result.geopolitical_risk, result.event_risk, result.data_risk, result.model_risk]
        expected_avg = sum(c.score for c in cats) / len(cats)
        assert abs(result.total_risk_score - expected_avg) < 0.1

    def test_top_contributors_sorted_correctly(self):
        from services.risk.engine import RiskEngine
        result = RiskEngine.calculate_profile("TST", {"de_ratio": 4.0}, {}, date.today())
        assert "Financial Risk" in result.top_contributors  # High de_ratio => financial risk highest


# =========================================================================
# Phase 4: Opportunity Engine Tests
# =========================================================================

class TestOpportunityEngine:
    def test_empty_inputs_returns_insufficient_confidence(self):
        from services.opportunity.engine import OpportunityEngine
        result = OpportunityEngine.calculate_medium_term(
            "TST", {}, {}, None, None, [], date.today()
        )
        assert result.confidence == "INSUFFICIENT"

    def test_score_is_deterministic(self):
        """Same inputs must produce same score (no randomness)."""
        from services.opportunity.engine import OpportunityEngine
        r1 = OpportunityEngine.calculate_medium_term("TST", {}, {}, None, None, [], date.today())
        r2 = OpportunityEngine.calculate_medium_term("TST", {}, {}, None, None, [], date.today())
        assert r1.opportunity_score == r2.opportunity_score

    def test_good_fundamentals_increase_score(self):
        from services.opportunity.engine import OpportunityEngine
        good_fund = {"roe": 0.25, "profit_growth_yoy": 0.25, "de_ratio": 0.3}
        bad_fund = {"roe": -0.05, "profit_growth_yoy": -0.20, "de_ratio": 4.0}
        r_good = OpportunityEngine.calculate_medium_term("TST", good_fund, {}, None, None, [], date.today())
        r_bad = OpportunityEngine.calculate_medium_term("TST", bad_fund, {}, None, None, [], date.today())
        assert r_good.opportunity_score > r_bad.opportunity_score

    def test_score_bounded_0_100(self):
        from services.opportunity.engine import OpportunityEngine
        result = OpportunityEngine.calculate_medium_term("TST", {}, {}, None, None, [], date.today())
        assert 0 <= result.opportunity_score <= 100

    def test_signal_conflict_detected(self):
        """High valuation attractiveness + poor fundamentals => conflict."""
        from services.opportunity.engine import OpportunityEngine
        good_val = {"margin_of_safety": 0.40, "pe_percentile": 10}  # Cheap
        bad_fund = {"roe": -0.10, "profit_growth_yoy": -0.30}  # Poor fundamentals
        result = OpportunityEngine.calculate_medium_term("TST", bad_fund, good_val, None, None, [], date.today())
        assert result.signal_conflict is True

    def test_model_version_present(self):
        from services.opportunity.engine import OpportunityEngine
        result = OpportunityEngine.calculate_medium_term("TST", {}, {}, None, None, [], date.today())
        assert result.model_version == "opportunity_medium_v1"

    def test_no_hardcoded_symbol_behavior(self):
        """Any symbol must produce same logic path when inputs are identical."""
        from services.opportunity.engine import OpportunityEngine
        inputs = ({"roe": 0.15}, {}, None, None, [], date.today())
        r_fpt = OpportunityEngine.calculate_medium_term("FPT", *inputs)
        r_vcb = OpportunityEngine.calculate_medium_term("VCB", *inputs)
        r_xyz = OpportunityEngine.calculate_medium_term("UNKNOWN", *inputs)
        # All should produce the same score because inputs are identical
        assert r_fpt.opportunity_score == r_vcb.opportunity_score == r_xyz.opportunity_score


# =========================================================================
# Phase 4: Macro Model Tests
# =========================================================================

class TestMacroModels:
    def test_macro_regime_state_valid_states(self):
        from services.macro.models import MacroRegimeState
        # Should not raise
        s = MacroRegimeState(state="RECOVERY", direction="UP", strength=75.0, confidence=0.8, drivers=["test"])
        assert s.state == "RECOVERY"

    def test_macro_regime_state_invalid_state_raises(self):
        from pydantic import ValidationError
        from services.macro.models import MacroRegimeState
        with pytest.raises(ValidationError):
            MacroRegimeState(state="NONSENSE", direction="UP", strength=75.0, confidence=0.8, drivers=[])


# =========================================================================
# Phase 5: AI Guardrail Tests
# =========================================================================

class TestAIGuardrails:
    def test_ai_router_routes_news_to_fast_model(self):
        from services.ai.router import AIRouter
        router = AIRouter()
        model = router.route_task("NEWS_CLASSIFICATION", "LOW")
        assert model == router.fast_model

    def test_ai_router_routes_deep_research_to_reasoning_model(self):
        from services.ai.router import AIRouter
        router = AIRouter()
        model = router.route_task("DEEP_RESEARCH", "HIGH")
        assert model == router.reasoning_model

    def test_ai_tools_get_stock_snapshot_returns_dict(self):
        """Tools must return structured data, not fail."""
        from services.ai.tools import AITools
        result = AITools.get_stock_snapshot("FPT")
        assert isinstance(result, dict)
        assert "symbol" in result
        assert "opportunity_score" in result
        assert "confidence" in result
        # Must not be hardcoded FPT-specific score
        assert result["confidence"] == "INSUFFICIENT"  # Because fundamentals are empty

    def test_ai_tools_do_not_emit_scores_for_unregistered_asset(self):
        from services.ai.tools import AITools
        result = AITools.get_stock_snapshot("UNREGISTERED_AI_FIXTURE")
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["opportunity_score"] is None
        assert result["risk_score"] is None

    def test_ai_tools_market_context_has_required_keys(self):
        from services.ai.tools import AITools
        result = AITools.get_market_context()
        assert "market_regime" in result
        assert "macro_growth" in result

    def test_ai_opportunity_does_not_hardcode_symbols(self):
        """Any symbol should produce equal base score with no fundamentals."""
        from services.ai.tools import AITools
        fpt = AITools.get_stock_snapshot("FPT")
        vcb = AITools.get_stock_snapshot("VCB")
        # Same base score expected when inputs are structurally identical (empty fundamentals)
        assert fpt["opportunity_score"] == vcb["opportunity_score"]
