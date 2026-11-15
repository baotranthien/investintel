from typing import Dict, Any, Optional
from .models import ValuationMethodOutput, FairValueRange, ValuationAssumption, DCFAssumptions

class DCFEngine:
    @staticmethod
    def _eval_single_dcf(
        assumptions: DCFAssumptions,
        shares_outstanding: int,
        net_debt: Optional[float],
        wacc_adj: float,
        g_adj: float,
        margin_adj: float,
    ) -> float:
        """Evaluate one (wacc, g, margin) DCF sensitivity point in VND/share."""
        if assumptions.base_revenue is None or assumptions.base_revenue <= 0 or shares_outstanding == 0:
            return 0.0
        fcf = []
        current_rev = assumptions.base_revenue
        for i in range(len(assumptions.revenue_growth_rates)):
            growth = assumptions.revenue_growth_rates[i]
            base_m_i = assumptions.ebit_margins[i]
            scaled_adj = margin_adj * (base_m_i / 0.06) if base_m_i < 0.06 else margin_adj
            margin = max(0.002, base_m_i + scaled_adj)
            current_rev *= (1 + growth)
            ebit = current_rev * margin
            nopat = ebit * (1 - assumptions.tax_rate)
            if assumptions.capex_percent_rev is not None or assumptions.wc_percent_rev is not None:
                reinvestment_rate = max(-0.05, min(0.12, (assumptions.capex_percent_rev or 0.0) + (assumptions.wc_percent_rev or 0.0)))
                projected_fcf = nopat - (current_rev * reinvestment_rate)
            else:
                projected_fcf = nopat
            fcf.append(projected_fcf)

        wacc = assumptions.wacc + wacc_adj
        tg = assumptions.terminal_growth_rate + g_adj
        if wacc <= tg:
            return 0.0
        terminal_fcf = fcf[-1] * (1 + tg)
        terminal_value = terminal_fcf / (wacc - tg)
        pv_fcf = sum(cf / ((1 + wacc) ** (i + 1)) for i, cf in enumerate(fcf))
        pv_tv = terminal_value / ((1 + wacc) ** len(fcf))
        equity_value = (pv_fcf + pv_tv) - (net_debt or 0.0)

        shares_raw = float(shares_outstanding)
        if 0 < shares_raw < 100_000:
            shares_raw *= 1_000_000_000 if shares_raw < 10_000 else 1_000_000
        return (equity_value * 1_000_000_000) / shares_raw

    @staticmethod
    def calculate_sensitivity_matrix(
        assumptions: DCFAssumptions,
        shares_outstanding: int,
        net_debt: Optional[float] = 0.0,
        wacc_deltas: tuple[float, ...] = (-0.01, 0.0, 0.01),
        g_deltas: tuple[float, ...] = (-0.005, 0.0, 0.005),
    ) -> Dict[str, Any]:
        """Compute 3x3 WACC x terminal-g sensitivity matrix and P10/P50/P90 quantiles."""
        grid = []
        all_vals: list[float] = []
        for dw in wacc_deltas:
            for dg in g_deltas:
                fv = DCFEngine._eval_single_dcf(assumptions, shares_outstanding, net_debt, dw, dg, 0.0)
                if fv > 0:
                    all_vals.append(fv)
                grid.append({
                    "wacc": round((assumptions.wacc + dw) * 100.0, 2),
                    "terminal_g": round((assumptions.terminal_growth_rate + dg) * 100.0, 2),
                    "fair_value": round(fv, 0),
                })
        sorted_vals = sorted(all_vals)
        n = len(sorted_vals)
        p10 = round(sorted_vals[max(0, int(0.10 * (n - 1)))], 0) if n else 0.0
        p50 = round(sorted_vals[n // 2], 0) if n else 0.0
        p90 = round(sorted_vals[min(n - 1, int(0.90 * (n - 1)))], 0) if n else 0.0
        return {
            "wacc_base_pct": round(assumptions.wacc * 100.0, 2),
            "terminal_g_base_pct": round(assumptions.terminal_growth_rate * 100.0, 2),
            "grid": grid,
            "p10": p10,
            "p50": p50,
            "p90": p90,
        }

    @staticmethod
    def calculate(
        assumptions: DCFAssumptions,
        shares_outstanding: int,
        net_debt: Optional[float] = 0.0,  # Debt - Cash; None treated as 0 (unlevered)
    ) -> ValuationMethodOutput:
        """
        Standard Discounted Cash Flow.
        Calculates firm value based on forecasted cash flows, then equity value, then per share.
        Returns Bear, Base, Bull by flexing the assumptions.
        If base_revenue is not provided or <= 0, returns INSUFFICIENT_DATA.
        """
        if net_debt is None:
            net_debt = 0.0
        if assumptions.base_revenue is None or assumptions.base_revenue <= 0:
            return ValuationMethodOutput(
                method="DCF",
                fair_value=FairValueRange(bear=0.0, base=0.0, bull=0.0),
                applicability="NOT_APPLICABLE",
                confidence="LOW",
                weight=0.0,
                warnings=["INSUFFICIENT_DATA: Base revenue missing or non-positive. Cannot perform DCF."]
            )

        if assumptions.wacc <= assumptions.terminal_growth_rate:
            return ValuationMethodOutput(
                method="DCF",
                fair_value=FairValueRange(bear=0.0, base=0.0, bull=0.0),
                applicability="NOT_APPLICABLE",
                confidence="LOW",
                weight=0.0,
                warnings=["INVALID_ASSUMPTION: Terminal growth rate (g_t) must be strictly less than WACC. Gordon Growth Model is undefined for WACC <= g_t."]
            )

        def _calc_dcf(wacc_adj: float, g_adj: float, margin_adj: float) -> float:
            return DCFEngine._eval_single_dcf(assumptions, shares_outstanding, net_debt, wacc_adj, g_adj, margin_adj)

        # Generate Scenarios (Flexing WACC, Terminal Growth, and Margins)
        base_value = _calc_dcf(0, 0, 0)
        bear_value = _calc_dcf(wacc_adj=0.01, g_adj=-0.005, margin_adj=-0.01)
        bull_value = _calc_dcf(wacc_adj=-0.01, g_adj=0.005, margin_adj=0.01)
        
        # Sort to ensure bear < base < bull
        values = sorted([bear_value, base_value, bull_value])
        
        range_out = FairValueRange(
            bear=values[0],
            base=values[1],
            bull=values[2]
        )
        
        assumptions_list = [
            ValuationAssumption(
                name="Base Revenue",
                value=round(assumptions.base_revenue, 1),
                unit="VND Billion",
                source="Canonical Financial Statements",
                type="OBSERVED",
            ),
            ValuationAssumption(
                name="WACC",
                value=round(assumptions.wacc * 100, 1),
                unit="%",
                source="Model baseline (Cost of Capital)",
                type="MODEL_ASSUMPTION",
            ),
            ValuationAssumption(
                name="Terminal Growth Rate",
                value=round(assumptions.terminal_growth_rate * 100, 1),
                unit="%",
                source="Long-term GDP growth proxy",
                type="MODEL_ASSUMPTION",
            ),
            ValuationAssumption(
                name="EBIT Margin",
                value=round(assumptions.ebit_margins[0] * 100, 1),
                unit="%",
                source="Baseline operating margin",
                type="HISTORICAL_DERIVED",
            ),
            ValuationAssumption(
                name="Tax Rate",
                value=round(assumptions.tax_rate * 100, 1),
                unit="%",
                source="Corporate tax rate (20%)",
                type="OBSERVED",
            ),
        ]

        return ValuationMethodOutput(
            method="DCF",
            fair_value=range_out,
            applicability="HIGH",
            confidence="MEDIUM",
            weight=0.0, # Will be set by ensemble
            assumptions_used=assumptions_list,
            warnings=[f"DCF inputs: Base Revenue={assumptions.base_revenue:,.1f}B VND, WACC={assumptions.wacc:.1%}, Terminal Growth={assumptions.terminal_growth_rate:.1%}, Tax={assumptions.tax_rate:.1%}"]
        )

class ResidualIncomeEngine:
    @staticmethod
    def calculate(
        bvps: float,
        roe: float,
        cost_of_equity: float,
        growth: float,
        years: int = 5
    ) -> ValuationMethodOutput:
        """
        Residual Income Model, especially suited for banks.
        Value = BV0 + Sum( (ROE - Ke) * BV_t-1 / (1 + Ke)^t ) + TV
        """
        if bvps is None or bvps <= 0:
            return ValuationMethodOutput(
                method="Residual Income",
                fair_value=FairValueRange(bear=0.0, base=0.0, bull=0.0),
                applicability="NOT_APPLICABLE",
                confidence="LOW",
                weight=0.0,
                warnings=["INSUFFICIENT_DATA: Missing or non-positive book value per share (BVPS)"]
            )

        def _calc_ri(roe_adj: float, ke_adj: float, g_adj: float) -> float:
            adj_roe = roe + roe_adj
            adj_ke = cost_of_equity + ke_adj
            adj_g = growth + g_adj
            
            current_bv = bvps
            pv_ri = 0
            
            for t in range(1, years + 1):
                ri = (adj_roe - adj_ke) * current_bv
                pv_ri += ri / ((1 + adj_ke) ** t)
                current_bv *= (1 + adj_g)
                
            # Terminal Value of RI
            # Apply competitive fade (0.65) and minimum terminal spread (5.5%) to prevent near-zero denominator explosion
            if adj_ke > adj_g:
                terminal_spread = max(0.055, adj_ke - adj_g)
                tv_ri = ((adj_roe - adj_ke) * 0.65 * current_bv) / terminal_spread
            else:
                tv_ri = 0
            pv_tv_ri = tv_ri / ((1 + adj_ke) ** years)
            
            return bvps + pv_ri + pv_tv_ri
            
        base_value = _calc_ri(0, 0, 0)
        bear_value = _calc_ri(roe_adj=-0.02, ke_adj=0.01, g_adj=-0.01)
        bull_value = _calc_ri(roe_adj=0.02, ke_adj=-0.01, g_adj=0.01)
        
        values = sorted([bear_value, base_value, bull_value])
        
        ri_assumptions = [
            ValuationAssumption(
                name="BVPS",
                value=round(bvps, 0),
                unit="VND/share",
                source="Canonical Balance Sheet & Shares",
                type="OBSERVED",
            ),
            ValuationAssumption(
                name="ROE",
                value=round(roe * 100, 1),
                unit="%",
                source="Canonical Fundamentals",
                type="HISTORICAL_DERIVED",
            ),
            ValuationAssumption(
                name="Cost of Equity (Ke)",
                value=round(cost_of_equity * 100, 1),
                unit="%",
                source="Model baseline (CAPM proxy)",
                type="MODEL_ASSUMPTION",
            ),
            ValuationAssumption(
                name="Terminal Growth",
                value=round(growth * 100, 1),
                unit="%",
                source="Long-term economic growth proxy",
                type="MODEL_ASSUMPTION",
            ),
        ]

        return ValuationMethodOutput(
            method="Residual Income",
            fair_value=FairValueRange(bear=values[0], base=values[1], bull=values[2]),
            applicability="HIGH",
            confidence="MEDIUM",
            weight=0.0,
            assumptions_used=ri_assumptions,
            warnings=[f"Residual Income inputs: BVPS={bvps:,.0f} VND, ROE={roe:.1%}, Cost of Equity={cost_of_equity:.1%}, Growth={growth:.1%}"]
        )

class RelativeValuationEngine:
    @staticmethod
    def calculate(
        metric_name: str,
        company_metric_value: float,
        peer_median: float,
        historical_median: float,
        company_fundamental_driver: float, # e.g. EPS for P/E
    ) -> ValuationMethodOutput:
        """
        Calculates implied fair value based on multiples.
        """
        # If the driver is negative, multiple valuation is not meaningful
        if company_fundamental_driver <= 0:
            return ValuationMethodOutput(
                method=f"Relative {metric_name}",
                fair_value=FairValueRange(bear=0, base=0, bull=0),
                applicability="NOT_APPLICABLE",
                confidence="LOW",
                warnings=[f"Negative fundamental driver ({company_fundamental_driver})"]
            )

        if peer_median is None or peer_median <= 0:
            return ValuationMethodOutput(
                method=f"Relative {metric_name}",
                fair_value=FairValueRange(bear=0, base=0, bull=0),
                applicability="NOT_APPLICABLE",
                confidence="LOW",
                warnings=[f"INSUFFICIENT_DATA: Missing or invalid peer median for {metric_name}"]
            )
            
        # Blend peer and historical median for base multiple
        hist_val = historical_median if (historical_median is not None and historical_median > 0) else peer_median
        base_multiple = (peer_median * 0.5) + (hist_val * 0.5)
        bear_multiple = min(peer_median, hist_val) * 0.85
        bull_multiple = max(peer_median, hist_val) * 1.15
        
        base_value = base_multiple * company_fundamental_driver
        bear_value = bear_multiple * company_fundamental_driver
        bull_value = bull_multiple * company_fundamental_driver
        
        values = sorted([bear_value, base_value, bull_value])
        
        return ValuationMethodOutput(
            method=f"Relative {metric_name}",
            fair_value=FairValueRange(bear=values[0], base=values[1], bull=values[2]),
            applicability="HIGH",
            confidence="MEDIUM"
        )
