# -*- coding: utf-8 -*-
"""
Historical Financial Analysis Engine — Phase 4B.
Provides multi-period longitudinal financial time-series:
- 5 Annual fiscal periods
- 12 Quarterly fiscal periods
- Key line items across Income Statement, Balance Sheet, and Cash Flows
- Margins and capital structure metrics across all periods
- Corporate actions timeline (splits, stock dividends, cash dividends)
- Accounting presentation consistency & shares tracking
"""
from datetime import date
from typing import Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, CorporateAction
from services.fundamentals.repository import FinancialRepository


class PeriodFinancialRecord(BaseModel):
    period_type: str  # ANNUAL or QUARTERLY
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    fiscal_period_start: Optional[date] = None
    fiscal_period_end: Optional[date] = None
    publication_date: Optional[date] = None
    # Income
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    net_income: Optional[float] = None
    net_income_parent: Optional[float] = None
    eps_basic: Optional[float] = None
    # Balance Sheet
    cash: Optional[float] = None
    short_term_investments: Optional[float] = None
    total_current_assets: Optional[float] = None
    total_assets: Optional[float] = None
    short_term_debt: Optional[float] = None
    long_term_debt: Optional[float] = None
    gross_debt: Optional[float] = None
    total_current_liabilities: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    equity_parent: Optional[float] = None
    # Cash Flow
    cfo: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None
    # Ratios
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    de_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_assets: Optional[float] = None
    shares_basic: Optional[int] = None


class CorporateActionRecord(BaseModel):
    action_date: date
    action_type: str
    ratio: Optional[float] = None
    value: Optional[float] = None
    notes: Optional[str] = None


class HistoricalFinancialDataset(BaseModel):
    symbol: str
    name: str
    as_of_date: date
    annual_periods: List[PeriodFinancialRecord]
    quarterly_periods: List[PeriodFinancialRecord]
    corporate_actions: List[CorporateActionRecord]
    provenance: dict[str, Any]


class HistoricalFinancialEngine:
    """Extracts, merges, and presents multi-year historical time-series."""

    def __init__(self, session: Session):
        self.session = session

    def get_historical_dataset(self, symbol: str, as_of: Optional[date] = None) -> HistoricalFinancialDataset:
        as_of = as_of or date.today()
        sym = symbol.upper()

        asset = self.session.query(Asset).filter(Asset.symbol == sym).first()
        asset_name = asset.name if asset else f"{sym} Corporation"

        repo = FinancialRepository(self.session)
        dataset = repo.get_financial_dataset(sym, as_of_date=as_of) or {}

        inc_annual = dataset.get("income_annual", [])
        inc_quarters = dataset.get("income_quarters", [])
        bal_annual = dataset.get("balance_annual", [])
        cf_annual = dataset.get("cashflow_annual", [])

        # Map balances and cash flows by period_end & period_type
        bal_map = {(str(b.get("fiscal_period_end")), b.get("period_type")): b for b in bal_annual}
        cf_map = {(str(c.get("fiscal_period_end")), c.get("period_type")): c for c in cf_annual}

        def _build_record(inc_row: dict) -> PeriodFinancialRecord:
            p_end = str(inc_row.get("fiscal_period_end"))
            p_type = inc_row.get("period_type")
            bs_row = bal_map.get((p_end, p_type)) or bal_map.get((p_end, "ANNUAL")) or bal_map.get((p_end, "QUARTERLY")) or {}
            cf_row = cf_map.get((p_end, p_type)) or cf_map.get((p_end, "ANNUAL")) or cf_map.get((p_end, "QUARTERLY")) or {}

            rev = inc_row.get("revenue")
            gp = inc_row.get("gross_profit")
            ni = inc_row.get("net_income_parent") if inc_row.get("net_income_parent") is not None else inc_row.get("net_income")
            st_debt = bs_row.get("short_term_debt")
            lt_debt = bs_row.get("long_term_debt")
            gross_debt = (st_debt or 0.0) + (lt_debt or 0.0) if (st_debt is not None or lt_debt is not None) else None
            tot_assets = bs_row.get("total_assets")
            tot_liab = bs_row.get("total_liabilities")
            tot_eq = bs_row.get("equity_parent") or bs_row.get("total_equity")
            cur_assets = bs_row.get("total_current_assets")
            cur_liab = bs_row.get("total_current_liabilities")

            gm = round(gp / rev * 100, 2) if (gp is not None and rev and rev > 0) else None
            nm = round(ni / rev * 100, 2) if (ni is not None and rev and rev > 0) else None
            de = round(gross_debt / tot_eq, 4) if (gross_debt is not None and tot_eq and tot_eq > 0) else None
            cr = round(cur_assets / cur_liab, 2) if (cur_assets is not None and cur_liab and cur_liab > 0) else None
            d_assets = round(tot_liab / tot_assets * 100, 2) if (tot_liab is not None and tot_assets and tot_assets > 0) else None

            cfo_val = cf_row.get("cash_from_operations")
            capex_val = cf_row.get("capex")
            fcf_val = cf_row.get("free_cash_flow")
            if fcf_val is None and cfo_val is not None and capex_val is not None:
                fcf_val = cfo_val + capex_val  # capex is negative

            return PeriodFinancialRecord(
                period_type=p_type,
                fiscal_year=inc_row.get("fiscal_year"),
                fiscal_quarter=inc_row.get("fiscal_quarter"),
                fiscal_period_start=inc_row.get("fiscal_period_start"),
                fiscal_period_end=inc_row.get("fiscal_period_end"),
                publication_date=inc_row.get("publication_date"),
                revenue=rev,
                gross_profit=gp,
                operating_income=inc_row.get("operating_income"),
                ebit=inc_row.get("ebit"),
                ebitda=inc_row.get("ebitda"),
                net_income=inc_row.get("net_income"),
                net_income_parent=inc_row.get("net_income_parent"),
                eps_basic=inc_row.get("eps_basic"),
                cash=bs_row.get("cash"),
                short_term_investments=bs_row.get("short_term_investments"),
                total_current_assets=cur_assets,
                total_assets=tot_assets,
                short_term_debt=st_debt,
                long_term_debt=lt_debt,
                gross_debt=gross_debt,
                total_current_liabilities=cur_liab,
                total_liabilities=tot_liab,
                total_equity=tot_eq,
                equity_parent=bs_row.get("equity_parent"),
                cfo=cfo_val,
                capex=capex_val,
                fcf=fcf_val,
                gross_margin=gm,
                net_margin=nm,
                de_ratio=de,
                current_ratio=cr,
                debt_to_assets=d_assets,
                shares_basic=inc_row.get("shares_basic"),
            )

        # Build annual periods (last 5 years)
        annual_records = [_build_record(r) for r in inc_annual[-5:]]

        # Build quarterly periods (last 12 quarters)
        quarterly_records = [_build_record(r) for r in inc_quarters[-12:]]

        # Fetch Corporate Actions
        actions = (
            self.session.query(CorporateAction)
            .filter(CorporateAction.symbol == sym, CorporateAction.action_date <= as_of)
            .order_by(CorporateAction.action_date.desc())
            .all()
        )
        ca_records = [
            CorporateActionRecord(
                action_date=ca.action_date,
                action_type=ca.action_type,
                ratio=ca.ratio,
                value=float(ca.value) if ca.value is not None else None,
                notes=ca.notes,
            )
            for ca in actions
        ]

        return HistoricalFinancialDataset(
            symbol=sym,
            name=asset_name,
            as_of_date=as_of,
            annual_periods=annual_records,
            quarterly_periods=quarterly_records,
            corporate_actions=ca_records,
            provenance={
                "source": "CANONICAL_FINANCIAL_STATEMENTS",
                "annual_count": len(annual_records),
                "quarterly_count": len(quarterly_records),
                "corporate_actions_count": len(ca_records),
                "as_of_date": as_of.isoformat(),
            }
        )
