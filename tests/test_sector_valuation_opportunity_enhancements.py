"""
Unit tests for Sector Standardization, Dynamic Valuation Assumptions,
and Sector-Aware Opportunity Intelligence Enhancements.
"""
from datetime import date
import pytest

from services.fundamentals.sector_models import (
    SECTOR_MODELS,
    UtilityModel,
    normalize_sector_name,
    COMPANY_SECTOR_MAP,
    get_sector_for_symbol,
    get_sector_model,
)
from services.valuation.models import DCFAssumptions
from services.valuation.engine import DCFEngine, ResidualIncomeEngine
from services.valuation.builder import ValuationSnapshotBuilder
from services.opportunity.engine import OpportunityEngine


class TestSectorStandardization:
    def test_utility_model_registered(self):
        assert "UTILITY" in SECTOR_MODELS
        assert SECTOR_MODELS["UTILITY"] == UtilityModel
        model = get_sector_model("POW")
        assert model.sector == "UTILITY"

    def test_normalize_sector_name(self):
        assert normalize_sector_name("banking") == "BANK"
        assert normalize_sector_name("BANKS") == "BANK"
        assert normalize_sector_name("Financial Services") == "SECURITIES"
        assert normalize_sector_name("Real Estate") == "REAL_ESTATE"
        assert normalize_sector_name("Consumer Goods") == "CONSUMER"
        assert normalize_sector_name("Basic Materials") == "MATERIALS"
        assert normalize_sector_name("Oil & Gas") == "OIL_GAS"
        assert normalize_sector_name("Utilities") == "UTILITY"
        assert normalize_sector_name("Manufacturing") == "INDUSTRIAL"
        assert normalize_sector_name("Logistics") == "TRANSPORTATION"
        assert normalize_sector_name(None) is None

    def test_company_sector_map_100_hose_coverage(self):
        key_stocks = {
            "ACB": "BANK", "VCB": "BANK", "MBB": "BANK", "TCB": "BANK",
            "SSI": "SECURITIES", "VCI": "SECURITIES", "VIX": "SECURITIES",
            "VHM": "REAL_ESTATE", "VIC": "REAL_ESTATE", "NVL": "REAL_ESTATE",
            "MWG": "RETAIL", "FRT": "RETAIL", "PNJ": "RETAIL",
            "FPT": "TECHNOLOGY", "CMG": "TECHNOLOGY",
            "HPG": "MATERIALS", "HSG": "MATERIALS", "BMP": "MATERIALS",
            "VNM": "CONSUMER", "MSN": "CONSUMER", "SAB": "CONSUMER",
            "GAS": "OIL_GAS", "PLX": "OIL_GAS", "PVD": "OIL_GAS",
            "REE": "UTILITY", "POW": "UTILITY",
            "GEX": "INDUSTRIAL", "VCG": "INDUSTRIAL",
            "HVN": "TRANSPORTATION", "VJC": "TRANSPORTATION", "GMD": "TRANSPORTATION",
        }
        for sym, expected_sector in key_stocks.items():
            assert get_sector_for_symbol(sym) == expected_sector


class TestDynamicValuationAssumptions:
    def test_dcf_reinvestment_rate(self):
        assump_base = DCFAssumptions(
            revenue_growth_rates=[0.10]*5,
            ebit_margins=[0.20]*5,
            tax_rate=0.20,
            wacc=0.12,
            terminal_growth_rate=0.03,
            base_revenue=10000.0,
        )
        out_base = DCFEngine.calculate(assump_base, shares_outstanding=1_000_000_000, net_debt=0)

        assump_reinvest = DCFAssumptions(
            revenue_growth_rates=[0.10]*5,
            ebit_margins=[0.20]*5,
            tax_rate=0.20,
            wacc=0.12,
            terminal_growth_rate=0.03,
            base_revenue=10000.0,
            capex_percent_rev=0.05,
            wc_percent_rev=0.02,
        )
        out_reinvest = DCFEngine.calculate(assump_reinvest, shares_outstanding=1_000_000_000, net_debt=0)

        assert out_base.fair_value.base > out_reinvest.fair_value.base > 0

    def test_valuation_snapshot_builder_dynamic_assumptions(self):
        builder = ValuationSnapshotBuilder("FPT", "TECHNOLOGY")
        dyn_fund = {
            "symbol": "FPT",
            "sector": "TECHNOLOGY",
            "eps_ttm": 5000.0,
            "bvps": 25000.0,
            "shares_outstanding": 1_000_000_000,
            "revenue_ttm": 50000.0,
            "revenue_yoy": 0.20,
            "revenue_cagr_3y": 0.18,
            "operating_margin": 0.22,
            "wacc": 0.115,
            "cost_of_equity": 0.125,
            "roe": 25.0,
            "peer_pe": 18.0,
            "peer_pb": 3.0,
            "use_dynamic_assumptions": True,
        }
        snap = builder.build(dyn_fund, current_price=90000.0, as_of=date.today())
        assert snap.composite_fair_value.range.base > 0
        assert snap.margin_of_safety is not None

    def test_valuation_snapshot_builder_backward_compatibility(self):
        builder = ValuationSnapshotBuilder("TEST", "GENERAL")
        static_fund = {
            "symbol": "TEST",
            "eps_ttm": 4000.0,
            "bvps": 20000.0,
            "shares_outstanding": 1_000_000_000,
            "revenue_ttm": 20000.0,
            "roe": 15.0,
            "peer_pe": 12.0,
            "peer_pb": 1.5,
        }
        snap = builder.build(static_fund, current_price=40000.0, as_of=date.today())
        assert snap.composite_fair_value.range.base > 0


class TestOpportunityEngineEnhancements:
    def test_bank_specific_scoring(self):
        bank_healthy = {
            "sector": "BANK",
            "roe": 0.22,
            "profit_growth_yoy": 0.18,
            "de_ratio": 9.5,  # high leverage natural for banks, must NOT be penalized
            "nim": 4.1,
            "npl_ratio": 1.2,
            "llr_coverage": 140.0,
        }
        bank_weak = {
            "sector": "BANK",
            "roe": 0.08,
            "profit_growth_yoy": -0.15,
            "de_ratio": 12.0,
            "nim": 2.2,
            "npl_ratio": 2.8,
            "llr_coverage": 50.0,
        }
        score_healthy = OpportunityEngine._score_fundamental(bank_healthy)
        score_weak = OpportunityEngine._score_fundamental(bank_weak)
        assert score_healthy > 75
        assert score_weak < 40

    def test_advanced_signals_scoring(self):
        fund_with_signals = {
            "sector": "TECHNOLOGY",
            "roe": 0.25,
            "profit_growth_yoy": 0.22,
            "de_ratio": 0.4,
            "earnings_acceleration": True,
            "cfo_positive": True,
            "price_momentum_score": 6.5,
        }
        fund_base = {
            "sector": "TECHNOLOGY",
            "roe": 0.25,
            "profit_growth_yoy": 0.22,
            "de_ratio": 0.4,
        }
        score_signals = OpportunityEngine._score_fundamental(fund_with_signals)
        score_base = OpportunityEngine._score_fundamental(fund_base)
        assert score_signals > score_base
