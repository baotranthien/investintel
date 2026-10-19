from typing import List, Dict, Any
from pydantic import BaseModel

class MethodSelectionResult(BaseModel):
    primary_methods: List[str]
    secondary_methods: List[str]
    excluded_methods: List[str]
    reasons: Dict[str, str]

class ValuationMethodSelector:
    """
    Selects valuation methods based on sector, industry, and fundamental characteristics.
    """
    
    # Pre-configured baseline method weights for different sectors
    BASELINE_WEIGHTS = {
        "BANK": {
            "P/B": 0.40,
            "Residual Income": 0.40,
            "P/E": 0.20
        },
        "TECHNOLOGY": {
            "DCF": 0.40,
            "P/E": 0.30,
            "EV/EBITDA": 0.30
        },
        "RETAIL": {
            "EV/EBITDA": 0.50,
            "P/E": 0.30,
            "DCF": 0.20
        },
        "MATERIALS": {
            "EV/EBITDA": 0.40,
            "P/B": 0.30,
            "P/E": 0.30
        },
        "DEFAULT": {
            "P/E": 0.40,
            "DCF": 0.40,
            "EV/EBITDA": 0.20
        }
    }

    def __init__(self, symbol: str, sector: str, industry: str = ""):
        self.symbol = symbol.upper()
        self.sector = sector.upper()
        self.industry = industry.upper()
        
    def select_methods(self, fundamentals: Dict[str, Any]) -> MethodSelectionResult:
        """
        Evaluate fundamentals and determine applicability of valuation methods.
        fundamentals dict should contain basic info like:
        - eps_ttm (float)
        - ebitda_ttm (float)
        - book_value_per_share (float)
        - is_financial (bool)
        - fcf_ttm (float)
        """
        primary = []
        secondary = []
        excluded = []
        reasons = {}
        
        eps = fundamentals.get("eps_ttm", 0)
        ebitda = fundamentals.get("ebitda_ttm", 0)
        fcf = fundamentals.get("fcf_ttm", 0)
        is_financial = self.sector in ["BANK", "BANKING", "FINANCIAL SERVICES", "INSURANCE", "FINANCIALS"]
        
        # 1. P/E Method
        if eps > 0:
            if is_financial:
                secondary.append("P/E")
                reasons["P/E"] = "Secondary for financials, useful but not primary like P/B."
            else:
                primary.append("P/E")
                reasons["P/E"] = "Primary method for companies with positive earnings."
        else:
            excluded.append("P/E")
            reasons["P/E"] = "Excluded due to negative earnings."
            
        # 2. P/B Method
        if is_financial:
            primary.append("P/B")
            reasons["P/B"] = "Primary valuation method for financial institutions."
        else:
            secondary.append("P/B")
            reasons["P/B"] = "Secondary method for non-financials, useful for asset-heavy businesses."
            
        # 3. EV/EBITDA Method
        if is_financial:
            excluded.append("EV/EBITDA")
            reasons["EV/EBITDA"] = "Not conceptually suitable for financial companies."
        elif ebitda > 0:
            primary.append("EV/EBITDA")
            reasons["EV/EBITDA"] = "Primary cash flow proxy for operating businesses."
        else:
            excluded.append("EV/EBITDA")
            reasons["EV/EBITDA"] = "Excluded due to negative EBITDA."
            
        # 4. DCF Method
        if is_financial:
            excluded.append("DCF")
            reasons["DCF"] = "Standard DCF excludes financials due to debt structure; use Residual Income or DDM instead."
        elif fcf > 0 or eps > 0:
            primary.append("DCF")
            reasons["DCF"] = "Primary intrinsic valuation based on free cash flows."
        else:
            secondary.append("DCF")
            reasons["DCF"] = "Cash flows currently negative, requires strong assumptions for turnaround."
            
        # 5. Residual Income
        if is_financial:
            primary.append("Residual Income")
            reasons["Residual Income"] = "Primary intrinsic valuation for banks."
        else:
            excluded.append("Residual Income")
            reasons["Residual Income"] = "Typically reserved for financial institutions."
            
        # 6. FCF Yield
        if not is_financial and fcf > 0:
            secondary.append("FCF Yield")
            reasons["FCF Yield"] = "Good secondary metric when FCF is economically meaningful."
        else:
            excluded.append("FCF Yield")
            reasons["FCF Yield"] = "Not meaningful for financials or negative FCF."
            
        # Refine by specific sectors
        if self.sector == "TECHNOLOGY":
            if "P/E" in secondary:
                secondary.remove("P/E")
                primary.append("P/E")
        elif self.sector == "RETAIL":
            if "EV/EBITDA" not in primary and "EV/EBITDA" not in excluded:
                primary.append("EV/EBITDA")
                
        return MethodSelectionResult(
            primary_methods=primary,
            secondary_methods=secondary,
            excluded_methods=excluded,
            reasons=reasons
        )
