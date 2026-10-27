from datetime import date, datetime, time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Asset, CorporateAction, DataLineage, DataSource, EventRecord, Price
from services.fundamentals.engine import TTMEngine
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.sector_models import get_sector_model
from services.fundamentals.snapshot import FundamentalSnapshotBuilder


WorkspaceStatus = Literal["AVAILABLE", "PARTIAL", "INSUFFICIENT_DATA"]
EvidenceStatus = Literal["AVAILABLE", "STALE", "INSUFFICIENT_DATA", "NOT_MEANINGFUL"]
ClaimType = Literal["FACT", "MODEL_OUTPUT", "INTERPRETATION", "HYPOTHESIS", "UNCERTAINTY"]


class Evidence(BaseModel):
    claim_type: ClaimType
    source: Optional[str] = None
    source_url: Optional[str] = None
    observation_date: Optional[date] = None
    publication_date: Optional[date] = None
    retrieved_at: Optional[datetime] = None
    data_origin: Optional[str] = None
    note: Optional[str] = None


class WorkspaceMetric(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    status: EvidenceStatus
    period: Optional[str] = None
    calculation: Optional[str] = None
    verification_level: Optional[str] = None
    evidence: Evidence


class TimelineItem(BaseModel):
    id: str
    date: Optional[str] = None
    kind: str
    title: str
    before: Optional[str] = None
    current: Optional[str] = None
    status: EvidenceStatus
    evidence: Evidence


class ResearchWorkspace(BaseModel):
    as_of_date: date
    status: WorkspaceStatus
    asset: dict[str, Any]
    price: dict[str, Any]
    opportunity: dict[str, Any]
    fundamentals: dict[str, Any]
    sector_analysis: dict[str, Any]
    valuation: dict[str, Any]
    factors: dict[str, Any]
    risk: dict[str, Any]
    macro_sensitivity: dict[str, Any]
    events: list[dict[str, Any]]
    timeline: list[TimelineItem]
    research_summary: dict[str, list[dict[str, Any]]]
    data_quality: dict[str, Any]


def _lineage_for(session: Session, table: str, record_id: Any) -> Optional[DataLineage]:
    return session.query(DataLineage).filter(
        DataLineage.record_table == table,
        DataLineage.record_id == str(record_id),
    ).order_by(DataLineage.created_at.desc()).first()


def _event_matches(event: EventRecord, symbol: str, sector: Optional[str]) -> bool:
    impacts = event.impacts or []
    if any((impact.get("entity_name") or "").upper() == symbol for impact in impacts):
        return True
    if symbol in f"{event.title} {event.description}".upper():
        return True
    sectors = [value.upper() for value in (event.affected_sectors or [])]
    countries = [value.upper() for value in (event.countries or [])]
    return bool((sector and sector.upper() in sectors) or "GLOBAL" in countries or "ALL" in sectors)


def _metric_from_snapshot(
    value: Optional[float],
    *,
    unit: Optional[str],
    period: Optional[str],
    metric: Optional[dict[str, Any]],
    source: Optional[str],
    source_date: Optional[date],
    publication_date: Optional[date],
    data_origin: Optional[str],
    verification_level: Optional[str] = None,
) -> WorkspaceMetric:
    metric = metric or {}
    metric_status = metric.get("data_status")
    if value is None:
        status: EvidenceStatus = "NOT_MEANINGFUL" if metric_status in {
            "NOT_MEANINGFUL", "NEGATIVE_DENOMINATOR", "DENOMINATOR_ZERO"
        } else "INSUFFICIENT_DATA"
        v_level = None
    else:
        status = "AVAILABLE"
        if verification_level:
            v_level = verification_level
        elif metric.get("value_status") == "DERIVED":
            v_level = "MATHEMATICALLY_CALCULATED"
        else:
            v_level = "DATA_PRESENT"
    return WorkspaceMetric(
        value=value,
        unit=unit or metric.get("unit"),
        status=status,
        period=period or metric.get("period"),
        calculation=metric.get("calculation_version"),
        verification_level=v_level,
        evidence=Evidence(
            claim_type="MODEL_OUTPUT" if metric.get("value_status") == "DERIVED" else "FACT",
            source=source,
            observation_date=source_date,
            publication_date=publication_date,
            data_origin=data_origin,
            note=metric.get("not_meaningful_reason"),
        ),
    )


def build_research_workspace(
    session: Session,
    symbol: str,
    as_of: Optional[date] = None,
) -> Optional[ResearchWorkspace]:
    as_of = as_of or date.today()
    from services.universe.registry import UniverseRegistry
    resolved = UniverseRegistry.resolve_instrument(session, symbol)
    normalized_symbol = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(symbol) or symbol.upper())
    asset = session.query(Asset).filter(Asset.symbol == normalized_symbol).first()
    if asset is None:
        return None

    price = session.query(Price).filter(
        Price.asset_id == asset.id,
        Price.status == "VALID",
        Price.observation_date <= as_of,
    ).order_by(Price.observation_date.desc()).first()
    price_lineage = _lineage_for(session, "prices", price.id) if price else None
    price_source = price.source if price else None
    price_origin = "INSUFFICIENT_DATA"
    price_status: EvidenceStatus = "INSUFFICIENT_DATA"
    if price:
        price_origin = "SEEDED_OR_UNTRACED"
        if price_lineage:
            price_origin = "STATIC_OR_SEEDED" if (price.source or "").upper() in {"HOSE_CSV", "MARKETDATACSV"} else "LINEAGED_INGESTION"
        price_status = "STALE" if (as_of - price.observation_date).days > 7 else "AVAILABLE"

    with FinancialRepository(session=session) as repository:
        dataset = repository.get_financial_dataset(normalized_symbol, as_of_date=as_of)

    profile = dataset["profile"] if dataset else {
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "exchange": asset.exchange,
        "sector": asset.sector or "GENERAL",
        "currency": asset.currency or "VND",
        "status": asset.status,
    }
    sector = (dataset["sector"] if dataset else asset.sector) or "GENERAL"
    dataset = dataset or {
        "symbol": normalized_symbol,
        "sector": sector,
        "income_annual": [],
        "income_quarters": [],
        "balance_annual": [],
        "cashflow_annual": [],
        "shares_outstanding": None,
        "sources": [],
        "latest_publication_date": None,
    }
    source_names = dataset.get("sources", [])
    primary_source = source_names[0] if source_names else None
    latest_publication = date.fromisoformat(dataset["latest_publication_date"]) if dataset.get("latest_publication_date") else None

    has_financials = bool(dataset["income_annual"] or dataset["income_quarters"] or dataset["balance_annual"])
    if has_financials:
        snapshot = FundamentalSnapshotBuilder(normalized_symbol, sector).build_snapshot(
            income_quarters=dataset["income_quarters"],
            income_annual=dataset["income_annual"],
            balance_annual=dataset["balance_annual"],
            cashflow_annual=dataset["cashflow_annual"],
            as_of_date=as_of,
            shares_outstanding=dataset.get("shares_outstanding"),
            sources=source_names,
        )
    else:
        snapshot = {}

    snapshot_source_date = None
    if snapshot.get("as_of"):
        try:
            snapshot_source_date = date.fromisoformat(str(snapshot["as_of"]))
        except ValueError:
            snapshot_source_date = None

    metric_groups = {
        "growth": snapshot.get("growth", {}),
        "profitability": snapshot.get("profitability", {}),
        "balance_sheet": snapshot.get("balance_sheet", {}),
        "cash_flow": snapshot.get("cash_flow", {}),
        "per_share": snapshot.get("per_share", {}),
        "efficiency": snapshot.get("efficiency", {}),
    }
    fundamentals_metrics: dict[str, WorkspaceMetric] = {}
    metric_labels = {
        "revenue_yoy": ("growth", "%"), "net_income_yoy": ("growth", "%"),
        "eps_yoy": ("growth", "%"), "revenue_cagr_3y": ("growth", "%"),
        "revenue_cagr_5y": ("growth", "%"), "eps_cagr_3y": ("growth", "%"),
        "gross_margin": ("profitability", "%"), "ebit_margin": ("profitability", "%"),
        "ebitda_margin": ("profitability", "%"), "net_margin": ("profitability", "%"),
        "roe": ("profitability", "%"), "roa": ("profitability", "%"),
        "roic": ("profitability", "%"), "de_ratio": ("balance_sheet", "ratio"),
        "net_debt_ebitda": ("balance_sheet", "ratio"), "debt_to_assets": ("balance_sheet", "%"),
        "current_ratio": ("balance_sheet", "ratio"), "quick_ratio": ("balance_sheet", "ratio"),
        "interest_coverage": ("balance_sheet", "ratio"), "cfo_to_ni": ("cash_flow", "ratio"),
        "fcf_to_ni": ("cash_flow", "ratio"), "dso": ("efficiency", "days"),
        "dio": ("efficiency", "days"), "dpo": ("efficiency", "days"),
        "ccc": ("efficiency", "days"),
    }
    for metric_id, (group, unit) in metric_labels.items():
        raw_metric = metric_groups[group].get(metric_id)
        if isinstance(raw_metric, dict):
            fundamentals_metrics[metric_id] = _metric_from_snapshot(
                raw_metric.get("value"), unit=unit, period=raw_metric.get("period"),
                metric=raw_metric, source=primary_source, source_date=snapshot_source_date,
                publication_date=latest_publication, data_origin="CANONICAL_FINANCIAL_STATEMENTS",
            )

    ttm_income = (
        TTMEngine.compute_ttm_income(dataset["income_quarters"])
        if snapshot.get("period") == "TTM" else {}
    )
    for metric_id, source_group, raw_key, unit in (
        ("eps_ttm", "per_share", "eps_ttm", "VND/share"),
        ("bvps", "per_share", "bvps", "VND/share"),
        ("revenue", "income", "revenue", "BILLION_VND"),
        ("net_income", "income", "net_income", "BILLION_VND"),
        ("operating_income", "income", "operating_income", "BILLION_VND"),
        ("cash", "balance_sheet", "cash", "BILLION_VND"),
        ("total_assets", "balance_sheet", "total_assets", "BILLION_VND"),
        ("total_liabilities", "balance_sheet", "total_liabilities", "BILLION_VND"),
        ("total_equity", "balance_sheet", "total_equity", "BILLION_VND"),
        ("cfo", "cash_flow", "cfo", "BILLION_VND"),
        ("fcf", "cash_flow", "fcf", "BILLION_VND"),
    ):
        period = snapshot.get("period") or "ANNUAL"
        if source_group == "income":
            value = (
                ttm_income.get(raw_key)
                if snapshot.get("period") == "TTM"
                else (dataset["income_annual"][-1].get(raw_key) if dataset["income_annual"] else None)
            )
        else:
            value = snapshot.get(source_group, {}).get(raw_key)
        if metric_id == "eps_ttm" and snapshot.get("period") != "TTM":
            value = None
        fundamentals_metrics[metric_id] = _metric_from_snapshot(
            value, unit=unit, period=period, metric=None, source=primary_source,
            source_date=snapshot_source_date, publication_date=latest_publication,
            data_origin="CANONICAL_FINANCIAL_STATEMENTS",
        )

    history_rows = []
    annual_rows = dataset["income_annual"]
    history_source_rows = annual_rows or dataset["income_quarters"]
    for row in history_source_rows:
        history_rows.append({
            "period_end": row.get("fiscal_period_end"),
            "publication_date": row.get("publication_date"),
            "fiscal_year": row.get("fiscal_year"),
            "fiscal_quarter": row.get("fiscal_quarter"),
            "period_type": row.get("period_type"),
            "revenue": row.get("revenue"),
            "earnings": row.get("net_income_parent") if row.get("net_income_parent") is not None else row.get("net_income"),
            "eps": row.get("eps_basic"),
            "source": primary_source,
        })

    sector_model = get_sector_model(normalized_symbol, sector)
    sector_snapshot = snapshot.get("sector_metrics", {})
    raw_sector_metrics = sector_snapshot.get("metrics", {})
    sector_metrics: dict[str, WorkspaceMetric] = {}
    for metric_id in sector_model.get_applicable_metrics():
        raw_metric = raw_sector_metrics.get(metric_id)
        if raw_metric is None:
            for group in metric_groups.values():
                if isinstance(group.get(metric_id), dict):
                    raw_metric = group[metric_id]
                    break
        sector_metrics[metric_id] = _metric_from_snapshot(
            raw_metric.get("value") if isinstance(raw_metric, dict) else None,
            unit=raw_metric.get("unit") if isinstance(raw_metric, dict) else None,
            period=raw_metric.get("period") if isinstance(raw_metric, dict) else snapshot.get("period"),
            metric=raw_metric if isinstance(raw_metric, dict) else None,
            source=primary_source,
            source_date=snapshot_source_date,
            publication_date=latest_publication,
            data_origin="CANONICAL_FINANCIAL_STATEMENTS" if has_financials else None,
        )

    events_query = session.query(EventRecord, DataSource).outerjoin(
        DataSource, EventRecord.source_id == DataSource.id
    ).filter(EventRecord.published_at.is_not(None), EventRecord.published_at <= datetime.combine(as_of, time.max))
    event_records = events_query.order_by(EventRecord.published_at.desc()).limit(200).all()
    events: list[dict[str, Any]] = []
    timeline: list[TimelineItem] = []
    for event, source in event_records:
        if not _event_matches(event, normalized_symbol, sector):
            continue
        event_source = source.name if source else None
        documents = event.sources or []
        claim_type: ClaimType = "FACT" if (event_source or documents) else "UNCERTAINTY"
        events.append({
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "materiality": event.materiality,
            "severity": event.severity,
            "published_at": event.published_at,
            "source": event_source,
            "source_documents": documents,
            "evidence": Evidence(
                claim_type=claim_type,
                source=event_source,
                publication_date=event.published_at.date() if event.published_at else None,
                retrieved_at=event.retrieved_at,
                data_origin="CANONICAL_EVENT_RECORD",
                note=None if claim_type == "FACT" else "No source link is associated with this event record.",
            ).model_dump(),
        })
        timeline.append(TimelineItem(
            id=f"event-{event.id}",
            date=event.published_at.date().isoformat() if event.published_at else None,
            kind="EVENT",
            title=event.title,
            status="AVAILABLE" if claim_type == "FACT" else "INSUFFICIENT_DATA",
            evidence=Evidence(
                claim_type=claim_type,
                source=event_source,
                publication_date=event.published_at.date() if event.published_at else None,
                retrieved_at=event.retrieved_at,
                data_origin="CANONICAL_EVENT_RECORD",
            ),
        ))

    actions = session.query(CorporateAction).filter(
        CorporateAction.symbol == normalized_symbol,
        CorporateAction.action_date <= as_of,
    ).order_by(CorporateAction.action_date.desc()).all()
    for action in actions:
        timeline.append(TimelineItem(
            id=f"action-{action.id}",
            date=action.action_date.isoformat(),
            kind="CORPORATE_ACTION",
            title=action.action_type,
            current=(str(action.value) if action.value is not None else str(action.ratio) if action.ratio is not None else None),
            status="AVAILABLE" if action.source else "INSUFFICIENT_DATA",
            evidence=Evidence(
                claim_type="FACT" if action.source else "UNCERTAINTY",
                source=action.source,
                observation_date=action.action_date,
                publication_date=action.ex_date,
                data_origin="CANONICAL_CORPORATE_ACTION",
                note=action.notes,
            ),
        ))

    if len(annual_rows) >= 2:
        previous, current = annual_rows[-2], annual_rows[-1]
        for field, label in (("revenue", "Revenue"), ("net_income_parent", "Earnings"), ("eps_basic", "EPS")):
            old_value = previous.get(field)
            new_value = current.get(field)
            if old_value is None or new_value is None:
                continue
            timeline.append(TimelineItem(
                id=f"financial-{field}-{current.get('fiscal_year')}",
                date=current["publication_date"].isoformat() if current.get("publication_date") else None,
                kind="FINANCIAL_CHANGE",
                title=f"{label} · {previous.get('fiscal_year')} → {current.get('fiscal_year')}",
                before=str(old_value),
                current=str(new_value),
                status="AVAILABLE" if primary_source else "INSUFFICIENT_DATA",
                evidence=Evidence(
                    claim_type="MODEL_OUTPUT",
                    source=primary_source,
                    observation_date=current.get("fiscal_period_end"),
                    publication_date=current.get("publication_date"),
                    data_origin="CANONICAL_FINANCIAL_STATEMENTS",
                ),
            ))
    timeline.sort(key=lambda item: item.date or date.min, reverse=True)

    latest_annual = annual_rows[-1] if annual_rows else {}
    previous_annual = annual_rows[-2] if len(annual_rows) >= 2 else {}
    changed_fields = ("revenue", "net_income_parent", "eps_basic")
    what_changed = []
    for field in changed_fields:
        old_value = previous_annual.get(field)
        current_value = latest_annual.get(field)
        if old_value is not None and current_value is not None:
            what_changed.append({
                "claim_type": "FACT",
                "metric": field,
                "before": old_value,
                "current": current_value,
                "before_period": previous_annual.get("fiscal_year"),
                "current_period": latest_annual.get("fiscal_year"),
                "source": primary_source,
                "publication_date": latest_annual.get("publication_date"),
            })

    revenue_trend = snapshot.get("trends", {}).get("revenue", {})
    why_now = []
    if revenue_trend.get("label") == "Improving" and annual_rows:
        why_now.append({
            "claim_type": "MODEL_OUTPUT",
            "text": "Revenue trend is classified as improving by the FundamentalSnapshotBuilder.",
            "calculation": revenue_trend.get("calculation_version", "trend_v1"),
            "source": primary_source,
            "publication_date": latest_publication,
        })
    if not why_now:
        why_now.append({
            "claim_type": "UNCERTAINTY",
            "text": "No evidence-backed positive setup is available from the current canonical inputs.",
        })
    why_not_now = []
    if not has_financials:
        why_not_now.append({"claim_type": "UNCERTAINTY", "text": "Canonical financial statements are not available."})
    if price is None:
        why_not_now.append({"claim_type": "UNCERTAINTY", "text": "Canonical price is not available."})
    if not why_not_now:
        why_not_now.append({
            "claim_type": "UNCERTAINTY",
            "text": "Valuation, factor, and risk outputs are withheld because their current producers rely on fixed assumptions, demo inputs, or stub defaults.",
        })
    what_wrong = [{
        "claim_type": "UNCERTAINTY",
        "text": "No asset-specific invalidation condition is stored in the evidence/thesis system.",
    }]

    lineage_origin = price_origin if price else "NO_PRICE_RECORD"
    quality = snapshot.get("data_quality", {})
    history_depth = len(annual_rows)
    missing_statement_source = not primary_source
    quality_status = "INSUFFICIENT_DATA" if not has_financials else "PARTIAL"
    if has_financials and quality.get("financial_data_completeness") == 1.0 and not missing_statement_source:
        quality_status = "AVAILABLE"

    valuation_metrics: dict[str, WorkspaceMetric] = {}
    eps_metric = fundamentals_metrics.get("eps_ttm")
    bvps_metric = fundamentals_metrics.get("bvps")
    current_price = float(price.adjusted_close if price and price.adjusted_close is not None else price.raw_close) if price else None

    # Load stored authoritative provider metrics from FundamentalMetric for cross-check/fallback
    from database.models import FundamentalMetric
    db_metrics = session.query(FundamentalMetric).filter(
        FundamentalMetric.symbol == normalized_symbol,
        FundamentalMetric.metric_id.in_(["PRICE_TO_EARNINGS", "PRICE_TO_BOOK", "P_E", "P_B"]),
        FundamentalMetric.value.isnot(None),
        FundamentalMetric.value > 0
    ).order_by(FundamentalMetric.fiscal_period_end.desc()).all()
    db_metric_map = {m.metric_id: float(m.value) for m in db_metrics}
    db_pe = db_metric_map.get("PRICE_TO_EARNINGS") or db_metric_map.get("P_E")
    db_pb = db_metric_map.get("PRICE_TO_BOOK") or db_metric_map.get("P_B")

    eps_val = eps_metric.value if eps_metric else None
    bvps_val = bvps_metric.value if bvps_metric else None

    for metric_id, denominator, fallback_val, unit in (
        ("pe", eps_val, db_pe, "multiple"),
        ("pb", bvps_val, db_pb, "multiple"),
    ):
        calc_val = None
        calc_note = "Observed multiple only; not a fair-value estimate."
        v_level = None
        status_str = "INSUFFICIENT_DATA"
        is_outlier = False

        min_b = 0.5 if metric_id == "pe" else 0.05
        max_b = 2500.0 if metric_id == "pe" else 50.0

        if current_price is not None and denominator is not None and denominator > 0:
            raw_ratio = current_price / denominator
            calc_val = round(raw_ratio, 2)
            basis_label = "adjusted close" if (price and price.adjusted_close is not None) else "raw close"
            denom_label = "EPS TTM" if metric_id == "pe" else "BVPS"

            if min_b <= raw_ratio <= max_b:
                calc_note = f"Mathematically calculated from canonical {basis_label} ({current_price:.1f} VND) / {denom_label} ({denominator:.1f} VND). Post-corporate-action share basis."
                status_str = "AVAILABLE"
                if fallback_val is not None:
                    if calc_val == round(fallback_val, 2):
                        v_level = "INDEPENDENTLY_VERIFIED"
                    elif abs(calc_val - round(fallback_val, 2)) / max(fallback_val, 0.01) < 0.15:
                        v_level = "SOURCE_RECONCILED"
                    else:
                        v_level = "MATHEMATICALLY_CALCULATED"
                else:
                    v_level = "MATHEMATICALLY_CALCULATED"
            else:
                is_outlier = True
                status_str = "CONFLICTING_DATA" if fallback_val is not None else "AVAILABLE"
                v_level = "CONFLICTING_DATA"
                calc_note = (
                    f"Calculated ratio ({raw_ratio:.1f}) is an extreme economic outlier (bounds: [{min_b}, {max_b}]). "
                    + (f"Conflicts with canonical provider ratio ({fallback_val:.2f})." if fallback_val is not None else "Unmasked.")
                )
        elif fallback_val is not None and (denominator is None or denominator <= 0):
            calc_val = round(fallback_val, 2)
            status_str = "AVAILABLE"
            v_level = "SOURCE_RECONCILED"
            calc_note = "Canonical provider ratio used; direct calculation unavailable or denominator non-positive."
        elif denominator is not None and denominator <= 0:
            status_str = "NOT_MEANINGFUL"
            v_level = "NOT_APPLICABLE"
            calc_note = f"Denominator ({denominator:.2f}) is non-positive; ratio is not economically meaningful."
        elif current_price is not None or denominator is not None:
            v_level = "DATA_PRESENT"

        meaningful = calc_val is not None
        valuation_metrics[metric_id] = WorkspaceMetric(
            value=calc_val,
            unit=unit,
            status=status_str,
            calculation="price / canonical EPS TTM" if metric_id == "pe" else "price / canonical BVPS",
            verification_level=v_level,
            evidence=Evidence(
                claim_type="MODEL_OUTPUT" if meaningful else "UNCERTAINTY",
                source=price_source,
                source_url=price_lineage.url if price_lineage else None,
                observation_date=price.observation_date if price else None,
                publication_date=latest_publication,
                retrieved_at=price_lineage.retrieved_at if price_lineage else None,
                data_origin=price_origin,
                note=calc_note if meaningful else "Requires positive canonical price and per-share fundamentals.",
            ),
        )

    # EV/EBITDA Calculation
    if sector.upper() in {"BANK", "BANKING", "FINANCIALS"}:
        valuation_metrics["ev_ebitda"] = WorkspaceMetric(
            status="NOT_MEANINGFUL",
            unit="multiple",
            evidence=Evidence(
                claim_type="UNCERTAINTY",
                note="EV/EBITDA is not applicable for banking institutions.",
            ),
        )
    else:
        cf_rows = dataset.get("cashflow_annual") or []
        latest_cf = cf_rows[-1] if cf_rows else {}
        depr_amort = latest_cf.get("depreciation_amortization", 0.0) or 0.0
        op_inc = (
            ttm_income.get("operating_income")
            if snapshot.get("period") == "TTM"
            else (annual_rows[-1].get("operating_income") if annual_rows else None)
        )
        ebitda_val = (op_inc + depr_amort) if op_inc is not None else None
        shares_cnt = dataset.get("shares_outstanding") or snapshot.get("per_share", {}).get("shares_basic") or 1_000_000_000
        net_debt_val = snapshot.get("balance_sheet", {}).get("net_debt") or 0.0

        if current_price is not None and shares_cnt and ebitda_val is not None:
            market_cap_bn = (current_price * shares_cnt) / 1_000_000_000
            ev_bn = market_cap_bn + net_debt_val
            if ebitda_val > 0:
                ev_ebitda_multiple = round(ev_bn / ebitda_val, 2)
                valuation_metrics["ev_ebitda"] = WorkspaceMetric(
                    value=ev_ebitda_multiple,
                    unit="multiple",
                    status="AVAILABLE",
                    calculation="EV / EBITDA",
                    evidence=Evidence(
                        claim_type="MODEL_OUTPUT",
                        source=primary_source,
                        observation_date=snapshot_source_date,
                        publication_date=latest_publication,
                        data_origin="CANONICAL_FINANCIAL_STATEMENTS",
                        note=f"Market cap: {market_cap_bn:.1f}B VND, Net Debt: {net_debt_val:.1f}B VND, EBITDA: {ebitda_val:.1f}B VND",
                    ),
                )
            else:
                valuation_metrics["ev_ebitda"] = WorkspaceMetric(
                    status="NOT_MEANINGFUL",
                    unit="multiple",
                    evidence=Evidence(
                        claim_type="UNCERTAINTY",
                        note="EBITDA is negative or zero.",
                    ),
                )
        else:
            valuation_metrics["ev_ebitda"] = WorkspaceMetric(
                status="INSUFFICIENT_DATA",
                unit="multiple",
                evidence=Evidence(
                    claim_type="UNCERTAINTY",
                    note="Insufficient price or EBITDA facts.",
                ),
            )

    unavailable_valuation = {
        metric: WorkspaceMetric(status="INSUFFICIENT_DATA", unit=None, evidence=Evidence(
            claim_type="UNCERTAINTY",
            note="No evidence-backed input contract is available for this output.",
        ))
        for metric in ("peg", "dividend_yield", "fcf_yield", "dcf", "residual_income", "ddm")
    }
    valuation_metrics.update(unavailable_valuation)

    factor_names = ["quality", "growth", "value", "dividend", "momentum", "defensive", "cyclical"]
    factors = {
        name: WorkspaceMetric(
            status="INSUFFICIENT_DATA",
            evidence=Evidence(
                claim_type="UNCERTAINTY",
                note="Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.",
            ),
        )
        for name in factor_names
    }

    risk_names = ["Market", "Business", "Financial", "Valuation", "Liquidity", "Macro", "Geopolitical", "Event", "Data", "Model"]
    risk = {
        "status": "INSUFFICIENT_DATA",
        "overall_score": None,
        "top_contributors": [],
        "missing_data_warning": "Current RiskEngine fills missing categories with stub/default scores; numeric risk is withheld until each category has evidenced inputs.",
        "categories": [{
            "name": name,
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "drivers": [],
        } for name in risk_names],
    }

    opportunity = {
        "score": None,
        "confidence": "INSUFFICIENT",
        "risk": None,
        "horizon": "MEDIUM_TERM",
        "status": "INSUFFICIENT_DATA",
        "why_now": why_now,
        "why_not_now": why_not_now,
        "what_would_make_me_wrong": what_wrong,
    }

    overview: dict[str, Any] = {
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "exchange": asset.exchange,
        "sector": sector,
        "currency": asset.currency,
        "status": asset.status,
    }
    price_payload = {
        "value": current_price,
        "raw_close": price.raw_close if price else None,
        "adjusted_close": price.adjusted_close if price else None,
        "adjustment_factor": price.adjustment_factor if price else None,
        "price_semantics": (
            "DIVIDEND_ADJUSTED_SERIES" if (price and price.adjustment_factor is None)
            else ("CORPORATE_ACTION_ADJUSTED" if (price and price.adjustment_factor is not None and price.adjustment_factor != 1.0)
            else "RAW_UNADJUSTED")
        ) if price else "NO_PRICE",
        "as_of_date": price.observation_date if price else None,
        "source": price_source,
        "status": price_status,
        "data_origin": price_origin,
        "retrieved_at": price_lineage.retrieved_at if price_lineage else (price.created_at if price else None),
        "source_url": price_lineage.url if price_lineage else None,
    }

    result_status: WorkspaceStatus = (
        "INSUFFICIENT_DATA" if not has_financials and price is None else
        "AVAILABLE" if has_financials and price is not None and quality_status == "AVAILABLE" else "PARTIAL"
    )
    response = ResearchWorkspace(
        as_of_date=as_of,
        status=result_status,
        asset=overview,
        price=price_payload,
        opportunity=opportunity,
        fundamentals={
            "status": "AVAILABLE" if has_financials else "INSUFFICIENT_DATA",
            "metrics": fundamentals_metrics,
            "period": snapshot.get("period"),
            "history": history_rows,
            "ttm_available": snapshot.get("period") == "TTM",
            "earnings_quality": snapshot.get("earnings_quality"),
            "financial_health": snapshot.get("financial_health"),
            "quality_flags": snapshot.get("flags", []),
            "data_quality": quality,
            "sources": source_names,
            "latest_publication_date": latest_publication,
        },
        sector_analysis={
            "sector": sector,
            "status": "AVAILABLE" if has_financials else "INSUFFICIENT_DATA",
            "applicable_metrics": sector_model.get_applicable_metrics(),
            "not_applicable_metrics": sector_snapshot.get(
                "not_applicable", getattr(sector_model, "NOT_APPLICABLE", [])
            ),
            "metrics": sector_metrics,
            "notes": sector_snapshot.get("notes", []),
        },
        valuation={
            "status": "PARTIAL" if any(item.status == "AVAILABLE" for item in valuation_metrics.values()) else "INSUFFICIENT_DATA",
            "metrics": valuation_metrics,
            "fair_value": None,
            "scenarios": [],
            "warnings": [
                "Fair value scenarios are withheld: the current valuation builder embeds fixed forecast assumptions and a fixed residual-income ROE.",
                "Observed P/E and P/B, when available, are current multiples and are not fair value estimates.",
            ],
        },
        factors={"status": "INSUFFICIENT_DATA", "scores": factors, "supporting": [], "contradicting": []},
        risk=risk,
        macro_sensitivity={
            "status": "INSUFFICIENT_DATA",
            "sensitivities": [],
            "note": "No canonical company-specific historical sensitivity model is registered.",
        },
        events=events,
        timeline=timeline,
        research_summary={
            "what_changed": what_changed,
            "why_now": why_now,
            "why_not_now": why_not_now,
            "what_would_make_me_wrong": what_wrong,
        },
        data_quality={
            "status": quality_status,
            "price_status": price_status,
            "financial_status": "AVAILABLE" if has_financials else "INSUFFICIENT_DATA",
            "source_origin": lineage_origin,
            "history_depth_years": history_depth,
            "stale_warning": price_status == "STALE",
            "as_of_date": as_of,
        },
    )
    return ResearchWorkspace.model_validate_json(response.model_dump_json())
