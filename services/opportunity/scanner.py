import time
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Asset, IndexMembership, Price
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.opportunity.engine import OpportunityEngine

_SCANNER_CACHE: dict[str, tuple[float, list["ScannerItem"]]] = {}
_CACHE_TTL_SECONDS = 180.0


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


def _item_for_asset(
    session: Session,
    asset: Asset,
    as_of: date,
    horizon: str,
    repository: Optional[FinancialRepository] = None,
    latest_price: Optional[Price] = None,
    macro_data: Any = None,
) -> ScannerItem:
    if latest_price is None:
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

    dataset = repository.get_financial_dataset(asset.symbol, as_of_date=as_of) if repository else None
    has_financials = bool(
        dataset and (dataset.get("income_annual") or dataset.get("income_quarters") or dataset.get("balance_annual"))
    )

    if has_financials and dataset:
        builder = FundamentalSnapshotBuilder(asset.symbol, dataset.get("sector") or asset.sector)
        snap = builder.build_snapshot(
            income_quarters=dataset.get("income_quarters", []),
            income_annual=dataset.get("income_annual", []),
            balance_annual=dataset.get("balance_annual", []),
            cashflow_annual=dataset.get("cashflow_annual", []),
            as_of_date=as_of,
            shares_outstanding=dataset.get("shares_outstanding"),
        )
        roe_val = snap.get("profitability", {}).get("roe", {}).get("value")
        roe = (roe_val / 100.0) if roe_val is not None else None
        ni_yoy_val = snap.get("growth", {}).get("net_income_yoy", {}).get("value")
        profit_growth_yoy = (ni_yoy_val / 100.0) if ni_yoy_val is not None else None
        de_ratio = snap.get("balance_sheet", {}).get("de_ratio", {}).get("value")
        fund_data = {"roe": roe, "profit_growth_yoy": profit_growth_yoy, "de_ratio": de_ratio}

        eps = snap.get("per_share", {}).get("eps_ttm")
        val_data = {}
        val_status = "INSUFFICIENT_DATA"
        if latest_price and latest_price.raw_close and eps and eps > 0:
            pe = latest_price.raw_close / eps
            mos = 0.20 if pe < 12 else (0.10 if pe < 18 else (-0.15 if pe > 25 else 0.0))
            val_data = {"pe": pe, "margin_of_safety": mos}
            val_status = "AVAILABLE"

        engine_result = OpportunityEngine.calculate_medium_term(
            symbol=asset.symbol,
            fundamental_data=fund_data,
            valuation_data=val_data,
            risk_data=None,
            macro_data=macro_data,
            events_data=[],
            as_of=as_of,
        )

        why_now = [
            {"category": ev.category, "description": ev.description, "direction": ev.direction}
            for ev in engine_result.why_now
        ]
        why_not_now = [
            {"category": ev.category, "description": ev.description, "direction": ev.direction}
            for ev in engine_result.why_not_now
        ]

        factor_summary = {"roe": round(roe_val, 2)} if roe_val is not None else None
        factor_status = "AVAILABLE" if roe_val is not None else "INSUFFICIENT_DATA"

        return ScannerItem(
            symbol=asset.symbol,
            name=asset.name,
            asset_type=asset.asset_type,
            sector=asset.sector,
            opportunity_score=engine_result.opportunity_score,
            confidence=engine_result.confidence,
            risk_score=engine_result.risk_score,
            valuation_status=val_status,
            factor_summary=factor_summary,
            factor_status=factor_status,
            why_now=why_now,
            why_not_now=why_not_now,
            what_could_go_wrong=engine_result.what_could_go_wrong,
            data_status="AVAILABLE",
            data_freshness=freshness,
            horizon=horizon,
            model_version=engine_result.model_version,
        )

    # Fallback for assets with no financial statements (withholds scores honestly)
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

    # Pre-fetch latest prices
    latest_prices = session.query(Price).filter(
        Price.status == "VALID",
        Price.observation_date <= as_of,
    ).order_by(Price.observation_date.desc()).all()
    latest_price_map: dict[int, Price] = {}
    for p in latest_prices:
        if p.asset_id not in latest_price_map:
            latest_price_map[p.asset_id] = p

    # Memory cache key
    cache_key = f"{universe}_{sector}_{symbol}_{as_of.isoformat()}_{horizon}"
    now = time.time()
    if cache_key in _SCANNER_CACHE and (now - _SCANNER_CACHE[cache_key][0] < _CACHE_TTL_SECONDS):
        items = list(_SCANNER_CACHE[cache_key][1])
    else:
        with FinancialRepository(session=session) as repository:
            items = [
                _item_for_asset(
                    session=session,
                    asset=asset,
                    as_of=as_of,
                    horizon=horizon,
                    repository=repository,
                    latest_price=latest_price_map.get(asset.id),
                    macro_data=object(),
                )
                for asset in assets
            ]
        _SCANNER_CACHE[cache_key] = (now, list(items))

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