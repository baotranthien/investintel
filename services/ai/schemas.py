from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


AIToolName = Literal[
    "asset", "fundamentals", "valuation", "factors", "risk", "macro", "regime",
    "events", "opportunity", "portfolio", "watchlist", "historical_snapshot",
    "evidence", "document_retrieval",
]
ClaimType = Literal["FACT", "MODEL_OUTPUT", "INTERPRETATION", "HYPOTHESIS", "UNCERTAINTY"]


class AIChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    symbol: str | None = Field(default=None, min_length=1, max_length=20)
    as_of_date: date | None = None
    active_tools: list[str] | None = None
    tool_names: list[AIToolName] = Field(default_factory=lambda: [
        "asset", "fundamentals", "valuation", "factors", "risk", "macro", "regime",
        "events", "opportunity", "portfolio", "watchlist", "historical_snapshot",
        "evidence", "document_retrieval",
    ])

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class AIClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: ClaimType
    text: str = Field(min_length=1, max_length=2000)
    citation_ids: list[str] = Field(default_factory=list)


class AIAnswerDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=5000)
    claims: list[AIClaim] = Field(..., min_length=1, max_length=30)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)


class AICitation(BaseModel):
    id: str
    claim_type: ClaimType
    responsible_module: str
    metric: str | None = None
    value: Any = None
    unit: str | None = None
    source: str | None = None
    source_url: str | None = None
    observation_date: str | None = None
    publication_date: str | None = None
    retrieved_at: str | None = None
    data_origin: str | None = None
    freshness: str | None = None
    note: str | None = None


class AIChatResponse(BaseModel):
    status: Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"]
    symbol: str | None = None
    resolved_symbol: str | None = None
    as_of_date: date
    prompt_version: str
    model: str | None = None
    answer: str
    claims: list[AIClaim]
    citations: list[AICitation]
    uncertainty: list[str]
    tools_used: list[str]
    usage: dict[str, Any] = Field(default_factory=dict)


class AnalystBriefRead(BaseModel):
    id: int
    brief_type: str
    as_of_date: date
    status: str
    payload: dict[str, Any]
    idempotency_key: str
    created_at: datetime


class AnalystBriefListResponse(BaseModel):
    total: int
    items: list[AnalystBriefRead]


class AnalystAlertRead(BaseModel):
    id: int
    alert_id: str
    symbol: str | None = None
    kind: str
    status: str
    payload: dict[str, Any]
    created_at: datetime
    resolved_at: datetime | None = None


class AnalystAlertListResponse(BaseModel):
    total: int
    items: list[AnalystAlertRead]


class AnalystJobRead(BaseModel):
    id: int
    job_key: str
    job_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    result: Any = None
    error: str | None = None


class AnalystJobListResponse(BaseModel):
    total: int
    items: list[AnalystJobRead]