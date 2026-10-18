from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Asset, IndexMembership, Price
from services.opportunity.engine import OpportunityEngine


ScannerStatus = Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA", "UNSUPPORTED_HORIZON"]


class ScannerItem(BaseModel):
    symbol: str
    name: str
    asset_type: str
    sector: Optional[str] = None
    opportunity_score: Optional[float] = None
    confidence: str = "INSUFFICIENT"
    risk_score: Optional[float] = None
    valuation_status: str = "INSUFFICIENT_DATA"
    factor_summary: Optional[dict[str, float]] = None
    factor_status: str = "INSUFFICIENT_DATA"
    why_now: list[dict[str, Any]] = Field(default_factory=list)
    why_not_now: list[dict[str, Any]] = Field(default_factory=list)
    what_could_go_wrong: list[str] = Field(default_factory=list)
    data_status: str
    data_freshness: dict[str, Any]
    horizon: str
    model_version: str


class OpportunityScannerResponse(BaseModel):
    status: ScannerStatus
    as_of_date: date
    universe: str
    horizon: str
    total_assets: int
    result_count: int
    sector_options: list[str]
    applied_filters: dict[str, Any]
    unavailable_filters: list[str] = Field(default_factory=list)
    results: list[ScannerItem]
    note: Optional[str] = None


def _universe_symbols(session: Session, universe: str, as_of: date) -> Optional[set[str]]:
    if universe == "ALL":
        return None
    memberships = session.query(IndexMembership).filter(
        IndexMembership.index_symbol == universe,
        IndexMembership.start_date <= as_of,
        (IndexMembership.end_date.is_(None)) | (IndexMembership.end_date >= as_of),
    ).all()
    return {
        member.symbol for member in memberships
        if member.published_at is None or member.published_at.date() <= as_of
    }


def _item_for_asset(session: Session, asset: Asset, as_of: date, horizon: str) -> ScannerItem:
    latest_price = session.query(Price).filter(
        Price.asset_id == asset.id,
        Price.observation_date <= as_of,
        Price.status == "VALID",
    ).order_by(Price.observation_date.desc()).first()
    if latest_price is None:
        freshness = {
            "status": "INSUFFICIENT_DATA",
            "as_of_date": None,
            "source": None,
        }
    else:
        age_days = (as_of - latest_price.observation_date).days
        freshness = {
            "status": "STALE" if age_days > 7 else "AVAILABLE",
            "as_of_date": latest_price.observation_date.isoformat(),
            "source": latest_price.source,
        }

    engine_result = OpportunityEngine.calculate_medium_term(
        symbol=asset.symbol,
        fundamental_data={},
        valuation_data={},
        risk_data=None,
        macro_data=None,
        events_data=[],
        as_of=as_of,
    )
    return ScannerItem(
        symbol=asset.symbol,
        name=asset.name,
        asset_type=asset.asset_type,
        sector=asset.sector,
        opportunity_score=None,
        confidence=engine_result.confidence,
        risk_score=None,
        valuation_status="INSUFFICIENT_DATA",
        factor_summary=None,
        factor_status="INSUFFICIENT_DATA",
        why_now=[],
        why_not_now=[{
            "category": "Data",
            "description": "INSUFFICIENT_DATA: chưa có fundamental/valuation inputs canonical để tạo rationale cho tài sản này.",
            "direction": "UNCERTAINTY",
        }],
        what_could_go_wrong=engine_result.what_could_go_wrong,
        data_status="INSUFFICIENT_DATA",
        data_freshness=freshness,
        horizon=horizon,
        model_version=engine_result.model_version,
    )


def build_opportunity_scanner(
    session: Session,
    as_of: date,
    universe: str = "ALL",
    sector: Optional[str] = None,
    horizon: str = "MEDIUM_TERM",
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    risk_max: Optional[float] = None,
    confidence: Optional[str] = None,
    factor: Optional[str] = None,
    valuation_status: Optional[str] = None,
    symbol: Optional[str] = None,
) -> OpportunityScannerResponse:
    sector_options = [
        value for (value,) in session.query(Asset.sector).filter(
            Asset.status == "ACTIVE",
            Asset.asset_type.in_(["STOCK", "ETF", "MUTUAL_FUND"]),
            Asset.sector.is_not(None),
        ).distinct().order_by(Asset.sector).all()
    ]
    universe_symbols = _universe_symbols(session, universe, as_of)
    query = session.query(Asset).filter(
        Asset.status == "ACTIVE",
        Asset.asset_type.in_(["STOCK", "ETF", "MUTUAL_FUND"]),
    )
    if universe_symbols is not None:
        query = query.filter(Asset.symbol.in_(universe_symbols)) if universe_symbols else query.filter(Asset.id == -1)
    if sector:
        query = query.filter(Asset.sector.ilike(sector))
    if symbol:
        query = query.filter(Asset.symbol == symbol.upper())

    assets = query.order_by(Asset.symbol).all()
    items = [_item_for_asset(session, asset, as_of, horizon) for asset in assets]
    unavailable_filters = []
    score_data_available = any(item.opportunity_score is not None for item in items)

    if score_min is not None or score_max is not None:
        items = [
            item for item in items
            if item.opportunity_score is not None
            and (score_min is None or item.opportunity_score >= score_min)
            and (score_max is None or item.opportunity_score <= score_max)
        ]
        if not score_data_available:
            unavailable_filters.append("score: all candidates currently have INSUFFICIENT_DATA")

    if risk_max is not None:
        items = [item for item in items if item.risk_score is not None and item.risk_score <= risk_max]
        unavailable_filters.append("risk: risk inputs are not available for scoring")
    if confidence:
        items = [item for item in items if item.confidence.upper() == confidence.upper()]
    if factor:
        items = [item for item in items if item.factor_summary and factor in item.factor_summary]
        unavailable_filters.append("factor: factor profiles are not connected to canonical inputs")
    if valuation_status:
        valuation_data_available = any(item.valuation_status != "INSUFFICIENT_DATA" for item in items)
        items = [item for item in items if item.valuation_status == valuation_status.upper()]
        if valuation_status.upper() == "AVAILABLE" and not valuation_data_available:
            unavailable_filters.append("valuation: valuation inputs are unavailable for the current candidate set")

    if horizon == "LONG_TERM":
        items = []
        unavailable_filters.append("horizon: the existing OpportunityEngine only calculates medium-term scores")

    response_status: ScannerStatus = (
        "UNSUPPORTED_HORIZON" if horizon == "LONG_TERM" else
        "INSUFFICIENT_DATA" if not items or all(item.data_status == "INSUFFICIENT_DATA" for item in items) else
        "AVAILABLE"
    )
    note = (
        "No opportunity scores are published until canonical fundamental, valuation, factor, risk, and macro inputs are available."
        if response_status != "AVAILABLE" else None
    )
    return OpportunityScannerResponse(
        status=response_status,
        as_of_date=as_of,
        universe=universe,
        horizon=horizon,
        total_assets=len(assets),
        result_count=len(items),
        sector_options=sector_options,
        applied_filters={
            "sector": sector,
            "score_min": score_min,
            "score_max": score_max,
            "risk_max": risk_max,
            "confidence": confidence,
            "factor": factor,
            "valuation_status": valuation_status,
        },
        unavailable_filters=unavailable_filters,
        results=items,
        note=note,
    )