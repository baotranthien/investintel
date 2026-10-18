from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import date

class FactorScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=100, description="Score from 0 to 100")
    change: Optional[float] = None
    peer_percentile: Optional[float] = None
    market_percentile: Optional[float] = None
    drivers: List[str] = []
    
class FactorProfile(BaseModel):
    symbol: str
    as_of: date
    
    quality: FactorScore
    growth: FactorScore
    value: FactorScore
    dividend: FactorScore
    momentum: FactorScore
    defensive: FactorScore
    cyclical: FactorScore
    
    conflicts: List[str] = []

class FactorScreenerParams(BaseModel):
    min_quality: Optional[float] = None
    min_growth: Optional[float] = None
    min_value: Optional[float] = None
    min_dividend: Optional[float] = None
    min_momentum: Optional[float] = None
    max_cyclical: Optional[float] = None
    sector: Optional[str] = None
