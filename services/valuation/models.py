from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import date

# -------------------------------------------------------------------------
# Assumptions
# -------------------------------------------------------------------------

class ValuationAssumption(BaseModel):
    name: str
    value: float | str | None
    unit: str
    source: str
    source_date: Optional[date] = None
    type: Literal["OBSERVED", "HISTORICAL_DERIVED", "USER_INPUT", "MODEL_ASSUMPTION", "EXTERNAL"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    version: str = "v1"

class DCFAssumptions(BaseModel):
    revenue_growth_rates: List[float] = Field(description="Year 1 to N growth rates")
    ebit_margins: List[float] = Field(description="Year 1 to N EBIT margins")
    tax_rate: float
    wacc: float = Field(description="Weighted Average Cost of Capital")
    terminal_growth_rate: float
    base_revenue: Optional[float] = Field(None, description="Actual base revenue in billions VND (required)")
    exit_multiple: Optional[float] = None
    capex_percent_rev: Optional[float] = None
    wc_percent_rev: Optional[float] = None
    
    def validate_assumptions(self):
        if self.wacc <= self.terminal_growth_rate:
            raise ValueError("WACC must be strictly greater than terminal growth rate (WACC > g)")

# -------------------------------------------------------------------------
# Outputs
# -------------------------------------------------------------------------

class FairValueRange(BaseModel):
    bear: float = Field(description="Bear case fair value")
    base: float = Field(description="Base case fair value")
    bull: float = Field(description="Bull case fair value")
    currency: str = "VND"

class ValuationMethodOutput(BaseModel):
    method: str = Field(description="Method name, e.g., 'DCF', 'P/E', 'Residual Income'")
    fair_value: FairValueRange
    implied_price: Optional[float] = Field(None, description="Point estimate if applicable")
    applicability: Literal["HIGH", "MEDIUM", "LOW", "NOT_APPLICABLE"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    weight: float = Field(0.0, description="Weight in the composite valuation (0-1)")
    assumptions_used: List[ValuationAssumption] = []
    warnings: List[str] = []

class ValuationScenario(BaseModel):
    scenario_name: str
    description: str
    fair_value: float
    assumptions: Dict[str, Any]

class CompositeFairValue(BaseModel):
    range: FairValueRange
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    method_disagreement: bool = False
    disagreement_reason: Optional[str] = None

class ValuationSnapshot(BaseModel):
    symbol: str
    as_of: date
    price_as_of: float
    calculation_version: str = "v1"
    
    methods: List[ValuationMethodOutput]
    composite_fair_value: CompositeFairValue
    scenarios: List[ValuationScenario]
    margin_of_safety: Optional[float] = None  # (Base - Price) / Base
    
    warnings: List[str] = []
