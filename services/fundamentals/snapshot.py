"""
Fundamental Snapshot Builder.

Orchestrates:
  1. Load normalized financials for a company
  2. Compute TTM
  3. Compute all derived metrics (margins, profitability, cash flow, etc.)
  4. Run sector model for sector-specific metrics
  5. Compute trend for key metrics
  6. Detect quality flags
  7. Compute financial health score
  8. Assemble AI-ready snapshot JSON

Output schema matches /api/v1/fundamentals/{symbol}/snapshot.

Historical reconstruction:
  - as_of_date parameter: only uses statements with publication_date <= as_of_date
  - This enables point-in-time backtest without look-ahead bias
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Any

from .engine import (
    TTMEngine, GrowthEngine, MarginEngine, ProfitabilityEngine,
    DebtEngine, LiquidityEngine, CoverageEngine, CashFlowQualityEngine,
    WorkingCapitalEngine, TrendEngine, QualityFlagEngine, FinancialHealthScorer,
    _average,
)
from .models import (
    MetricResult, DataStatus, TrendLabel, QualityFlagResult, FlagType,
)
from .sector_models import get_sector_model, get_sector_for_symbol


class FundamentalSnapshotBuilder:
    """
    Builds a full fundamental snapshot for a company.
    All inputs are dicts (from DB or fixture).
    No ORM dependencies — decoupled from persistence layer.
    """

    CALCULATION_VERSION = "v1"

    def __init__(self, symbol: str, sector: Optional[str] = None):
        self.symbol = symbol.upper()
        self.sector = sector or get_sector_for_symbol(self.symbol)
        self._sector_model = get_sector_model(self.symbol, sector)

    def build_snapshot(
        self,
        income_quarters: list[dict],      # sorted asc by fiscal_period_end
        income_annual: list[dict],        # sorted asc
        balance_annual: list[dict],       # sorted asc
        cashflow_annual: list[dict],      # sorted asc
        as_of_date: Optional[date] = None,
        shares_outstanding: Optional[float] = None,
        publication_dates: Optional[dict] = None,  # {fiscal_period_end: pub_date}
        sources: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Main entry point. Returns full snapshot dict.

        as_of_date: if provided, filters out data with publication_date > as_of_date
                    (prevents look-ahead bias).
        """
        # Filter by publication date if provided (historical reconstruction)
        if as_of_date and publication_dates:
            income_quarters = [
                q for q in income_quarters
                if publication_dates.get(str(q.get("fiscal_period_end")), date.max) <= as_of_date
            ]
            income_annual = [
                a for a in income_annual
                if publication_dates.get(str(a.get("fiscal_period_end")), date.max) <= as_of_date
            ]
            balance_annual = [
                b for b in balance_annual
                if publication_dates.get(str(b.get("fiscal_period_end")), date.max) <= as_of_date
            ]
            cashflow_annual = [
                c for c in cashflow_annual
                if publication_dates.get(str(c.get("fiscal_period_end")), date.max) <= as_of_date
            ]

        latest_income_q = income_quarters[-1] if income_quarters else {}
        latest_income_a = income_annual[-1] if income_annual else {}
        latest_bs = balance_annual[-1] if balance_annual else {}
        prev_bs = balance_annual[-2] if len(balance_annual) >= 2 else {}
        latest_cf = cashflow_annual[-1] if cashflow_annual else {}
        prior_cf = cashflow_annual[-2] if len(cashflow_annual) >= 2 else {}

        # Determine latest reporting period
        latest_period_end = latest_bs.get("fiscal_period_end") or latest_income_a.get("fiscal_period_end")
        latest_year = latest_income_a.get("fiscal_year") if income_annual else None
        prior_year_income = income_annual[-2] if len(income_annual) >= 2 else {}

        # ─── TTM ─────────────────────────────────────────────
        ttm_ok, ttm_reason = TTMEngine.validate_quarter_coverage(income_quarters)
        if ttm_ok:
            ttm = TTMEngine.compute_ttm_income(income_quarters)
        else:
            ttm = {}

        # ─── Primary income source: TTM > Annual ─────────────
        def get_income(field: str) -> Optional[float]:
            val = ttm.get(field) if ttm else None
            return val if val is not None else latest_income_a.get(field)

        revenue = get_income("revenue")
        gross_profit = get_income("gross_profit")
        cogs = get_income("cost_of_goods_sold")
        operating_income = get_income("operating_income")
        ebit = operating_income  # using operating income as EBIT proxy
        ebitda_val = None
        if ebit is not None and latest_cf.get("depreciation_amortization"):
            ebitda_val = ebit + latest_cf["depreciation_amortization"]
        net_income = get_income("net_income")
        net_income_parent = get_income("net_income_parent") or net_income
        interest_income = get_income("interest_income")
        interest_expense = get_income("interest_expense")
        income_tax = get_income("income_tax")
        eps_basic = get_income("eps_basic")

        # ─── Balance sheet ─────────────────────────────────────
        cash = latest_bs.get("cash")
        sti = latest_bs.get("short_term_investments")
        accounts_receivable = latest_bs.get("accounts_receivable")
        inventory = latest_bs.get("inventory")
        total_current_assets = latest_bs.get("total_current_assets")
        total_assets = latest_bs.get("total_assets")
        accounts_payable = latest_bs.get("accounts_payable")
        short_term_debt = latest_bs.get("short_term_debt")
        total_current_liabilities = latest_bs.get("total_current_liabilities")
        long_term_debt = latest_bs.get("long_term_debt")
        total_liabilities = latest_bs.get("total_liabilities")
        total_equity = latest_bs.get("total_equity")
        equity_parent = latest_bs.get("equity_parent") or total_equity
        equity_parent_prior = prev_bs.get("equity_parent")
        total_assets_prior = prev_bs.get("total_assets")

        # Prior year income
        revenue_prior = prior_year_income.get("revenue")
        net_income_prior = prior_year_income.get("net_income_parent") or prior_year_income.get("net_income")
        eps_prior = prior_year_income.get("eps_basic")

        # ─── Cash flow ─────────────────────────────────────────
        cfo = latest_cf.get("cash_from_operations")
        capex_val = latest_cf.get("capex")
        fcf_val = CashFlowQualityEngine.fcf(cfo, capex_val) if cfo is not None else latest_cf.get("free_cash_flow")

        # ─── DERIVED: Debt ─────────────────────────────────────
        gross_debt_val = DebtEngine.gross_debt(short_term_debt, long_term_debt)
        net_debt_val = DebtEngine.net_debt(gross_debt_val, cash, sti)

        # ─── MARGINS ───────────────────────────────────────────
        period = "TTM" if ttm_ok else "ANNUAL"
        gross_margin_r = MarginEngine.gross_margin(gross_profit, revenue, period)
        ebit_margin_r = MarginEngine.ebit_margin(ebit, revenue, period)
        ebitda_margin_r = MarginEngine.ebitda_margin(ebitda_val, revenue, period)
        net_margin_r = MarginEngine.net_margin(net_income_parent, revenue, period)
        cfo_margin_r = MarginEngine.cfo_margin(cfo, revenue, period)

        # ─── PROFITABILITY ─────────────────────────────────────
        roe_r = ProfitabilityEngine.roe(net_income_parent, equity_parent_prior, equity_parent, period)
        roa_r = ProfitabilityEngine.roa(net_income, total_assets_prior, total_assets, period)
        # Effective tax rate
        eff_tax = None
        if income_tax is not None and net_income is not None and net_income != 0:
            pre_tax = (latest_income_a.get("pre_tax_income") or
                       (net_income - income_tax if income_tax else None))
            if pre_tax and abs(pre_tax) > 0:
                eff_tax = abs(income_tax) / abs(pre_tax)
        roic_r = ProfitabilityEngine.roic(
            ebit, eff_tax, total_equity, gross_debt_val, cash,
            period, self.sector
        )

        # ─── CAPITAL STRUCTURE ─────────────────────────────────
        de_ratio_r = DebtEngine.de_ratio(gross_debt_val, equity_parent, period)
        net_debt_ebitda_r = DebtEngine.net_debt_ebitda(net_debt_val, ebitda_val, period, self.sector)
        debt_assets_r = DebtEngine.debt_to_assets(total_liabilities, total_assets, period)

        # ─── LIQUIDITY ─────────────────────────────────────────
        current_ratio_r = LiquidityEngine.current_ratio(
            total_current_assets, total_current_liabilities, period, self.sector)
        quick_ratio_r = LiquidityEngine.quick_ratio(
            total_current_assets, inventory, total_current_liabilities, period, self.sector)

        # ─── COVERAGE ──────────────────────────────────────────
        interest_cov_r = CoverageEngine.interest_coverage(ebit, interest_expense, period)

        # ─── CASH FLOW QUALITY ─────────────────────────────────
        cfo_ni_r = CashFlowQualityEngine.cfo_to_ni(cfo, net_income_parent, period)
        fcf_ni_r = CashFlowQualityEngine.fcf_to_ni(fcf_val, net_income_parent, period)
        capex_rev_r = MarginEngine.cfo_margin(abs(capex_val) if capex_val else None, revenue, period)

        # ─── GROWTH ────────────────────────────────────────────
        revenue_yoy_r = GrowthEngine.yoy(revenue, revenue_prior, "revenue_yoy", "revenue_yoy_v1")
        ni_yoy_r = GrowthEngine.yoy(net_income_parent, net_income_prior, "net_income_yoy", "net_income_yoy_v1")
        eps_yoy_r = GrowthEngine.yoy(eps_basic, eps_prior, "eps_yoy", "eps_yoy_v1")

        # CAGR (3Y, 5Y)
        income_5y_ago = income_annual[0] if len(income_annual) >= 5 else None
        income_3y_ago = income_annual[-4] if len(income_annual) >= 4 else None

        rev_cagr_3y_r = GrowthEngine.cagr(
            income_3y_ago.get("revenue") if income_3y_ago else None,
            revenue, 3, "revenue_cagr_3y", "revenue_cagr_3y_v1", "3Y"
        ) if income_3y_ago else MetricResult.insufficient_history("revenue_cagr_3y", "revenue_cagr_3y_v1", 3, "%", "3Y")

        rev_cagr_5y_r = GrowthEngine.cagr(
            income_5y_ago.get("revenue") if income_5y_ago else None,
            revenue, 5, "revenue_cagr_5y", "revenue_cagr_5y_v1", "5Y"
        ) if income_5y_ago else MetricResult.insufficient_history("revenue_cagr_5y", "revenue_cagr_5y_v1", 5, "%", "5Y")

        eps_3y_ago = income_3y_ago.get("eps_basic") if income_3y_ago else None
        eps_cagr_3y_r = GrowthEngine.cagr(
            eps_3y_ago, eps_basic, 3, "eps_cagr_3y", "eps_cagr_3y_v1", "3Y"
        ) if eps_3y_ago else MetricResult.insufficient_history("eps_cagr_3y", "eps_cagr_3y_v1", 3, "%", "3Y")

        # ─── WORKING CAPITAL ───────────────────────────────────
        prev_ar = prev_bs.get("accounts_receivable")
        prev_inv = prev_bs.get("inventory")
        prev_ap = prev_bs.get("accounts_payable")
        avg_ar = _average(accounts_receivable, prev_ar)
        avg_inv = _average(inventory, prev_inv)
        avg_ap = _average(accounts_payable, prev_ap)

        dso_r = WorkingCapitalEngine.dso(avg_ar, revenue)
        dio_r = WorkingCapitalEngine.dio(avg_inv, cogs)
        dpo_r = WorkingCapitalEngine.dpo(avg_ap, cogs)
        ccc_r = WorkingCapitalEngine.ccc(
            dso_r.value, dio_r.value, dpo_r.value,
        )

        # ─── PER SHARE ─────────────────────────────────────────
        shares = shares_outstanding or latest_income_a.get("shares_basic")
        total_eq = equity_parent if equity_parent is not None else total_equity
        bvps_val = None
        if total_eq and shares and shares > 0:
            equity_vnd = total_eq * 1_000_000_000 if (total_eq < 10_000_000 and shares > 100_000) else total_eq
            bvps_val = equity_vnd / shares
        eps_ttm_val = None
        is_eps_estimate = False
        eps_diagnostic = None
        ni_ttm = ttm.get("net_income_parent") if ttm.get("net_income_parent") is not None else ttm.get("net_income")
        if ni_ttm is not None and shares and shares > 0:
            eps_ttm_val = (ni_ttm * 1_000_000_000) / shares
            # If shares was not directly provided as statement shares_basic, it's a period-end fallback estimate
            has_statement_shares_basic = bool(
                latest_income_a.get("shares_basic") or 
                (income_quarters and any(bool(q.get("shares_basic")) for q in income_quarters[-4:]))
            )
            if not has_statement_shares_basic:
                is_eps_estimate = True
                eps_diagnostic = "WEIGHTED_AVERAGE_UNAVAILABLE_FALLBACK_TO_PERIOD_END_OUTSTANDING"
        elif ttm.get("eps_basic") is not None and ttm.get("eps_basic") > 0:
            eps_ttm_val = ttm.get("eps_basic")
        if eps_ttm_val is None:
            eps_ttm_val = eps_basic

        # ─── TREND ANALYSIS ────────────────────────────────────
        rev_series = [(str(a.get("fiscal_period_end", "")), a.get("revenue")) for a in income_annual]
        ni_series = [(str(a.get("fiscal_period_end", "")), a.get("net_income_parent") or a.get("net_income")) for a in income_annual]
        gm_series = [(str(a.get("fiscal_period_end", "")),
                      (a.get("gross_profit") / a.get("revenue") * 100)
                      if a.get("gross_profit") and a.get("revenue") else None)
                     for a in income_annual]

        rev_trend = TrendEngine.compute_trend("revenue", rev_series)
        ni_trend = TrendEngine.compute_trend("net_income", ni_series)
        gm_trend = TrendEngine.compute_trend("gross_margin", gm_series)

        # ─── QUALITY FLAGS ─────────────────────────────────────
        ni_series_vals = [a.get("net_income_parent") or a.get("net_income") for a in income_annual]
        cfo_series_vals = [c.get("cash_from_operations") for c in cashflow_annual]
        gm_vals = [v for _, v in gm_series]

        prev_revenue = revenue_prior
        prev_ar_val = prev_bs.get("accounts_receivable")
        prev_inv_val = prev_bs.get("inventory")

        roe_val = roe_r.value if roe_r.data_status == DataStatus.VALID else None
        prev_roe_r = ProfitabilityEngine.roe(
            net_income_prior,
            balance_annual[-3].get("equity_parent") if len(balance_annual) >= 3 else None,
            equity_parent_prior,
        ) if len(balance_annual) >= 2 else MetricResult.missing("roe", "roe_v1", "Insufficient history")
        prev_roe_val = prev_roe_r.value if prev_roe_r.data_status == DataStatus.VALID else None

        from .engine import OneOffEarningsDetector, EarningsQualityEngine
        one_off_result = OneOffEarningsDetector.detect(
            net_income=net_income,
            operating_income=operating_income,
            other_income=latest_income_a.get("other_income") if latest_income_a else None,
            cfo=cfo,
            gross_margin=gross_margin_r.value if gross_margin_r.data_status == DataStatus.VALID else None,
            prev_gross_margin=gm_vals[-2] if len(gm_vals) >= 2 else None,
        )
        has_one_off_val = one_off_result.get("has_one_off")

        flags = QualityFlagEngine.detect_flags(
            symbol=self.symbol,
            period=str(latest_period_end),
            gross_debt=gross_debt_val,
            total_assets=total_assets,
            cfo_series=cfo_series_vals,
            ni_series=ni_series_vals,
            gross_margin_series=gm_vals,
            ar=accounts_receivable,
            ar_prior=prev_ar_val,
            revenue=revenue,
            revenue_prior=prev_revenue,
            inventory=inventory,
            inventory_prior=prev_inv_val,
            fcf=fcf_val,
            roe=roe_val,
            roe_prior=prev_roe_val,
            has_one_off=bool(has_one_off_val) if has_one_off_val is not None else False,
        )

        # ─── EARNINGS QUALITY ──────────────────────────────────
        earnings_quality = EarningsQualityEngine.analyze(
            net_income=net_income,
            net_income_parent=net_income_parent,
            operating_income=operating_income,
            other_income=latest_income_a.get("other_income") if latest_income_a else None,
            cfo=cfo,
            fcf=fcf_val,
            has_one_off=has_one_off_val,
        )
        earnings_quality["one_off_reasons"] = one_off_result.get("reasons", [])

        # ─── SECTOR METRICS ────────────────────────────────────
        sector_snap = self._sector_model.calculate_metrics(0, {
            "income": latest_income_a or {},
            "balance_sheet": latest_bs or {},
            "cash_flow": latest_cf or {},
            "prev_balance_sheet": prev_bs or {},
            "avg_earning_assets": latest_bs.get("loans_and_advances"),  # bank proxy
            "shares_basic": shares,
        })

        # ─── FINANCIAL HEALTH SCORE ────────────────────────────
        health = FinancialHealthScorer.score(
            roe=roe_val,
            net_margin=net_margin_r.value if net_margin_r.data_status == DataStatus.VALID else None,
            revenue_yoy=revenue_yoy_r.value if revenue_yoy_r.data_status == DataStatus.VALID else None,
            eps_yoy=eps_yoy_r.value if eps_yoy_r.data_status == DataStatus.VALID else None,
            cfo_to_ni=cfo_ni_r.value if cfo_ni_r.data_status == DataStatus.VALID else None,
            fcf=fcf_val,
            de_ratio=de_ratio_r.value if de_ratio_r.data_status == DataStatus.VALID else None,
            current_ratio=current_ratio_r.value if current_ratio_r.data_status == DataStatus.VALID else None,
            gross_margin_trend=gm_trend.label,
            flags=flags,
            sector=self.sector,
        )

        # ─── DATA QUALITY ──────────────────────────────────────
        def completeness_check(*vals) -> float:
            total = len(vals)
            present = sum(1 for v in vals if v is not None)
            return round(present / total, 2) if total > 0 else 0.0

        data_quality = {
            "financial_data_completeness": completeness_check(
                revenue, net_income, total_assets, total_equity,
                cfo, gross_profit, ebit,
            ),
            "historical_depth_years": len(income_annual),
            "historical_depth_label": (
                "Robust (5Y+)" if len(income_annual) >= 5 else
                "Moderate (3Y+)" if len(income_annual) >= 3 else
                "Limited (< 3Y)"
            ),
            "ttm_available": ttm_ok,
            "sector": self.sector,
            "statement_consistency": "NOT_CHECKED",  # Phase 2: basic
            "source_reliability": "FIXTURE" if self.symbol.startswith("FIXTURE_") else "SECONDARY",
        }

        # ─── ASSEMBLE SNAPSHOT ─────────────────────────────────
        def _mr(r: MetricResult) -> dict:
            return r.to_dict()

        snapshot = {
            "symbol": self.symbol,
            "sector": self.sector,
            "period": period,
            "as_of": str(latest_period_end) if latest_period_end else None,
            "calculation_version": self.CALCULATION_VERSION,
            "ttm": ttm,
            "revenue_ttm": revenue if ttm_ok else None,
            "net_income_ttm": (net_income_parent or net_income) if ttm_ok else None,
            "revenue_annual": latest_income_a.get("revenue") if latest_income_a else None,
            "net_income_annual": (latest_income_a.get("net_income_parent") or latest_income_a.get("net_income")) if latest_income_a else None,
            "bvps": bvps_val,
            "eps_ttm": eps_ttm_val,
            "eps_basic": latest_income_a.get("eps_basic") if latest_income_a else None,

            "growth": {
                "revenue_yoy": _mr(revenue_yoy_r),
                "net_income_yoy": _mr(ni_yoy_r),
                "eps_yoy": _mr(eps_yoy_r),
                "revenue_cagr_3y": _mr(rev_cagr_3y_r),
                "revenue_cagr_5y": _mr(rev_cagr_5y_r),
                "eps_cagr_3y": _mr(eps_cagr_3y_r),
            },

            "profitability": {
                "gross_margin": _mr(gross_margin_r),
                "ebit_margin": _mr(ebit_margin_r),
                "ebitda_margin": _mr(ebitda_margin_r),
                "net_margin": _mr(net_margin_r),
                "cfo_margin": _mr(cfo_margin_r),
                "roe": _mr(roe_r),
                "roa": _mr(roa_r),
                "roic": _mr(roic_r),
            },

            "balance_sheet": {
                "cash": cash,
                "gross_debt": gross_debt_val,
                "net_debt": net_debt_val,
                "total_equity": total_equity,
                "equity_parent": equity_parent,
                "total_assets": total_assets,
                "de_ratio": _mr(de_ratio_r),
                "net_debt_ebitda": _mr(net_debt_ebitda_r),
                "debt_to_assets": _mr(debt_assets_r),
                "current_ratio": _mr(current_ratio_r),
                "quick_ratio": _mr(quick_ratio_r),
                "interest_coverage": _mr(interest_cov_r),
                "bvps": bvps_val,
            },

            "cash_flow": {
                "cfo": cfo,
                "capex": capex_val,
                "fcf": fcf_val,
                "cfo_to_ni": _mr(cfo_ni_r),
                "fcf_to_ni": _mr(fcf_ni_r),
            },

            "efficiency": {
                "dso": _mr(dso_r),
                "dio": _mr(dio_r),
                "dpo": _mr(dpo_r),
                "ccc": _mr(ccc_r),
            },

            "per_share": {
                "eps_ttm": eps_ttm_val,
                "bvps": bvps_val,
                "shares_basic": shares,
                "is_eps_estimate": is_eps_estimate,
                "eps_diagnostic_reason": eps_diagnostic,
            },

            "trends": {
                "revenue": rev_trend.to_dict(),
                "net_income": ni_trend.to_dict(),
                "gross_margin": gm_trend.to_dict(),
            },

            "earnings_quality": earnings_quality,

            "sector_metrics": {
                "sector": sector_snap.sector,
                "metrics": {k: _mr(v) for k, v in sector_snap.metrics.items()},
                "not_applicable": sector_snap.not_applicable,
                "notes": sector_snap.notes,
            },

            "financial_health": health,

            "flags": [
                {
                    "type": f.flag_type.value,
                    "severity": f.severity,
                    "description": f.description,
                    "description_vi": f.description_vi,
                    "evidence": f.evidence,
                }
                for f in flags
            ],

            "data_quality": data_quality,
            "sources": sources if sources is not None else (["CANONICAL_DATABASE"] if not self.symbol.startswith("FIXTURE_") else ["SYNTHETIC_FIXTURE"]),
        }

        return snapshot
