from typing import Dict, Any, List, Optional
from datetime import date
from .models import ValuationSnapshot, CompositeFairValue, FairValueRange, DCFAssumptions, ValuationScenario
from .selector import ValuationMethodSelector
from .engine import DCFEngine, ResidualIncomeEngine, RelativeValuationEngine

class ValuationSnapshotBuilder:
    def __init__(self, symbol: str, sector: Optional[str] = "GENERAL"):
        self.symbol = symbol.upper()
        self.sector = (sector or "GENERAL").upper()
        self.selector = ValuationMethodSelector(self.symbol, self.sector)

    def build_dcf_context(self, fundamentals: Dict[str, Any]) -> tuple[DCFAssumptions, float, bool, bool]:
        """Build canonical DCF assumptions, cost of equity, real-estate flag, and cyclical flag."""
        use_dyn = bool(fundamentals.get("use_dynamic_assumptions", False))
        cyclical_commodity_sectors = {"OIL_GAS", "ENERGY", "STEEL", "REAL_ESTATE"}
        cyclical_commodity_tickers = {"HPG", "HSG", "NKG", "DCM", "DPM", "GVR", "PHR", "HT1"}
        real_estate_tickers = {"VHM", "NLG", "KDH", "NVL", "PDR", "DXG", "KBC", "BCM", "VRE", "HDG", "DIG", "CEO", "SCR"}
        is_real_estate = self.sector == "REAL_ESTATE" or self.symbol in real_estate_tickers
        is_cyclical_sector = (self.sector in cyclical_commodity_sectors) or (
            self.sector == "MATERIALS" and self.symbol in cyclical_commodity_tickers
        )

        if use_dyn:
            rev_cagr = fundamentals.get("revenue_cagr_3y")
            rev_yoy = fundamentals.get("revenue_yoy")
            if rev_cagr is not None and abs(rev_cagr) > 1.0:
                rev_cagr /= 100.0
            if rev_yoy is not None and abs(rev_yoy) > 1.0:
                rev_yoy /= 100.0

            if rev_cagr is not None and rev_yoy is not None:
                g1 = 0.60 * rev_cagr + 0.40 * rev_yoy
            elif rev_cagr is not None:
                g1 = rev_cagr
            elif rev_yoy is not None:
                g1 = rev_yoy
            else:
                g1 = None

            if g1 is not None:
                max_g1 = 0.14 if is_cyclical_sector else 0.26
                g1 = max(0.03, min(max_g1, g1))
                g5 = max(0.05 if is_cyclical_sector else 0.06, min(0.08, (g1 + 0.03) / 2.0))
                revenue_growth_rates = [round(g1 - (g1 - g5) * (i / 4.0), 4) for i in range(5)]
            else:
                revenue_growth_rates = [0.10, 0.09, 0.08, 0.07, 0.06]

            op_m = fundamentals.get("operating_margin")
            if op_m is not None and abs(op_m) > 1.0:
                op_m /= 100.0
            if op_m is not None:
                base_m = max(0.008, min(0.40, op_m))
                if is_cyclical_sector and base_m > 0.14:
                    target_m = 0.15 if is_real_estate else 0.115
                    ebit_margins = [round(base_m - (base_m - target_m) * (i / 4.0), 4) for i in range(5)]
                else:
                    target_m = 0.20 if base_m > 0.22 else base_m
                    ebit_margins = [round(base_m - (base_m - target_m) * 0.20 * (i / 4.0), 4) for i in range(5)]
            else:
                base_m = 0.15
                ebit_margins = [0.15] * 5

            dcf_wacc = float(fundamentals.get("wacc") or 0.12)
            cost_of_equity = float(fundamentals.get("cost_of_equity") or 0.12)
            capex_pct = fundamentals.get("capex_to_revenue")
            if capex_pct is not None and abs(capex_pct) > 1.0:
                capex_pct = abs(capex_pct) / 100.0
            if capex_pct is None:
                capex_pct = round(max(0.003, min(0.06, base_m * 0.25)), 4)
            if is_real_estate:
                capex_pct = max(capex_pct, 0.10)
        else:
            revenue_growth_rates = [0.10, 0.09, 0.08, 0.07, 0.06]
            ebit_margins = [0.20, 0.20, 0.20, 0.20, 0.20]
            dcf_wacc = 0.12
            cost_of_equity = 0.12
            capex_pct = None

        base_rev = fundamentals.get("revenue_ttm") or fundamentals.get("revenue_annual") or fundamentals.get("latest_annual_revenue")
        dcf_assump = DCFAssumptions(
            revenue_growth_rates=revenue_growth_rates,
            ebit_margins=ebit_margins,
            tax_rate=0.20,
            wacc=dcf_wacc,
            terminal_growth_rate=0.03,
            base_revenue=base_rev,
            capex_percent_rev=capex_pct,
        )
        return dcf_assump, cost_of_equity, is_real_estate, is_cyclical_sector

    def build(self, fundamentals: Dict[str, Any], current_price: float, as_of: date) -> ValuationSnapshot:
        selection = self.selector.select_methods(fundamentals)
        methods = []
        
        eps = fundamentals.get("eps_ttm") or 0
        bvps = fundamentals.get("bvps") or 0
        shares_outstanding = fundamentals.get("shares_outstanding", 1_000_000_000)
        
        # Retrieve peer and historical multiples from dataset (None if missing)
        peer_pe = fundamentals.get("peer_pe")
        hist_pe = fundamentals.get("hist_pe")
        
        peer_pb = fundamentals.get("peer_pb")
        hist_pb = fundamentals.get("hist_pb")
        
        use_dyn = bool(fundamentals.get("use_dynamic_assumptions", False))
        dcf_assump, cost_of_equity, is_real_estate, is_cyclical_sector = self.build_dcf_context(fundamentals)

        # Execute selected methods
        if "P/E" in selection.primary_methods or "P/E" in selection.secondary_methods:
            out = RelativeValuationEngine.calculate("P/E", current_price / eps if eps > 0 else 0, peer_pe, hist_pe, eps)
            out.weight = (0.4 if "P/E" in selection.primary_methods else 0.1) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        if "P/B" in selection.primary_methods or "P/B" in selection.secondary_methods:
            out = RelativeValuationEngine.calculate("P/B", current_price / bvps if bvps > 0 else 0, peer_pb, hist_pb, bvps)
            out.weight = (0.4 if "P/B" in selection.primary_methods else 0.1) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        dcf_sensitivity: Optional[Dict[str, Any]] = None
        rnav_normalized = False
        rnav_scale = 1.0
        if "DCF" in selection.primary_methods or "DCF" in selection.secondary_methods:
            out = DCFEngine.calculate(dcf_assump, shares_outstanding, net_debt=fundamentals.get("net_debt", 0))
            out.weight = (0.5 if "DCF" in selection.primary_methods else 0.2) if out.applicability != "NOT_APPLICABLE" else 0.0
            if out.applicability != "NOT_APPLICABLE":
                # Pillar 1: Real Estate RNAV normalization (prevent single-quarter bulk handover distortion)
                if is_real_estate and bvps and bvps > 0 and out.fair_value.base > bvps * 1.45:
                    rnav_scale = (bvps * 1.35) / out.fair_value.base
                    out.fair_value = FairValueRange(
                        bear=round(out.fair_value.bear * rnav_scale, 0),
                        base=round(out.fair_value.base * rnav_scale, 0),
                        bull=round(out.fair_value.bull * rnav_scale, 0),
                    )
                    out.warnings.append(
                        f"REAL_ESTATE_RNAV_NORMALIZATION: Capped bulk-handover DCF peak to sustainable landbank-adjusted RNAV band ({out.fair_value.base:,.0f} VND/share)."
                    )
                    rnav_normalized = True
                dcf_sensitivity = DCFEngine.calculate_sensitivity_matrix(
                    dcf_assump, shares_outstanding, net_debt=fundamentals.get("net_debt", 0)
                )
                if rnav_normalized and dcf_sensitivity:
                    dcf_sensitivity["p10"] = round(float(dcf_sensitivity["p10"]) * rnav_scale, 0)
                    dcf_sensitivity["p50"] = round(float(dcf_sensitivity["p50"]) * rnav_scale, 0)
                    dcf_sensitivity["p90"] = round(float(dcf_sensitivity["p90"]) * rnav_scale, 0)
                    for g_row in dcf_sensitivity.get("grid", []):
                        g_row["fair_value"] = round(float(g_row["fair_value"]) * rnav_scale, 0)
            methods.append(out)
            
        if "Residual Income" in selection.primary_methods or "Residual Income" in selection.secondary_methods:
            real_roe = fundamentals.get("roe")
            if real_roe is not None and real_roe != 0:
                roe_val = (real_roe / 100.0) if abs(real_roe) > 1.0 else float(real_roe)
            else:
                roe_val = 0.18
            ri_growth = min(0.045, max(0.030, roe_val * 0.20)) if use_dyn else 0.04
            ri_coe = max(0.115, cost_of_equity) if use_dyn else 0.12
            out = ResidualIncomeEngine.calculate(bvps=bvps, roe=roe_val, cost_of_equity=ri_coe, growth=ri_growth)
            out.weight = (0.5 if "Residual Income" in selection.primary_methods else 0.2) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        # Normalize weights
        total_weight = sum(m.weight for m in methods)
        for m in methods:
            if total_weight > 0:
                m.weight = m.weight / total_weight
                
        # Composite calculation
        comp_bear = sum(m.fair_value.bear * m.weight for m in methods)
        comp_base = sum(m.fair_value.base * m.weight for m in methods)
        comp_bull = sum(m.fair_value.bull * m.weight for m in methods)
        
        # Check method disagreement and valid methods
        disagreement = False
        reason = None
        has_valid_method = any(m.fair_value.base > 0 for m in methods if m.weight > 0)
        excluded_methods = [m.method for m in methods if m.applicability == "NOT_APPLICABLE" or m.weight == 0.0]
        
        snapshot_warnings = []
        if rnav_normalized:
            snapshot_warnings.append(
                f"REAL_ESTATE_RNAV_NORMALIZATION: Anchored {self.symbol} DCF peak to sustainable landbank-adjusted RNAV range."
            )
        if use_dyn and is_cyclical_sector:
            snapshot_warnings.append(
                f"CYCLICAL_PEAK_DAMPING: Applied mid-cycle growth and EBIT margin mean-reversion for {self.sector}."
            )
        if excluded_methods:
            snapshot_warnings.append(
                f"Excluded methods from composite fair value (weight=0.0): {', '.join(excluded_methods)}"
            )

        if methods and has_valid_method:
            bases = [m.fair_value.base for m in methods if m.fair_value.base > 0 and m.weight > 0]
            if bases and max(bases) > min(bases) * 1.5:
                disagreement = True
                reason = "High dispersion between intrinsic and relative valuation methods."
                
        composite = CompositeFairValue(
            range=FairValueRange(bear=comp_bear, base=comp_base, bull=comp_bull),
            confidence="MEDIUM" if (has_valid_method and not disagreement and not excluded_methods) else "LOW",
            method_disagreement=disagreement,
            disagreement_reason=reason if has_valid_method else "INSUFFICIENT_DATA: No valuation method has sufficient data"
        )
        
        margin_of_safety = (comp_base - current_price) / comp_base if comp_base > 0 else None

        scenarios: List[ValuationScenario] = []
        if dcf_sensitivity and dcf_sensitivity.get("p50"):
            scenarios = [
                ValuationScenario(
                    scenario_name="Bear / Tightening Stress (P10)",
                    description=f"WACC {dcf_sensitivity['wacc_base_pct'] + 1.0:.2f}%, terminal g {max(1.5, dcf_sensitivity['terminal_g_base_pct'] - 0.5):.2f}%",
                    fair_value=float(dcf_sensitivity["p10"]),
                    assumptions={"p10": dcf_sensitivity["p10"], "p50": dcf_sensitivity["p50"], "p90": dcf_sensitivity["p90"], "grid": dcf_sensitivity["grid"]},
                ),
                ValuationScenario(
                    scenario_name="Base Case (P50)",
                    description=f"WACC {dcf_sensitivity['wacc_base_pct']:.2f}%, terminal g {dcf_sensitivity['terminal_g_base_pct']:.2f}%",
                    fair_value=float(dcf_sensitivity["p50"]),
                    assumptions={"wacc_pct": dcf_sensitivity["wacc_base_pct"], "terminal_g_pct": dcf_sensitivity["terminal_g_base_pct"]},
                ),
                ValuationScenario(
                    scenario_name="Bull / Easing Upside (P90)",
                    description=f"WACC {max(7.0, dcf_sensitivity['wacc_base_pct'] - 1.0):.2f}%, terminal g {dcf_sensitivity['terminal_g_base_pct'] + 0.5:.2f}%",
                    fair_value=float(dcf_sensitivity["p90"]),
                    assumptions={"p10": dcf_sensitivity["p10"], "p50": dcf_sensitivity["p50"], "p90": dcf_sensitivity["p90"]},
                ),
            ]
        elif comp_base > 0:
            scenarios = [
                ValuationScenario(scenario_name="Bear Case", description="Conservative downside band", fair_value=round(comp_bear, 0), assumptions={}),
                ValuationScenario(scenario_name="Base Case", description="Central composite estimate", fair_value=round(comp_base, 0), assumptions={}),
                ValuationScenario(scenario_name="Bull Case", description="Constructive upside band", fair_value=round(comp_bull, 0), assumptions={}),
            ]

        return ValuationSnapshot(
            symbol=self.symbol,
            as_of=as_of,
            price_as_of=current_price,
            methods=methods,
            composite_fair_value=composite,
            scenarios=scenarios,
            margin_of_safety=margin_of_safety,
            warnings=snapshot_warnings
        )
