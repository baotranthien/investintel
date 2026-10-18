from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import date

# -------------------------------------------------------------------------
# Macro Data Models
# -------------------------------------------------------------------------

class MacroVariable(BaseModel):
    name: str
    region: Literal["VIETNAM", "US", "CHINA", "GLOBAL"]
    current_value: float
    previous_value: float
    yoy: Optional[float] = None
    mom: Optional[float] = None
    trend: Literal["IMPROVING", "STABLE", "DETERIORATING", "VOLATILE", "UNKNOWN"]
    acceleration: Optional[float] = None
    percentile_historical: Optional[float] = None
    surprise: Optional[float] = None # Actual - Expected
    source: str
    as_of: date

class MacroRegimeState(BaseModel):
    state: Literal["EXPANSION", "CONTRACTION", "STABLE", "VOLATILE", "RECOVERY", "IMPROVING", "DETERIORATING"]
    direction: Literal["UP", "DOWN", "FLAT"]
    strength: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    drivers: List[str]

class MacroDashboard(BaseModel):
    growth: MacroRegimeState
    inflation: MacroRegimeState
    liquidity: MacroRegimeState
    rates: MacroRegimeState
    currency: MacroRegimeState
    credit: MacroRegimeState
    external_demand: MacroRegimeState
    commodities: MacroRegimeState
    
    variables: List[MacroVariable]

# -------------------------------------------------------------------------
# Market Regime Models
# -------------------------------------------------------------------------

class MarketRegime(BaseModel):
    regime: Literal["EXPANSION", "RECOVERY", "NEUTRAL", "INFLATIONARY", "TIGHTENING", "RISK_OFF", "STRESS", "INSUFFICIENT_DATA"]
    confidence: float = Field(ge=0, le=1)
    drivers: List[str]
    risks: List[str]
    changes: List[str]
    as_of: date
    model_version: str = "v1"
    supporting_signals: List[str] = Field(default_factory=list)
    conflicting_signals: List[str] = Field(default_factory=list)
    data_coverage: Optional[float] = None
    historical_context: List[str] = Field(default_factory=list)
    momentum_20d: Optional[float] = None
    advancing: Optional[int] = None
    declining: Optional[int] = None
    unchanged: Optional[int] = None
    breadth_percent: Optional[float] = None

class MarketBreadth(BaseModel):
    advancing: int
    declining: int
    unchanged: int
    new_highs: int
    new_lows: int
    above_ma20_pct: float
    above_ma50_pct: float
    above_ma200_pct: float
    trend: Literal["IMPROVING", "DETERIORATING", "NEUTRAL"]
