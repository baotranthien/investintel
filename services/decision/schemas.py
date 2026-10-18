from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class DecisionScenario(BaseModel):
    claim_type: Literal["FACT", "MODEL_OUTPUT", "INTERPRETATION", "HYPOTHESIS", "UNCERTAINTY"]
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    assumptions: list[str]
    key_drivers: list[str]
    valuation_range: Optional[str] = None
    risks: list[str]
    confidence: Literal["HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA"]
    uncertainty: Optional[str] = None


class DecisionContextResponse(BaseModel):
    symbol: str
    decision_state: str
    what_changed: list[dict[str, Any]]
    why_now: list[dict[str, Any]]
    why_not_now: list[dict[str, Any]]
    what_would_make_me_wrong: list[dict[str, Any]]
    scenario: dict[str, DecisionScenario]
    evidence: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    explainability: dict[str, dict[str, Any]]
    as_of_date: date
    snapshot: dict[str, Any]


class DecisionSnapshotResponse(BaseModel):
    id: int
    symbol: str
    as_of_date: date
    captured_at: datetime


class PortfolioDecisionResponse(BaseModel):
    portfolio_id: str
    decision_state: str
    allocation_drift: list[dict[str, Any]]
    concentration: dict[str, Any]
    portfolio_changes: list[dict[str, Any]]
    opportunity_changes: list[dict[str, Any]]
    risk_changes: list[dict[str, Any]]
    portfolio_fit_changes: list[dict[str, Any]]
    scenario: dict[str, DecisionScenario]
    evidence: list[dict[str, Any]]
    recommended_actions: list[str]
    as_of_date: date