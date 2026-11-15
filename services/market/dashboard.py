from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Asset, DataLineage, DataSource, EventRecord, MacroObservation, MarketFlowDaily, Price
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


def _price_metrics_batch(session: Session, symbols: list[str], as_of: date) -> dict[str, MarketMetric]:
    if not symbols:
        return {}
    assets = {
        asset.symbol: asset
        for asset in session.query(Asset).filter(Asset.symbol.in_(symbols)).all()
    }
    asset_ids = [asset.id for asset in assets.values()]
    prices_by_aid: dict[int, Price] = {}
    lineages_by_pid: dict[str, DataLineage] = {}

    if asset_ids:
        ranked_prices = (
            session.query(
                Price.id.label("price_id"),
                func.row_number()
                .over(
                    partition_by=Price.asset_id,
                    order_by=Price.observation_date.desc(),
                )
                .label("rn"),
            )
            .filter(
                Price.asset_id.in_(asset_ids),
                Price.status == "VALID",
                Price.observation_date <= as_of,
            )
            .subquery()
        )
        price_rows = (
            session.query(Price)
            .join(ranked_prices, Price.id == ranked_prices.c.price_id)
            .filter(ranked_prices.c.rn == 1)
            .all()
        )
        prices_by_aid = {pr.asset_id: pr for pr in price_rows}

        price_id_strs = [str(pr.id) for pr in price_rows]
        if price_id_strs:
            ranked_lineage = (
                session.query(
                    DataLineage.id.label("lin_id"),
                    func.row_number()
                    .over(
                        partition_by=DataLineage.record_id,
                        order_by=DataLineage.created_at.desc(),
                    )
                    .label("rn"),
                )
                .filter(
                    DataLineage.record_table == "prices",
                    DataLineage.record_id.in_(price_id_strs),
                )
                .subquery()
            )
            lineage_rows = (
                session.query(DataLineage)
                .join(ranked_lineage, DataLineage.id == ranked_lineage.c.lin_id)
                .filter(ranked_lineage.c.rn == 1)
                .all()
            )
            lineages_by_pid = {lin.record_id: lin for lin in lineage_rows}

    metrics: dict[str, MarketMetric] = {}
    for symbol in symbols:
        asset = assets.get(symbol)
        if asset is None:
            metrics[symbol] = MarketMetric(
                status="INSUFFICIENT_DATA",
                note="Index is not registered as a canonical asset.",
            )
            continue
        price = prices_by_aid.get(asset.id)
        if price is None:
            metrics[symbol] = MarketMetric(
                status="INSUFFICIENT_DATA",
                note="No valid canonical index price is available.",
            )
            continue
        lineage = lineages_by_pid.get(str(price.id))
        observation_status = _freshness_status(price.observation_date, as_of)
        source = price.source or (lineage.raw_source if lineage else None)
        data_origin = "SEEDED_OR_UNTRACED"
        if lineage:
            data_origin = "STATIC_OR_SEEDED" if (price.source or "").upper() in {"HOSE_CSV", "MARKETDATACSV"} else "LINEAGED_INGESTION"
        metrics[symbol] = MarketMetric(
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
    return metrics


def _price_metric(session: Session, symbol: str, as_of: date) -> MarketMetric:
    return _price_metrics_batch(session, [symbol], as_of)[symbol]


def build_market_dashboard(session: Session, as_of: date) -> MarketDashboard:
    index_names = {
        "VN30": "VN30 Index",
        "VN100": "VN100 Index",
        "VN300": "VN300 Index",
    }
    index_metrics = _price_metrics_batch(session, list(index_names.keys()), as_of)
    indexes = [
        MarketIndexQuote(symbol=symbol, name=name, metric=index_metrics[symbol])
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
    try:
        latest_flow_date = (
            session.query(func.max(MarketFlowDaily.observation_date))
            .filter(MarketFlowDaily.observation_date <= as_of)
            .scalar()
        )
        if latest_flow_date is not None:
            flow_rows = (
                session.query(MarketFlowDaily)
                .filter(MarketFlowDaily.observation_date == latest_flow_date)
                .all()
            )
            if flow_rows:
                total_buy = sum(float(r.foreign_buy_value or 0.0) for r in flow_rows)
                total_sell = sum(float(r.foreign_sell_value or 0.0) for r in flow_rows)
                total_net_vnd = sum(float(r.foreign_net_value or 0.0) for r in flow_rows)
                ranked_buy = sorted(
                    ((r.symbol, round(float(r.foreign_net_value or 0.0) / 1e9, 2)) for r in flow_rows if (r.foreign_net_value or 0.0) > 0),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
                ranked_sell = sorted(
                    ((r.symbol, round(float(r.foreign_net_value or 0.0) / 1e9, 2)) for r in flow_rows if (r.foreign_net_value or 0.0) < 0),
                    key=lambda x: x[1],
                )[:5]
                foreign_flow = MarketMetric(
                    value=round(total_net_vnd / 1e9, 2),
                    unit="BILLION_VND",
                    as_of_date=latest_flow_date,
                    source=flow_rows[0].source or "VPS_FOREIGN_FLOW",
                    status="AVAILABLE",
                    data_origin="CANONICAL_DATABASE",
                    note=f"Net foreign flow across {len(flow_rows)} covered stocks on {latest_flow_date.isoformat()}: {total_net_vnd / 1e9:+.2f}B VND.",
                    details={
                        "buy_billion_vnd": round(total_buy / 1e9, 2),
                        "sell_billion_vnd": round(total_sell / 1e9, 2),
                        "net_billion_vnd": round(total_net_vnd / 1e9, 2),
                        "stocks_covered": len(flow_rows),
                        "top_net_buy": [{"symbol": s, "net_billion_vnd": v} for s, v in ranked_buy],
                        "top_net_sell": [{"symbol": s, "net_billion_vnd": v} for s, v in ranked_sell],
                    },
                )
        else:
            macro_ff = (
                session.query(MacroObservation)
                .filter(
                    MacroObservation.series_id == "HOSE_FOREIGN_NET_FLOW",
                    MacroObservation.observation_date <= as_of,
                    MacroObservation.anomaly.is_(False),
                )
                .order_by(MacroObservation.observation_date.desc())
                .first()
            )
            if macro_ff and macro_ff.value is not None:
                foreign_flow = MarketMetric(
                    value=round(float(macro_ff.value), 2),
                    unit="BILLION_VND",
                    as_of_date=macro_ff.observation_date,
                    source="HOSE_FOREIGN_NET_FLOW",
                    status="AVAILABLE",
                    data_origin="CANONICAL_DATABASE",
                    note=f"HOSE aggregate net foreign flow on {macro_ff.observation_date.isoformat()}: {float(macro_ff.value):+.2f}B VND.",
                )
    except Exception:
        pass

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