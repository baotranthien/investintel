"""
Core computation engine for the Fundamental Engine.

Implements:
  - TTM (Trailing Twelve Months)
  - YoY (Year over Year)
  - QoQ (Quarter over Quarter)
  - CAGR (3Y, 5Y)
  - Margin calculations
  - Profitability (ROE, ROA, ROIC)
  - Capital structure / Debt
  - Liquidity
  - Coverage
  - Cash flow quality
  - Working capital (DSO, DIO, DPO, CCC)
  - EPS engine
  - Trend engine
  - Acceleration engine
  - Quality flag engine

Rules:
  - Deterministic only. No LLM.
  - Missing → NULL + data_status (never 0)
  - Negative denominator → NOT_MEANINGFUL
  - Zero denominator → DENOMINATOR_ZERO (NOT_MEANINGFUL)
  - CAGR with negative base → NOT_MEANINGFUL (not_meaningful)
  - No look-ahead: metrics use only publication_date <= as_of_date
"""

from __future__ import annotations

import math
import statistics
from datetime import date, datetime
from typing import Optional, Any

from .models import (
    MetricResult, DataStatus, ValueStatus, TrendLabel, TrendResult,
    QualityFlagResult, FlagType,
)
from .formula_registry import FORMULA_REGISTRY

EPSILON = 1e-10  # near-zero threshold


# ─────────────────────────────────────────────────────────
# Safe arithmetic helpers
# ─────────────────────────────────────────────────────────

def _safe_ratio(numerator: Optional[float], denominator: Optional[float],
                metric_id: str, version: str, unit: str = "ratio",
                period: str = "TTM") -> MetricResult:
    """Safely compute numerator / denominator, returning MetricResult."""
    if numerator is None:
        return MetricResult.missing(metric_id, version, "Numerator data not available", unit, period)
    if denominator is None:
        return MetricResult.missing(metric_id, version, "Denominator data not available", unit, period)
    if abs(denominator) < EPSILON:
        return MetricResult(
            value=None, unit=unit, metric_id=metric_id, calculation_version=version,
            period=period, data_status=DataStatus.DENOMINATOR_ZERO,
            not_meaningful_reason="Denominator is zero — ratio not meaningful.",
        )
    if denominator < 0:
        return MetricResult(
            value=None, unit=unit, metric_id=metric_id, calculation_version=version,
            period=period, data_status=DataStatus.NEGATIVE_DENOMINATOR,
            not_meaningful_reason="Negative denominator — ratio not meaningful.",
        )
    return MetricResult(
        value=numerator / denominator, unit=unit, metric_id=metric_id,
        calculation_version=version, period=period,
        data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
    )


def _safe_pct(numerator: Optional[float], denominator: Optional[float],
              metric_id: str, version: str, period: str = "TTM") -> MetricResult:
    """Like _safe_ratio but returns percentage (×100)."""
    r = _safe_ratio(numerator, denominator, metric_id, version, "%", period)
    if r.value is not None:
        r.value = r.value * 100
    return r


def _average(*values: Optional[float]) -> Optional[float]:
    """Average of non-None values; returns None if all None."""
    non_null = [v for v in values if v is not None]
    return sum(non_null) / len(non_null) if non_null else None


# ─────────────────────────────────────────────────────────
# TTM ENGINE
# ─────────────────────────────────────────────────────────

class TTMEngine:
    """
    Trailing Twelve Months aggregation.
    Requires last 4 fiscal quarters (sorted chronologically).
    Flow metrics: sum over 4 quarters.
    Balance sheet: use latest quarter (snapshot).
    """

    FLOW_METRICS = {
        "revenue", "gross_profit", "operating_income", "ebit", "ebitda",
        "net_income", "net_income_parent", "cash_from_operations",
        "cash_from_investing", "cash_from_financing", "capex",
        "dividends_paid", "depreciation_amortization", "interest_income",
        "interest_expense", "income_tax", "pre_tax_income",
        "selling_expense", "general_admin_expense", "cost_of_goods_sold",
    }

    @classmethod
    def compute_ttm_income(
        cls,
        quarters: list[dict],  # list of normalized income dicts, sorted by fiscal_period_end asc
    ) -> dict[str, Optional[float]]:
        """
        Sum last 4 quarters for flow items.
        quarters[-1] is most recent.
        Returns dict of canonical_metric → TTM value.
        """
        if len(quarters) < 4:
            return {}
        last_4 = quarters[-4:]
        ttm: dict[str, Optional[float]] = {}
        for metric in cls.FLOW_METRICS:
            values = [q.get(metric) for q in last_4]
            non_null = [v for v in values if v is not None]
            if len(non_null) < 4:
                # Fail-closed: Never sum partial quarters (< 4) into a 12-month TTM flow metric!
                ttm[metric] = None
            else:
                ttm[metric] = sum(non_null)
        # EPS TTM: require all 4 quarters to have positive reported basic EPS
        eps_values = [q.get("eps_basic") for q in last_4 if q.get("eps_basic") is not None and q.get("eps_basic") > 0]
        ttm["eps_basic"] = sum(eps_values) if len(eps_values) == 4 else None
        ttm["eps_diluted"] = sum(
            q.get("eps_diluted") for q in last_4
            if q.get("eps_diluted") is not None
        ) if len([q for q in last_4 if q.get("eps_diluted")]) == 4 else None
        return ttm

    @classmethod
    def validate_quarter_coverage(cls, quarters: list[dict]) -> tuple[bool, str]:
        """Check that quarters cover 4 consecutive non-overlapping discrete quarters."""
        from services.contracts.validators import validate_quarterly_continuity
        valid, reason, _ = validate_quarterly_continuity(quarters)
        return valid, reason


# ─────────────────────────────────────────────────────────
# GROWTH ENGINE (YoY, QoQ, CAGR)
# ─────────────────────────────────────────────────────────

class GrowthEngine:

    @staticmethod
    def yoy(current: Optional[float], prior: Optional[float],
            metric_id: str, version: str, period: str = "ANNUAL") -> MetricResult:
        """YoY = current / prior - 1."""
        if current is None:
            return MetricResult.missing(metric_id, version, "Current period data missing", "%", period)
        if prior is None:
            return MetricResult.missing(metric_id, version, "Prior year data not available", "%", period)
        if abs(prior) < EPSILON:
            return MetricResult(
                value=None, unit="%", metric_id=metric_id, calculation_version=version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Prior year value is zero — growth rate not meaningful.",
            )
        if prior < 0:
            return MetricResult(
                value=None, unit="%", metric_id=metric_id, calculation_version=version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Prior year value is negative — YoY growth not meaningful.",
            )
        return MetricResult(
            value=(current / prior - 1) * 100,
            unit="%", metric_id=metric_id, calculation_version=version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )

    @staticmethod
    def qoq(current: Optional[float], prior_quarter: Optional[float],
            metric_id: str, version: str) -> MetricResult:
        """QoQ = current / prior_quarter - 1. Warns about seasonal effects."""
        if current is None:
            return MetricResult.missing(metric_id, version, "Current quarter data missing", "%", "QoQ")
        if prior_quarter is None:
            return MetricResult.missing(metric_id, version, "Prior quarter data not available", "%", "QoQ")
        if abs(prior_quarter) < EPSILON:
            return MetricResult(
                value=None, unit="%", metric_id=metric_id, calculation_version=version,
                period="QoQ", data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Prior quarter value is zero.",
            )
        return MetricResult(
            value=(current / prior_quarter - 1) * 100,
            unit="%", metric_id=metric_id, calculation_version=version,
            period="QoQ", data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )

    @staticmethod
    def cagr(
        base_value: Optional[float],
        end_value: Optional[float],
        n_years: int,
        metric_id: str,
        version: str,
        period: str,
    ) -> MetricResult:
        """
        CAGR = (end / base) ^ (1/n) - 1.
        NOT_MEANINGFUL when base ≤ 0 or end ≤ 0.
        """
        label = f"{n_years}Y"
        if base_value is None or end_value is None:
            return MetricResult.missing(metric_id, version, "Insufficient data for CAGR", "%", period)
        if n_years < 1:
            return MetricResult.not_meaningful(metric_id, version, "n_years must be ≥ 1", "%", period)
        if base_value <= 0 or end_value <= 0:
            return MetricResult(
                value=None, unit="%", metric_id=metric_id, calculation_version=version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason=f"Negative or zero value — {label} CAGR not meaningful.",
            )
        try:
            cagr_val = ((end_value / base_value) ** (1 / n_years) - 1) * 100
        except (ZeroDivisionError, ValueError):
            return MetricResult.not_meaningful(metric_id, version, "Computation error in CAGR", "%", period)
        return MetricResult(
            value=cagr_val, unit="%", metric_id=metric_id, calculation_version=version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )


# ─────────────────────────────────────────────────────────
# MARGIN ENGINE
# ─────────────────────────────────────────────────────────

class MarginEngine:

    @staticmethod
    def gross_margin(gross_profit: Optional[float], revenue: Optional[float], period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["gross_margin"]
        return _safe_pct(gross_profit, revenue, spec.metric_id, spec.version, period)

    @staticmethod
    def ebit_margin(ebit: Optional[float], revenue: Optional[float], period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["ebit_margin"]
        return _safe_pct(ebit, revenue, spec.metric_id, spec.version, period)

    @staticmethod
    def ebitda_margin(ebitda: Optional[float], revenue: Optional[float], period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["ebitda_margin"]
        return _safe_pct(ebitda, revenue, spec.metric_id, spec.version, period)

    @staticmethod
    def net_margin(net_income_parent: Optional[float], revenue: Optional[float], period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["net_margin"]
        return _safe_pct(net_income_parent, revenue, spec.metric_id, spec.version, period)

    @staticmethod
    def cfo_margin(cfo: Optional[float], revenue: Optional[float], period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["cfo_margin"]
        return _safe_pct(cfo, revenue, spec.metric_id, spec.version, period)


# ─────────────────────────────────────────────────────────
# PROFITABILITY ENGINE
# ─────────────────────────────────────────────────────────

class ProfitabilityEngine:

    @staticmethod
    def roe(
        net_income_parent: Optional[float],
        equity_parent_start: Optional[float],
        equity_parent_end: Optional[float],
        period: str = "ANNUAL",
    ) -> MetricResult:
        """ROE = Net Income (Parent) / Average Equity (Parent)."""
        spec = FORMULA_REGISTRY["roe"]
        avg_equity = _average(equity_parent_start, equity_parent_end)
        if avg_equity is not None and avg_equity <= 0:
            return MetricResult(
                value=None, unit="%", metric_id=spec.metric_id, calculation_version=spec.version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Average equity ≤ 0 — ROE not meaningful.",
            )
        return _safe_pct(net_income_parent, avg_equity, spec.metric_id, spec.version, period)

    @staticmethod
    def roa(
        net_income: Optional[float],
        assets_start: Optional[float],
        assets_end: Optional[float],
        period: str = "ANNUAL",
    ) -> MetricResult:
        """ROA = Net Income / Average Total Assets."""
        spec = FORMULA_REGISTRY["roa"]
        avg_assets = _average(assets_start, assets_end)
        return _safe_pct(net_income, avg_assets, spec.metric_id, spec.version, period)

    @staticmethod
    def roic(
        operating_income: Optional[float],
        effective_tax_rate: Optional[float],
        total_equity: Optional[float],
        gross_debt: Optional[float],
        cash: Optional[float],
        period: str = "ANNUAL",
        sector: str = "GENERAL",
    ) -> MetricResult:
        """
        ROIC = NOPAT / Invested Capital
        NOPAT = EBIT × (1 - effective_tax_rate)
        Invested Capital = Total Equity + Gross Debt - Cash
        Not applicable for BANK sector.
        """
        spec = FORMULA_REGISTRY["roic"]
        if sector == "BANK":
            return MetricResult(
                value=None, unit="%", metric_id=spec.metric_id, calculation_version=spec.version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="ROIC is not applicable for the banking sector. Use ROE/ROA instead.",
            )
        if operating_income is None:
            return MetricResult.missing(spec.metric_id, spec.version, "EBIT not available", "%", period)
        tax_rate = effective_tax_rate if effective_tax_rate is not None else 0.20
        nopat = operating_income * (1 - tax_rate)
        e = total_equity or 0.0
        d = gross_debt or 0.0
        c = cash or 0.0
        invested_capital = e + d - c
        if abs(invested_capital) < EPSILON or invested_capital < 0:
            return MetricResult(
                value=None, unit="%", metric_id=spec.metric_id, calculation_version=spec.version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Invested capital ≤ 0 — ROIC not meaningful.",
            )
        return MetricResult(
            value=(nopat / invested_capital) * 100,
            unit="%", metric_id=spec.metric_id, calculation_version=spec.version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )


# ─────────────────────────────────────────────────────────
# CAPITAL STRUCTURE / DEBT ENGINE
# ─────────────────────────────────────────────────────────

class DebtEngine:

    @staticmethod
    def gross_debt(short_term_debt: Optional[float], long_term_debt: Optional[float]) -> Optional[float]:
        a = short_term_debt or 0.0
        b = long_term_debt or 0.0
        if short_term_debt is None and long_term_debt is None:
            return None
        return a + b

    @staticmethod
    def net_debt(gross_debt: Optional[float], cash: Optional[float],
                 short_term_investments: Optional[float]) -> Optional[float]:
        if gross_debt is None:
            return None
        liquid = (cash or 0.0) + (short_term_investments or 0.0)
        return gross_debt - liquid

    @staticmethod
    def de_ratio(gross_debt: Optional[float], equity_parent: Optional[float],
                 period: str = "ANNUAL") -> MetricResult:
        spec = FORMULA_REGISTRY["de_ratio"]
        return _safe_ratio(gross_debt, equity_parent, spec.metric_id, spec.version, "ratio", period)

    @staticmethod
    def net_debt_ebitda(net_debt: Optional[float], ebitda: Optional[float],
                        period: str = "TTM", sector: str = "GENERAL") -> MetricResult:
        spec = FORMULA_REGISTRY["net_debt_ebitda"]
        if sector == "BANK":
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Not applicable for banking sector.", "times", period)
        return _safe_ratio(net_debt, ebitda, spec.metric_id, spec.version, "times", period)

    @staticmethod
    def debt_to_assets(total_liabilities: Optional[float], total_assets: Optional[float],
                       period: str = "ANNUAL") -> MetricResult:
        spec = FORMULA_REGISTRY["debt_to_assets"]
        return _safe_pct(total_liabilities, total_assets, spec.metric_id, spec.version, period)


# ─────────────────────────────────────────────────────────
# LIQUIDITY ENGINE
# ─────────────────────────────────────────────────────────

class LiquidityEngine:

    @staticmethod
    def current_ratio(current_assets: Optional[float], current_liabilities: Optional[float],
                      period: str = "ANNUAL", sector: str = "GENERAL") -> MetricResult:
        spec = FORMULA_REGISTRY["current_ratio"]
        if sector == "BANK":
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Current ratio is not applicable for banks.", "ratio", period)
        return _safe_ratio(current_assets, current_liabilities, spec.metric_id, spec.version, "ratio", period)

    @staticmethod
    def quick_ratio(current_assets: Optional[float], inventory: Optional[float],
                    current_liabilities: Optional[float], period: str = "ANNUAL",
                    sector: str = "GENERAL") -> MetricResult:
        spec = FORMULA_REGISTRY["quick_ratio"]
        if sector == "BANK":
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Quick ratio is not applicable for banks.", "ratio", period)
        quick_assets = (current_assets or 0.0) - (inventory or 0.0)
        if current_assets is None:
            return MetricResult.missing(spec.metric_id, spec.version, "Current assets missing", "ratio", period)
        return _safe_ratio(quick_assets, current_liabilities, spec.metric_id, spec.version, "ratio", period)


# ─────────────────────────────────────────────────────────
# COVERAGE ENGINE
# ─────────────────────────────────────────────────────────

class CoverageEngine:

    @staticmethod
    def interest_coverage(ebit: Optional[float], interest_expense: Optional[float],
                          period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["interest_coverage"]
        if interest_expense is None or abs(interest_expense) < EPSILON:
            return MetricResult(
                value=None, unit="times", metric_id=spec.metric_id, calculation_version=spec.version,
                period=period, data_status=DataStatus.NOT_MEANINGFUL,
                not_meaningful_reason="Interest expense is zero or missing — coverage ratio N/A.",
            )
        # interest_expense stored as negative; use absolute value
        ie = abs(interest_expense)
        return _safe_ratio(ebit, ie, spec.metric_id, spec.version, "times", period)


# ─────────────────────────────────────────────────────────
# CASH FLOW QUALITY ENGINE
# ─────────────────────────────────────────────────────────

class CashFlowQualityEngine:

    @staticmethod
    def fcf(cfo: Optional[float], capex: Optional[float]) -> Optional[float]:
        """FCF = CFO - |Capex|. Capex stored as negative."""
        if cfo is None:
            return None
        capex_abs = abs(capex) if capex is not None else 0.0
        return cfo - capex_abs

    @staticmethod
    def cfo_to_ni(cfo: Optional[float], net_income: Optional[float],
                  period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["cfo_to_ni"]
        if net_income is not None and net_income <= 0:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Net income ≤ 0 — CFO/NI not meaningful.", "ratio", period)
        return _safe_ratio(cfo, net_income, spec.metric_id, spec.version, "ratio", period)

    @staticmethod
    def fcf_to_ni(fcf: Optional[float], net_income: Optional[float],
                  period: str = "TTM") -> MetricResult:
        spec = FORMULA_REGISTRY["fcf_to_ni"]
        if net_income is not None and net_income <= 0:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Net income ≤ 0 — FCF/NI not meaningful.", "ratio", period)
        return _safe_ratio(fcf, net_income, spec.metric_id, spec.version, "ratio", period)

    @staticmethod
    def detect_divergence(
        net_income_series: list[Optional[float]],
        cfo_series: list[Optional[float]],
    ) -> bool:
        """
        Returns True if Net Income is consistently positive while CFO is consistently negative.
        This is a CashFlowDivergence flag — not a fraud conclusion.
        """
        if len(net_income_series) < 3 or len(cfo_series) < 3:
            return False
        ni_pos = all(v is not None and v > 0 for v in net_income_series[-3:])
        cfo_neg = all(v is not None and v < 0 for v in cfo_series[-3:])
        return ni_pos and cfo_neg


# ─────────────────────────────────────────────────────────
# WORKING CAPITAL ENGINE
# ─────────────────────────────────────────────────────────

class WorkingCapitalEngine:

    @staticmethod
    def dso(avg_accounts_receivable: Optional[float], revenue: Optional[float],
            days: int = 365, period: str = "ANNUAL") -> MetricResult:
        """DSO = Average AR / Revenue × days."""
        spec = FORMULA_REGISTRY["dso"]
        if revenue is None or abs(revenue) < EPSILON:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Revenue is zero or missing.", "days", period)
        if avg_accounts_receivable is None:
            return MetricResult.missing(spec.metric_id, spec.version, "Accounts receivable missing", "days", period)
        return MetricResult(
            value=(avg_accounts_receivable / revenue) * days,
            unit="days", metric_id=spec.metric_id, calculation_version=spec.version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )

    @staticmethod
    def dio(avg_inventory: Optional[float], cogs: Optional[float],
            days: int = 365, period: str = "ANNUAL") -> MetricResult:
        """DIO = Average Inventory / COGS × days."""
        spec = FORMULA_REGISTRY["dio"]
        if cogs is None or abs(cogs) < EPSILON:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "COGS is zero or missing — may be a service company.", "days", period)
        if avg_inventory is None:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "Inventory data not available.", "days", period)
        return MetricResult(
            value=(avg_inventory / abs(cogs)) * days,
            unit="days", metric_id=spec.metric_id, calculation_version=spec.version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )

    @staticmethod
    def dpo(avg_accounts_payable: Optional[float], cogs: Optional[float],
            days: int = 365, period: str = "ANNUAL") -> MetricResult:
        """DPO = Average AP / COGS × days."""
        spec = FORMULA_REGISTRY["dpo"]
        if cogs is None or abs(cogs) < EPSILON:
            return MetricResult.not_meaningful(spec.metric_id, spec.version,
                                               "COGS is zero or missing.", "days", period)
        if avg_accounts_payable is None:
            return MetricResult.missing(spec.metric_id, spec.version, "Accounts payable missing", "days", period)
        return MetricResult(
            value=(avg_accounts_payable / abs(cogs)) * days,
            unit="days", metric_id=spec.metric_id, calculation_version=spec.version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )

    @staticmethod
    def ccc(dso: Optional[float], dio: Optional[float], dpo: Optional[float],
            period: str = "ANNUAL") -> MetricResult:
        """CCC = DSO + DIO - DPO."""
        spec = FORMULA_REGISTRY["ccc"]
        if dso is None or dpo is None:
            return MetricResult.missing(spec.metric_id, spec.version,
                                        "DSO or DPO missing for CCC calculation.", "days", period)
        ccc_val = (dso or 0.0) + (dio or 0.0) - (dpo or 0.0)
        return MetricResult(
            value=ccc_val, unit="days", metric_id=spec.metric_id, calculation_version=spec.version,
            period=period, data_status=DataStatus.VALID, value_status=ValueStatus.DERIVED,
        )


# ─────────────────────────────────────────────────────────
# TREND ENGINE
# ─────────────────────────────────────────────────────────

class TrendEngine:
    """
    Deterministic trend engine.
    Input: list of (period_label, value) pairs, sorted by period ascending.
    """

    MIN_PERIODS_FOR_TREND = 3

    @classmethod
    def compute_trend(cls, metric_id: str, series: list[tuple[str, Optional[float]]]) -> TrendResult:
        """
        Classify trend as Improving / Stable / Deteriorating / Volatile / Insufficient Data.
        Uses linear slope and recent period comparison.
        """
        version = "trend_v1"
        valid_series = [(p, v) for p, v in series if v is not None]
        periods = [p for p, _ in valid_series]
        values = [v for _, v in valid_series]

        if len(values) < cls.MIN_PERIODS_FOR_TREND:
            return TrendResult(
                metric_id=metric_id,
                label=TrendLabel.INSUFFICIENT_DATA,
                recent_values=values,
                periods=periods,
                note=f"Needs ≥ {cls.MIN_PERIODS_FOR_TREND} data points.",
                calculation_version=version,
            )

        # Compute slope (simple linear regression)
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        slope = numerator / denominator if abs(denominator) > EPSILON else 0.0

        # Coefficient of variation (volatility)
        try:
            std = statistics.stdev(values)
            cv = abs(std / y_mean) if abs(y_mean) > EPSILON else 0.0
        except statistics.StatisticsError:
            cv = 0.0

        # Classify
        if cv > 0.5:  # high volatility
            label = TrendLabel.VOLATILE
            note = "High variability across periods."
        elif abs(slope) < abs(y_mean) * 0.02:  # < 2% per-period change
            label = TrendLabel.STABLE
            note = "Broadly stable across periods."
        elif slope > 0:
            label = TrendLabel.IMPROVING
            note = "Positive trend over the observation period."
        else:
            label = TrendLabel.DETERIORATING
            note = "Negative trend over the observation period."

        return TrendResult(
            metric_id=metric_id,
            label=label,
            slope=round(slope, 4),
            recent_values=values[-5:],
            periods=periods[-5:],
            note=note,
            calculation_version=version,
        )


# ─────────────────────────────────────────────────────────
# ACCELERATION ENGINE
# ─────────────────────────────────────────────────────────

class AccelerationEngine:

    @staticmethod
    def detect_acceleration(yoy_series: list[Optional[float]]) -> Optional[str]:
        """
        Given YoY growth rates (ascending), detect if growth is accelerating.
        Returns: "Accelerating" | "Decelerating" | "Stable" | None
        """
        valid = [v for v in yoy_series if v is not None]
        if len(valid) < 3:
            return None
        last3 = valid[-3:]
        if last3[2] > last3[1] > last3[0]:
            return "Accelerating"
        if last3[2] < last3[1] < last3[0]:
            return "Decelerating"
        return "Stable"


# ─────────────────────────────────────────────────────────
# EARNINGS QUALITY ENGINE
# ─────────────────────────────────────────────────────────

class OneOffEarningsDetector:
    """
    Detects one-off/non-recurring earnings items based on:
    - unusual gains/losses / other income
    - discontinued operations
    - asset disposal / exceptional items
    - margin discontinuity (>10ppt jump)
    - abnormal cash vs earnings divergence
    Returns detection dictionary:
      {"has_one_off": bool | None, "status": "DETECTED" | "NONE_DETECTED" | "UNKNOWN", "reasons": list[str]}
    """
    @staticmethod
    def detect(
        net_income: Optional[float],
        operating_income: Optional[float],
        other_income: Optional[float] = None,
        cfo: Optional[float] = None,
        gross_margin: Optional[float] = None,
        prev_gross_margin: Optional[float] = None,
        exceptional_items: Optional[float] = None,
        discontinued_ops: Optional[float] = None,
    ) -> dict[str, Any]:
        flags = []
        if net_income is None:
            return {"has_one_off": None, "status": "UNKNOWN", "reasons": ["INSUFFICIENT_DATA"]}

        # 1. Other income / unusual gains
        if other_income is not None and abs(net_income) > EPSILON:
            if abs(other_income) / abs(net_income) > 0.20:
                flags.append(f"High other income ratio ({other_income / net_income:.1%} of net income)")

        # 2. Exceptional items or asset disposal
        if exceptional_items is not None and abs(exceptional_items) > EPSILON:
            flags.append("Exceptional items / asset disposal present")

        # 3. Discontinued operations
        if discontinued_ops is not None and abs(discontinued_ops) > EPSILON:
            flags.append("Discontinued operations present")

        # 4. Margin discontinuity
        if gross_margin is not None and prev_gross_margin is not None:
            if abs(gross_margin - prev_gross_margin) >= 10.0:
                flags.append(f"Margin discontinuity: shift of {gross_margin - prev_gross_margin:.1f} ppt")

        # 5. Abnormal cash vs earnings divergence
        if cfo is not None and net_income > EPSILON:
            if cfo < 0 or (abs(cfo - net_income) / net_income > 1.2 and cfo < net_income * 0.5):
                flags.append(f"Abnormal cash vs earnings divergence (CFO={cfo:,.0f}, NI={net_income:,.0f})")

        if flags:
            return {"has_one_off": True, "status": "DETECTED", "reasons": flags}
        return {"has_one_off": False, "status": "NONE_DETECTED", "reasons": []}


class EarningsQualityEngine:
    """
    Operating Profit Quality Framework:
      operating_profit_quality: Operating income / Net income (sustainability of earnings)
      cash_conversion: CFO / Net Income (accrual risk)
      recurring_earnings_quality: composite
      one_off_dependence: HIGH | LOW | UNKNOWN
    """

    @staticmethod
    def analyze(
        net_income: Optional[float],
        net_income_parent: Optional[float],
        operating_income: Optional[float],
        other_income: Optional[float],
        cfo: Optional[float],
        fcf: Optional[float],
        has_one_off: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Framework output:
          - operating_profit_quality: HIGH | MODERATE | LOW
          - cash_conversion: HIGH | MODERATE | LOW | NOT_MEANINGFUL
          - recurring_earnings_quality: HIGH | MODERATE | LOW
          - one_off_dependence: HIGH | LOW | UNKNOWN
        """
        result = {}

        # Operating profit quality
        if operating_income is not None and net_income is not None and abs(net_income) > EPSILON:
            op_ratio = operating_income / net_income
            if op_ratio >= 0.85:
                result["operating_profit_quality"] = "HIGH"
            elif op_ratio >= 0.60:
                result["operating_profit_quality"] = "MODERATE"
            else:
                result["operating_profit_quality"] = "LOW"
        else:
            result["operating_profit_quality"] = "INSUFFICIENT_DATA"

        # Cash conversion
        if cfo is not None and net_income is not None and net_income > EPSILON:
            cc = cfo / net_income
            if cc >= 0.9:
                result["cash_conversion"] = "HIGH"
            elif cc >= 0.6:
                result["cash_conversion"] = "MODERATE"
            elif cc >= 0:
                result["cash_conversion"] = "LOW"
            else:
                result["cash_conversion"] = "NEGATIVE_CFO"
        else:
            result["cash_conversion"] = "NOT_MEANINGFUL"

        # One-off dependence
        if has_one_off is None:
            result["one_off_dependence"] = "UNKNOWN"
        else:
            result["one_off_dependence"] = "HIGH" if has_one_off else "LOW"

        # Recurring earnings quality
        if result.get("operating_profit_quality") == "HIGH" and result.get("cash_conversion") == "HIGH":
            result["recurring_earnings_quality"] = "HIGH"
        elif result.get("operating_profit_quality") == "LOW" or result.get("cash_conversion") in ("LOW", "NEGATIVE_CFO"):
            result["recurring_earnings_quality"] = "LOW"
        else:
            result["recurring_earnings_quality"] = "MODERATE"

        return result


# ─────────────────────────────────────────────────────────
# QUALITY FLAG ENGINE
# ─────────────────────────────────────────────────────────

class QualityFlagEngine:

    @staticmethod
    def detect_flags(
        symbol: str,
        period: str,
        gross_debt: Optional[float],
        total_assets: Optional[float],
        cfo_series: list[Optional[float]],
        ni_series: list[Optional[float]],
        gross_margin_series: list[Optional[float]],
        ar: Optional[float],
        ar_prior: Optional[float],
        revenue: Optional[float],
        revenue_prior: Optional[float],
        inventory: Optional[float],
        inventory_prior: Optional[float],
        fcf: Optional[float],
        roe: Optional[float],
        roe_prior: Optional[float],
        has_one_off: Optional[bool] = None,
        revenue_yoy_series: list[Optional[float]] = None,
        eps_yoy_series: list[Optional[float]] = None,
    ) -> list[QualityFlagResult]:
        flags: list[QualityFlagResult] = []

        # HighDebt: D/Assets > 70%
        if gross_debt is not None and total_assets is not None and total_assets > EPSILON:
            if gross_debt / total_assets > 0.70:
                flags.append(QualityFlagResult(
                    flag_type=FlagType.HIGH_DEBT,
                    severity="WARNING",
                    description=f"Gross debt/assets exceeds 70%: {gross_debt/total_assets:.1%}",
                    description_vi=f"Tỷ lệ nợ vay/tổng tài sản vượt 70%: {gross_debt/total_assets:.1%}",
                    evidence={"gross_debt": gross_debt, "total_assets": total_assets},
                ))

        # CashFlowDivergence
        if CashFlowQualityEngine.detect_divergence(ni_series, cfo_series):
            flags.append(QualityFlagResult(
                flag_type=FlagType.CASH_FLOW_DIVERGENCE,
                severity="WARNING",
                description="Net income consistently positive while CFO consistently negative (last 3 periods).",
                description_vi="Lợi nhuận ròng dương liên tục nhưng dòng tiền hoạt động âm — cần kiểm tra.",
                evidence={"net_income_series": ni_series[-3:], "cfo_series": cfo_series[-3:]},
            ))

        # MarginCompression
        if len(gross_margin_series) >= 2:
            valid = [v for v in gross_margin_series if v is not None]
            if len(valid) >= 2 and valid[-1] < valid[-2] - 2.0:  # >2ppt drop
                flags.append(QualityFlagResult(
                    flag_type=FlagType.MARGIN_COMPRESSION,
                    severity="WARNING",
                    description=f"Gross margin compressed by >{valid[-2] - valid[-1]:.1f}ppt.",
                    description_vi=f"Biên lợi nhuận gộp giảm >{valid[-2] - valid[-1]:.1f} điểm %.",
                    evidence={"margin_series": valid[-3:]},
                ))

        # ReceivableGrowth
        if ar is not None and ar_prior is not None and revenue is not None and revenue_prior is not None:
            if ar_prior > EPSILON and revenue_prior > EPSILON:
                ar_growth = (ar / ar_prior - 1) * 100
                rev_growth = (revenue / revenue_prior - 1) * 100
                if ar_growth > rev_growth + 15:  # AR growing 15pp faster than revenue
                    flags.append(QualityFlagResult(
                        flag_type=FlagType.RECEIVABLE_GROWTH,
                        severity="WARNING",
                        description=f"AR growth ({ar_growth:.1f}%) materially exceeds revenue growth ({rev_growth:.1f}%).",
                        description_vi=f"Tăng trưởng phải thu ({ar_growth:.1f}%) vượt xa tăng trưởng doanh thu ({rev_growth:.1f}%).",
                        evidence={"ar_growth_pct": ar_growth, "revenue_growth_pct": rev_growth},
                    ))

        # InventoryBuild
        if inventory is not None and inventory_prior is not None and revenue is not None and revenue_prior is not None:
            if inventory_prior > EPSILON and revenue_prior > EPSILON:
                inv_growth = (inventory / inventory_prior - 1) * 100
                rev_growth = (revenue / revenue_prior - 1) * 100
                if inv_growth > rev_growth + 15:
                    flags.append(QualityFlagResult(
                        flag_type=FlagType.INVENTORY_BUILD,
                        severity="WARNING",
                        description=f"Inventory growth ({inv_growth:.1f}%) materially exceeds revenue growth ({rev_growth:.1f}%).",
                        description_vi=f"Tồn kho tăng ({inv_growth:.1f}%) vượt xa doanh thu ({rev_growth:.1f}%).",
                        evidence={"inventory_growth_pct": inv_growth, "revenue_growth_pct": rev_growth},
                    ))

        # NegativeFCF
        if fcf is not None and fcf < 0:
            flags.append(QualityFlagResult(
                flag_type=FlagType.NEGATIVE_FCF,
                severity="INFO",
                description=f"Free cash flow is negative: {fcf:,.0f}.",
                description_vi=f"Dòng tiền tự do âm: {fcf:,.0f}.",
                evidence={"fcf": fcf},
            ))

        # ROEDecline
        if roe is not None and roe_prior is not None:
            if roe < roe_prior - 3.0:  # >3ppt drop
                flags.append(QualityFlagResult(
                    flag_type=FlagType.ROE_DECLINE,
                    severity="WARNING",
                    description=f"ROE declined by {roe_prior - roe:.1f}ppt.",
                    description_vi=f"ROE giảm {roe_prior - roe:.1f} điểm %.",
                    evidence={"roe_current": roe, "roe_prior": roe_prior},
                ))

        # OneOffProfit
        if has_one_off:
            flags.append(QualityFlagResult(
                flag_type=FlagType.ONE_OFF_PROFIT,
                severity="INFO",
                description="One-off/non-recurring income items detected in this period.",
                description_vi="Có các khoản thu nhập một lần/không lặp lại trong kỳ.",
                evidence={},
            ))

        # RevenueAcceleration
        if revenue_yoy_series:
            acc = AccelerationEngine.detect_acceleration(revenue_yoy_series)
            if acc == "Accelerating":
                flags.append(QualityFlagResult(
                    flag_type=FlagType.REVENUE_ACCELERATION,
                    severity="INFO",
                    description="Revenue growth is accelerating over recent periods.",
                    description_vi="Tăng trưởng doanh thu đang tăng tốc.",
                    evidence={"yoy_series": revenue_yoy_series[-3:]},
                ))

        # EarningsAcceleration
        if eps_yoy_series:
            acc = AccelerationEngine.detect_acceleration(eps_yoy_series)
            if acc == "Accelerating":
                flags.append(QualityFlagResult(
                    flag_type=FlagType.EARNINGS_ACCELERATION,
                    severity="INFO",
                    description="EPS growth is accelerating over recent periods.",
                    description_vi="Tăng trưởng EPS đang tăng tốc.",
                    evidence={"yoy_series": eps_yoy_series[-3:]},
                ))

        return flags


# ─────────────────────────────────────────────────────────
# FINANCIAL HEALTH SCORE (Optional baseline — not investment score)
# ─────────────────────────────────────────────────────────

class FinancialHealthScorer:
    """
    Produces a Financial Health score (0–100) from deterministic rules.
    Components: Profitability, Growth, Cash Flow, Balance Sheet, Stability.
    This is a RESEARCH metric. NOT a Buy/Sell recommendation.
    """

    @staticmethod
    def score(
        roe: Optional[float],
        net_margin: Optional[float],
        revenue_yoy: Optional[float],
        eps_yoy: Optional[float],
        cfo_to_ni: Optional[float],
        fcf: Optional[float],
        de_ratio: Optional[float],
        current_ratio: Optional[float],
        gross_margin_trend: TrendLabel,
        flags: list[QualityFlagResult],
        sector: str = "GENERAL",
    ) -> dict[str, Any]:
        """
        Compute financial health score. Returns dict with score + breakdown.
        """
        components = {}
        weights = {
            "profitability": 0.25,
            "growth": 0.25,
            "cash_flow": 0.25,
            "balance_sheet": 0.15,
            "stability": 0.10,
        }

        # Profitability (0–100)
        prof_score = 50.0  # default
        if roe is not None:
            if roe >= 20:
                prof_score = 90
            elif roe >= 15:
                prof_score = 75
            elif roe >= 10:
                prof_score = 60
            elif roe >= 0:
                prof_score = 40
            else:
                prof_score = 10
        if net_margin is not None:
            margin_boost = min(20, net_margin)  # cap at 20ppt bonus
            prof_score = min(100, prof_score + margin_boost / 2)
        components["profitability"] = round(prof_score, 1)

        # Growth (0–100)
        growth_score = 50.0
        if revenue_yoy is not None:
            if revenue_yoy >= 20:
                growth_score = 90
            elif revenue_yoy >= 10:
                growth_score = 75
            elif revenue_yoy >= 5:
                growth_score = 60
            elif revenue_yoy >= 0:
                growth_score = 45
            else:
                growth_score = 20
        if eps_yoy is not None and eps_yoy > 0:
            growth_score = min(100, growth_score + 5)
        components["growth"] = round(growth_score, 1)

        # Cash Flow (0–100)
        cf_score = 50.0
        if cfo_to_ni is not None:
            if cfo_to_ni >= 1.0:
                cf_score = 90
            elif cfo_to_ni >= 0.7:
                cf_score = 70
            elif cfo_to_ni >= 0.4:
                cf_score = 50
            elif cfo_to_ni >= 0:
                cf_score = 30
            else:
                cf_score = 10
        if fcf is not None and fcf < 0:
            cf_score = max(10, cf_score - 20)
        components["cash_flow"] = round(cf_score, 1)

        # Balance Sheet (0–100)
        bs_score = 60.0
        if de_ratio is not None:
            if de_ratio <= 0.3:
                bs_score = 90
            elif de_ratio <= 0.8:
                bs_score = 70
            elif de_ratio <= 1.5:
                bs_score = 50
            elif de_ratio <= 3.0:
                bs_score = 30
            else:
                bs_score = 10
        # Banks: skip de_ratio
        if sector == "BANK":
            bs_score = 60.0
        components["balance_sheet"] = round(bs_score, 1)

        # Stability (flags impact)
        flag_types = {f.flag_type for f in flags}
        stability_score = 80.0
        if FlagType.CASH_FLOW_DIVERGENCE in flag_types:
            stability_score -= 20
        if FlagType.MARGIN_COMPRESSION in flag_types:
            stability_score -= 10
        if FlagType.HIGH_DEBT in flag_types:
            stability_score -= 10
        if FlagType.RECEIVABLE_GROWTH in flag_types:
            stability_score -= 10
        stability_score = max(10, stability_score)
        components["stability"] = round(stability_score, 1)

        # Weighted total
        total = sum(components[k] * weights[k] for k in weights)
        components["total"] = round(total, 1)

        # Labels
        def label(v):
            if v >= 80:
                return "Strong"
            if v >= 65:
                return "Healthy"
            if v >= 50:
                return "Moderate"
            if v >= 35:
                return "Weak"
            return "Poor"

        return {
            "score": components["total"],
            "label": label(components["total"]),
            "components": {
                "profitability": {"score": components["profitability"], "label": label(components["profitability"])},
                "growth": {"score": components["growth"], "label": label(components["growth"])},
                "cash_flow": {"score": components["cash_flow"], "label": label(components["cash_flow"])},
                "balance_sheet": {"score": components["balance_sheet"], "label": label(components["balance_sheet"])},
                "stability": {"score": components["stability"], "label": label(components["stability"])},
            },
            "disclaimer": "Điểm sức khỏe tài chính — chỉ phục vụ nghiên cứu. Không phải khuyến nghị mua/bán.",
        }
