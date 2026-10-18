from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import date

class SignalEvidence(BaseModel):
    category: str
    description: str
    direction: Literal["POSITIVE", "NEGATIVE", "MIXED"]

class OpportunityScore(BaseModel):
    symbol: str
    as_of: date
    horizon: Literal["MEDIUM_TERM", "LONG_TERM"]
    
    opportunity_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    confidence: Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]
    
    # Classifications
    opportunity_types: List[str] # e.g. ["Quality Opportunity", "Catalyst Opportunity"]
    is_candidate: bool # Long-Term Candidate or Medium-Term Candidate
    
    # Explanations
    why_now: List[SignalEvidence]
    why_not_now: List[SignalEvidence]
    what_could_go_wrong: List[str]
    
    # Signals
    fundamental_signal: Literal["POSITIVE", "NEGATIVE", "MIXED"]
    valuation_signal: Literal["POSITIVE", "NEGATIVE", "MIXED"]
    technical_signal: Literal["POSITIVE", "NEGATIVE", "MIXED"]
    macro_signal: Literal["POSITIVE", "NEGATIVE", "MIXED"]
    
    signal_conflict: bool = False
    
    model_version: str = "opportunity_v1"
