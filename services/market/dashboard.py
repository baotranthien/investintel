from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Asset, DataLineage, DataSource, EventRecord, Price
from services.macro.engine import MarketRegimeEngine


MetricStatus = Literal["AVAILABLE", "STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"]


class MarketMetric(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    as_of_date: Optional[date] = None
    published_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    source: Optional[str] = None
    status: MetricStatus
    data_origin: Optional[str] = None
    note: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class MarketIndexQuote(BaseModel):
    symbol: str
    name: str
    metric: MarketMetric


class MarketEventItem(BaseModel):
    id: str
    title: str
    event_type: str
    materiality: str
    severity: float
    published_at: Optional[datetime]
    source: Optional[str]
    source_documents: list[str] = Field(default_factory=list)


class MarketRegimeSummary(BaseModel):
    regime: Literal[
        "EXPANSION", "RECOVERY", "NEUTRAL", "INFLATIONARY", "TIGHTENING",
        "RISK_OFF", "STRESS", "INSUFFICIENT_DATA",
    ]
    confidence: float
    drivers: list[str]
    risks: list[str]
    changes: list[str]
    as_of: Optional[date] = None
    model_version: str
    supporting_signals: list[str] = Field(default_factory=list)
    conflicting_signals: list[str] = Field(default_factory=list)
    data_coverage: Optional[float] = None
    historical_context: list[str] = Field(default_factory=list)
    momentum_20d: Optional[float] = None
    advancing: Optional[int] = None
    declining: Optional[int] = None
    unchanged: Optional[int] = None
    breadth_percent: Optional[float] = None
    benchmark: str = "VN100"
    total_eligible: Optional[int] = None
    covered_members: Optional[int] = None
    denominator_rule: Optional[str] = None


class MarketDashboard(BaseModel):
    status: Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"]
    as_of_date: date
    indexes: list[MarketIndexQuote]
    market_regime: MarketRegimeSummary
    breadth: MarketMetric
    momentum: MarketMetric
    liquidity: MarketMetric
    foreign_flow: MarketMetric
    events_status: MetricStatus
    major_events: list[MarketEventItem]


def _freshness_status(observation_date: date, as_of: date) -> MetricStatus:
    return "STALE" if (as_of - observation_date).days > 7 else "AVAILABLE"


def _price_metric(session: Session, symbol: str, as_of: date) -> MarketMetric:
    asset = session.query(Asset).filter(Asset.symbol == symbol).first()
    if asset is None:
        return MarketMetric(status="INSUFFICIENT_DATA", note="Index is not registered as a canonical asset.")

    price = session.query(Price).filter(
        Price.asset_id == asset.id,
        Price.status == "VALID",
        Price.observation_date <= as_of,
    ).order_by(Price.observation_date.desc()).first()
    if price is None:
        return MarketMetric(status="INSUFFICIENT_DATA", note="No valid canonical index price is available.")

    lineage = session.query(DataLineage).filter(
        DataLineage.record_table == "prices",
        DataLineage.record_id == str(price.id),
    ).order_by(DataLineage.created_at.desc()).first()
    observation_status = _freshness_status(price.observation_date, as_of)
    source = price.source or (lineage.raw_source if lineage else None)
    data_origin = "SEEDED_OR_UNTRACED"
    if lineage:
        data_origin = "STATIC_OR_SEEDED" if (price.source or "").upper() in {"HOSE_CSV", "MARKETDATACSV"} else "LINEAGED_INGESTION"
    return MarketMetric(
        value=price.adjusted_close if price.adjusted_close is not None else price.raw_close,
        unit="index_points",
        as_of_date=price.observation_date,
        retrieved_at=lineage.retrieved_at if lineage else price.created_at,
        source=source,
        status=observation_status,
        data_origin=data_origin,
        note="Canonical database record; source may be seeded or static. See provenance.",
        details={"lineage_url": lineage.url if lineage else None},
    )


def build_market_dashboard(session: Session, as_of: date) -> MarketDashboard:
    index_names = {
        "VN30": "VN30 Index",
        "VN100": "VN100 Index",
        "VN300": "VN300 Index",
    }
    indexes = [
        MarketIndexQuote(symbol=symbol, name=name, metric=_price_metric(session, symbol, as_of))
        for symbol, name in index_names.items()
    ]

    regime = MarketRegimeEngine.determine_regime(as_of, session=session, benchmark="VN100")
    if regime.regime == "INSUFFICIENT_DATA":
        vn30_regime = MarketRegimeEngine.determine_regime(as_of, session=session, benchmark="VN30")
        if vn30_regime.regime != "INSUFFICIENT_DATA":
            regime = vn30_regime

    benchmark_date = regime.as_of
    benchmark_metric = next((item.metric for item in indexes if item.symbol == regime.benchmark), None)
    inherited_status: MetricStatus = (
        benchmark_metric.status if benchmark_metric and benchmark_metric.value is not None
        else "INSUFFICIENT_DATA"
    )

    breadth_details = {
        "benchmark": regime.benchmark,
        "session_date": str(benchmark_date) if benchmark_date else None,
        "advancing": regime.advancing,
        "declining": regime.declining,
        "unchanged": regime.unchanged,
        "covered_members": regime.covered_members,
        "total_eligible": regime.total_eligible,
        "coverage": regime.data_coverage,
        "coverage_percent": round((regime.data_coverage or 0.0) * 100.0, 1),
        "denominator_rule": regime.denominator_rule,
        "threshold": ">= 50% constituent coverage on same session date required for AVAILABLE",
    }

    if regime.breadth_percent is None or regime.regime == "INSUFFICIENT_DATA":
        breadth = MarketMetric(
            status="INSUFFICIENT_DATA",
            as_of_date=benchmark_date,
            source=f"Canonical {regime.benchmark} membership and prices",
            note=(
                regime.drivers[0] if regime.drivers
                else f"INSUFFICIENT_DATA: Độ rộng thị trường {regime.benchmark} yêu cầu tối thiểu 50% mã thành phần có giá hợp lệ cùng phiên."
            ),
            details=breadth_details,
        )
    else:
        breadth = MarketMetric(
            value=regime.breadth_percent,
            unit="percent_advancing",
            as_of_date=benchmark_date,
            source=f"Canonical {regime.benchmark} membership and prices",
            status=inherited_status,
            details=breadth_details,
        )

    if regime.momentum_20d is None:
        momentum = MarketMetric(
            status="INSUFFICIENT_DATA",
            as_of_date=benchmark_date,
            source=f"Canonical {regime.benchmark} index prices",
            note=f"20-session momentum requires 21 valid {regime.benchmark} index observations.",
        )
    else:
        momentum = MarketMetric(
            value=round(regime.momentum_20d * 100.0, 2),
            unit="percent_20_sessions",
            as_of_date=benchmark_date,
            source=f"Canonical {regime.benchmark} index prices",
            status=inherited_status,
            details={
                "benchmark": regime.benchmark,
                "session_date": str(benchmark_date) if benchmark_date else None,
                "window_sessions": 20,
            },
        )

    if benchmark_date is None:
        liquidity = MarketMetric(
            status="INSUFFICIENT_DATA",
            source="Canonical prices.turnover",
            note="No market benchmark date is available for turnover aggregation.",
        )
    else:
        turnover_rows = session.query(Price).join(Asset, Price.asset_id == Asset.id).filter(
            Asset.exchange == "HOSE",
            Asset.asset_type.in_(["STOCK", "ETF"]),
            Price.observation_date == benchmark_date,
            Price.status == "VALID",
            Price.turnover.is_not(None),
        ).all()
        total_turnover = sum(row.turnover or 0.0 for row in turnover_rows)
        liquidity = MarketMetric(
            value=total_turnover if turnover_rows else None,
            unit="VND",
            as_of_date=benchmark_date,
            source="Canonical prices.turnover",
            status=inherited_status if turnover_rows else "INSUFFICIENT_DATA",
            note=None if turnover_rows else "Canonical turnover values are not populated for this date.",
            details={"assets_with_turnover": len(turnover_rows)},
        )

    foreign_flow = MarketMetric(
        status="NOT_CONFIGURED",
        source=None,
        note="No foreign-flow dataset or provider is registered in the current schema.",
    )

    event_rows = session.query(EventRecord, DataSource).outerjoin(
        DataSource, EventRecord.source_id == DataSource.id
    ).filter(
        EventRecord.materiality.in_(["MATERIAL", "CRITICAL"]),
        EventRecord.published_at.is_not(None),
        EventRecord.published_at <= datetime.combine(as_of, datetime.max.time(), tzinfo=timezone.utc),
    ).order_by(EventRecord.published_at.desc()).limit(8).all()
    def _format_source_doc(doc: Any) -> str:
        if isinstance(doc, dict):
            name = doc.get("name") or doc.get("title")
            url = doc.get("url") or doc.get("link")
            if name and url:
                return f"{name} ({url})"
            return str(url or name or doc)
        return str(doc)

    major_events = [
        MarketEventItem(
            id=event.id,
            title=event.title,
            event_type=event.event_type,
            materiality=event.materiality,
            severity=event.severity or 0.0,
            published_at=event.published_at,
            source=source.name if source else None,
            source_documents=[_format_source_doc(doc) for doc in (event.sources or [])],
        )
        for event, source in event_rows
    ]
    events_status: MetricStatus = "AVAILABLE" if major_events else "INSUFFICIENT_DATA"

    available_parts = sum(
        metric.value is not None and metric.status == "AVAILABLE"
        for metric in (breadth, momentum, liquidity)
    )
    status: Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"] = (
        "INSUFFICIENT_DATA" if available_parts == 0 else
        "AVAILABLE" if available_parts == 3 and regime.regime != "INSUFFICIENT_DATA" else "PARTIAL"
    )
    return MarketDashboard(
        status=status,
        as_of_date=as_of,
        indexes=indexes,
        market_regime=MarketRegimeSummary.model_validate(regime.model_dump()),
        breadth=breadth,
        momentum=momentum,
        liquidity=liquidity,
        foreign_flow=foreign_flow,
        events_status=events_status,
        major_events=major_events,
    )