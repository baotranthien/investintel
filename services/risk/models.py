from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import date

class RiskCategory(BaseModel):
    name: str
    score: float = Field(ge=0, le=100) # Higher = more risk
    type: Literal["SYSTEMATIC", "IDIOSYNCRATIC"]
    drivers: List[str]

class MacroSensitivity(BaseModel):
    variable: str
    sensitivity: Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "UNSTABLE"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    description: str

class DrawdownStats(BaseModel):
    max_drawdown: float
    average_drawdown: float
    recovery_time_days: int
    current_drawdown: float

class StockRiskProfile(BaseModel):
    symbol: str
    as_of: date
    
    total_risk_score: float = Field(ge=0, le=100)
    
    market_risk: RiskCategory
    business_risk: RiskCategory
    financial_risk: RiskCategory
    valuation_risk: RiskCategory
    liquidity_risk: RiskCategory
    macro_risk: RiskCategory
    geopolitical_risk: RiskCategory
    event_risk: RiskCategory
    data_risk: RiskCategory
    model_risk: RiskCategory
    
    top_contributors: List[str]
    macro_sensitivities: List[MacroSensitivity]
    drawdown_stats: DrawdownStats
    volatility_annualized: float
    beta: Optional[float]
