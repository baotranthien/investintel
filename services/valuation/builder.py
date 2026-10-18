from typing import Dict, Any, List
from datetime import date
from .models import ValuationSnapshot, CompositeFairValue, FairValueRange, ValuationMethodOutput, DCFAssumptions
from .selector import ValuationMethodSelector
from .engine import DCFEngine, ResidualIncomeEngine, RelativeValuationEngine

class ValuationSnapshotBuilder:
    def __init__(self, symbol: str, sector: str):
        self.symbol = symbol.upper()
        self.sector = sector.upper()
        self.selector = ValuationMethodSelector(self.symbol, self.sector)

    def build(self, fundamentals: Dict[str, Any], current_price: float, as_of: date) -> ValuationSnapshot:
        selection = self.selector.select_methods(fundamentals)
        methods = []
        
        eps = fundamentals.get("eps_ttm", 0)
        bvps = fundamentals.get("bvps", 0)
        shares_outstanding = fundamentals.get("shares_outstanding", 1_000_000_000)
        
        # Retrieve peer and historical multiples from dataset (None if missing)
        peer_pe = fundamentals.get("peer_pe")
        hist_pe = fundamentals.get("hist_pe")
        
        peer_pb = fundamentals.get("peer_pb")
        hist_pb = fundamentals.get("hist_pb")
        
        # Execute selected methods
        if "P/E" in selection.primary_methods or "P/E" in selection.secondary_methods:
            out = RelativeValuationEngine.calculate("P/E", current_price / eps if eps > 0 else 0, peer_pe, hist_pe, eps)
            out.weight = (0.4 if "P/E" in selection.primary_methods else 0.1) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        if "P/B" in selection.primary_methods or "P/B" in selection.secondary_methods:
            out = RelativeValuationEngine.calculate("P/B", current_price / bvps if bvps > 0 else 0, peer_pb, hist_pb, bvps)
            out.weight = (0.4 if "P/B" in selection.primary_methods else 0.1) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        if "DCF" in selection.primary_methods or "DCF" in selection.secondary_methods:
            base_rev = fundamentals.get("revenue_ttm")
            dcf_assump = DCFAssumptions(
                revenue_growth_rates=[0.10, 0.09, 0.08, 0.07, 0.06],
                ebit_margins=[0.20, 0.20, 0.20, 0.20, 0.20],
                tax_rate=0.20,
                wacc=0.12,
                terminal_growth_rate=0.03,
                base_revenue=base_rev
            )
            out = DCFEngine.calculate(dcf_assump, shares_outstanding, net_debt=fundamentals.get("net_debt", 0))
            out.weight = (0.5 if "DCF" in selection.primary_methods else 0.2) if out.applicability != "NOT_APPLICABLE" else 0.0
            methods.append(out)
            
        if "Residual Income" in selection.primary_methods:
            out = ResidualIncomeEngine.calculate(bvps=bvps, roe=0.18, cost_of_equity=0.12, growth=0.05)
            out.weight = 0.5
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
        
        # Check method disagreement (e.g. if dispersion is high)
        disagreement = False
        reason = None
        if methods:
            bases = [m.fair_value.base for m in methods if m.fair_value.base > 0]
            if bases and max(bases) > min(bases) * 1.5:
                disagreement = True
                reason = "High dispersion between intrinsic and relative valuation methods."
                
        composite = CompositeFairValue(
            range=FairValueRange(bear=comp_bear, base=comp_base, bull=comp_bull),
            confidence="MEDIUM" if not disagreement else "LOW",
            method_disagreement=disagreement,
            disagreement_reason=reason
        )
        
        margin_of_safety = (comp_base - current_price) / comp_base if comp_base > 0 else None
        
        return ValuationSnapshot(
            symbol=self.symbol,
            as_of=as_of,
            price_as_of=current_price,
            methods=methods,
            composite_fair_value=composite,
            scenarios=[],
            margin_of_safety=margin_of_safety
        )
