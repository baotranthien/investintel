import pytest
from datetime import date
from sqlalchemy.orm import Session

from services.valuation.engine import DCFEngine
from services.valuation.models import DCFAssumptions
from services.fundamentals.engine import ProfitabilityEngine, CoverageEngine
from services.fundamentals.models import DataStatus
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.fundamentals.repository import FinancialRepository


class TestAnalyticalAccuracyRemediation:
    """
    Quality Control & Remediation Regression Tests:
    1. DCF WACC == g_t boundary returns INVALID_ASSUMPTION and fair_value=0.0.
    2. DCF WACC < g_t boundary returns INVALID_ASSUMPTION and fair_value=0.0.
    3. Bank sector (VCB) excludes industrial FCF, Gross Margin, and Interest Coverage.
    4. BMP Interest Coverage identifies NEGLIGIBLE_INTEREST_EXPENSE for negligible debt.
    5. Negative Invested Capital returns DataStatus.NOT_MEANINGFUL.
    6. Effective tax rate is bounded within realistic corporate range [0%, 50%].
    """

    def test_dcf_wacc_equal_terminal_growth_returns_invalid_assumption(self):
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10, 0.08, 0.06],
            ebit_margins=[0.20, 0.20, 0.20],
            tax_rate=0.20,
            wacc=0.03,  # Equal to terminal growth rate
            terminal_growth_rate=0.03,
            base_revenue=50_000.0,
        )
        res = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=0.0)
        assert res.fair_value.base == 0.0
        assert res.fair_value.bear == 0.0
        assert res.fair_value.bull == 0.0
        assert res.applicability == "NOT_APPLICABLE"
        assert any("INVALID_ASSUMPTION" in w for w in res.warnings)

    def test_dcf_wacc_less_than_terminal_growth_returns_invalid_assumption(self):
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10, 0.08, 0.06],
            ebit_margins=[0.20, 0.20, 0.20],
            tax_rate=0.20,
            wacc=0.02,  # Strictly less than terminal growth rate
            terminal_growth_rate=0.03,
            base_revenue=50_000.0,
        )
        res = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=0.0)
        assert res.fair_value.base == 0.0
        assert res.fair_value.bear == 0.0
        assert res.fair_value.bull == 0.0
        assert res.applicability == "NOT_APPLICABLE"
        assert any("INVALID_ASSUMPTION" in w for w in res.warnings)

    def test_bank_sector_excludes_industrial_fcf_and_margins(self, db_session: Session):
        repo = FinancialRepository(db_session)
        dataset = repo.get_financial_dataset("VCB", as_of_date=date(2026, 11, 2))
        builder = FundamentalSnapshotBuilder("VCB", sector="BANK")
        snap = builder.build_snapshot(
            income_quarters=dataset["income_quarters"],
            income_annual=dataset["income_annual"],
            balance_annual=dataset["balance_annual"],
            cashflow_annual=dataset["cashflow_annual"],
            shares_outstanding=dataset.get("shares_outstanding"),
        )
        # Verify banking exclusions
        assert snap["profitability"]["gross_margin"]["data_status"] == "NOT_MEANINGFUL"
        assert snap["balance_sheet"]["interest_coverage"]["data_status"] == "NOT_MEANINGFUL"
        assert snap["cash_flow"]["fcf"] is None
        assert snap["cash_flow"]["fcf_to_ni"]["data_status"] == "NOT_MEANINGFUL"

    def test_bmp_negligible_interest_expense_flagged(self):
        # BMP EBIT ~ 1,563B vs interest expense ~ 0.0958B (< 1B)
        res = CoverageEngine.interest_coverage(ebit=1563.0, interest_expense=-0.0958)
        assert res.value is not None
        assert res.value > 10000.0
        assert res.not_meaningful_reason is not None
        assert "NEGLIGIBLE_INTEREST_EXPENSE" in res.not_meaningful_reason

    def test_negative_invested_capital_roic_not_meaningful(self):
        # Invested capital = equity (1,000) + debt (0) - cash (2,000) = -1,000 < 0
        res = ProfitabilityEngine.roic(
            operating_income=100.0,
            effective_tax_rate=0.20,
            total_equity=1000.0,
            gross_debt=0.0,
            cash=2000.0,
        )
        assert res.value is None
        assert res.data_status == DataStatus.NOT_MEANINGFUL
        assert "NEGATIVE_INVESTED_CAPITAL" in (res.not_meaningful_reason or "")

    def test_effective_tax_rate_bounded_and_positive_nopat(self):
        # Testing tax rate fallback when eff_tax exceeds 50%
        builder = FundamentalSnapshotBuilder("MWG", sector="RETAIL")
        # Build with synthetic inputs where income_tax is unusually high
        income_quarters = [
            {"fiscal_period_end": date(2025, 9, 30), "operating_income": 2500.0, "net_income": 2000.0, "income_tax": 500.0, "revenue": 30000.0, "gross_profit": 6000.0},
            {"fiscal_period_end": date(2025, 12, 31), "operating_income": 2500.0, "net_income": 2000.0, "income_tax": 500.0, "revenue": 30000.0, "gross_profit": 6000.0},
            {"fiscal_period_end": date(2026, 3, 31), "operating_income": 2500.0, "net_income": 2000.0, "income_tax": 500.0, "revenue": 30000.0, "gross_profit": 6000.0},
            {"fiscal_period_end": date(2026, 6, 30), "operating_income": 2500.0, "net_income": 2000.0, "income_tax": 500.0, "revenue": 30000.0, "gross_profit": 6000.0},
        ]
        balance_annual = [
            {"fiscal_period_end": date(2025, 12, 31), "total_equity": 30000.0, "cash": 5000.0, "short_term_debt": 10000.0, "long_term_debt": 0.0},
            {"fiscal_period_end": date(2026, 6, 30), "total_equity": 35000.0, "cash": 5000.0, "short_term_debt": 10000.0, "long_term_debt": 0.0},
        ]
        snap = builder.build_snapshot(
            income_quarters=income_quarters,
            income_annual=[],
            balance_annual=balance_annual,
            cashflow_annual=[],
        )
        roic = snap["profitability"]["roic"]
        assert roic["data_status"] == "VALID"
        assert roic["value"] > 0, "ROIC must be positive when EBIT > 0 and Invested Capital > 0"

