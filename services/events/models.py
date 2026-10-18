from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class EventImpact(BaseModel):
    entity_name: str # e.g. "Oil & Gas Sector" or "FPT"
    entity_type: Literal["SECTOR", "COMPANY", "MACRO_VARIABLE"]
    direction: Literal["POSITIVE", "NEGATIVE", "MIXED", "UNCERTAIN", "NO_MATERIAL_EVIDENCE"]
    magnitude: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    evidence: str

class NewsEvent(BaseModel):
    id: str
    title: str
    description: str
    event_type: str # e.g. Earnings, M&A, Supply Disruption, Geopolitical Escalation
    materiality: Literal["INFORMATIONAL", "RELEVANT", "MATERIAL", "CRITICAL"]
    severity: float = Field(ge=0, le=100)
    sentiment: Literal["POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED", "UNCLEAR"]
    
    countries: List[str] = []
    affected_sectors: List[str] = []
    
    impacts: List[EventImpact] = []
    sources: List[str] = []
    timestamp: datetime
