import time
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Asset, IndexMembership, Price
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.sector_models import (
    get_sector_for_symbol,
    normalize_sector_name,
    COMPANY_SECTOR_MAP,
)
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.opportunity.engine import OpportunityEngine

_SCANNER_CACHE: dict[str, tuple[float, list["ScannerItem"]]] = {}
_CACHE_TTL_SECONDS = 1800.0  # 30 minutes in-memory cache


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
    try:
        memberships = session.query(IndexMembership).filter(
            IndexMembership.index_symbol == universe,
            IndexMembership.start_date <= as_of,
            (IndexMembership.end_date.is_(None)) | (IndexMembership.end_date >= as_of),
        ).all()
        res = set()
        for member in memberships:
            pub = member.published_at
            if pub is None:
                res.add(member.symbol)
            elif hasattr(pub, "date") and pub.date() <= as_of:
                res.add(member.symbol)
            elif str(pub)[:10] <= as_of.isoformat():
                res.add(member.symbol)
        return res
    except Exception:
        return None


def _item_for_asset(
    session: Session,
    asset: Asset,
    as_of: date,
    horizon: str,
    repository: Optional[FinancialRepository] = None,
    latest_price: Optional[Price] = None,
    macro_data: Any = None,
    past_closes: Optional[list[float]] = None,
    bank_metric: Optional[Any] = None,
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

    dataset = repository.get_financial_dataset(asset.symbol, as_of_date=as_of, asset=asset) if repository else None
    resolved_sector = get_sector_for_symbol(asset.symbol, dataset.get("sector") if dataset else asset.sector)
    has_financials = bool(
        dataset and (dataset.get("income_annual") or dataset.get("income_quarters") or dataset.get("balance_annual"))
    )

    if has_financials and dataset:
        builder = FundamentalSnapshotBuilder(asset.symbol, resolved_sector)
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
        fund_data = {
            "sector": resolved_sector,
            "roe": roe,
            "profit_growth_yoy": profit_growth_yoy,
            "de_ratio": de_ratio,
        }

        if resolved_sector == "BANK":
            sec_metrics = snap.get("sector_metrics", {}).get("metrics", {})
            nim = sec_metrics.get("nim", {}).get("value")
            npl = sec_metrics.get("npl_ratio", {}).get("value")
            llr = sec_metrics.get("llr_coverage", {}).get("value")
            if nim is None or npl is None or llr is None:
                bm = bank_metric
                if bm is None:
                    try:
                        from database.models import BankMetric
                        bm = session.query(BankMetric).filter(
                            BankMetric.asset_id == asset.id,
                            BankMetric.fiscal_date <= as_of
                        ).order_by(BankMetric.fiscal_date.desc()).first()
                    except Exception:
                        pass
                if bm:
                    if nim is None: nim = bm.nim
                    if npl is None: npl = bm.npl_ratio
                    if llr is None: llr = bm.llr_ratio
            if nim is not None: fund_data["nim"] = nim
            if npl is not None: fund_data["npl_ratio"] = npl
            if llr is not None: fund_data["llr_coverage"] = llr

        # Earnings acceleration from income_quarters
        income_quarters = dataset.get("income_quarters", [])
        if len(income_quarters) >= 5:
            sorted_q = sorted(
                [q for q in income_quarters if q.get("fiscal_period_end")],
                key=lambda x: x["fiscal_period_end"]
            )
            if len(sorted_q) >= 5:
                latest_q = sorted_q[-1]
                prior_q = sorted_q[-2]

                def _get_ni(q):
                    return q.get("net_income_parent") or q.get("net_income") or 0.0

                latest_ni = _get_ni(latest_q)
                prior_ni = _get_ni(prior_q)
                yoy_latest_base = _get_ni(sorted_q[-5])
                yoy_prior_base = _get_ni(sorted_q[-6]) if len(sorted_q) >= 6 else None

                if yoy_latest_base and abs(yoy_latest_base) > 0:
                    g_latest = (latest_ni - yoy_latest_base) / abs(yoy_latest_base)
                    if yoy_prior_base and abs(yoy_prior_base) > 0:
                        g_prior = (prior_ni - yoy_prior_base) / abs(yoy_prior_base)
                        if g_latest > g_prior:
                            fund_data["earnings_acceleration"] = True
                        elif g_latest < g_prior - 0.20 and g_latest < 0:
                            fund_data["earnings_acceleration"] = False

        # CFO positive from cash_flow
        cf_data = snap.get("cash_flow", {})
        cfo = cf_data.get("cfo")
        cfo_ni = cf_data.get("cfo_to_ni", {})
        cfo_to_ni_val = cfo_ni.get("value") if isinstance(cfo_ni, dict) else cfo_ni
        if cfo is not None:
            if cfo > 0 and (cfo_to_ni_val is None or cfo_to_ni_val >= 0.8):
                fund_data["cfo_positive"] = True
            elif cfo < 0:
                fund_data["cfo_positive"] = False

        # Price momentum score from 60 past trading sessions
        closes = past_closes
        if closes is None:
            try:
                past_prices = session.query(Price.raw_close).filter(
                    Price.asset_id == asset.id,
                    Price.observation_date <= as_of,
                    Price.status == "VALID"
                ).order_by(Price.observation_date.desc()).limit(60).all()
                closes = [p[0] for p in past_prices if p[0] is not None]
            except Exception:
                closes = []
        if len(closes) >= 20:
            current_p = closes[0]
            ma20 = sum(closes[:20]) / 20.0
            ret20 = (current_p - closes[19]) / closes[19] if closes[19] > 0 else 0.0
            ma50 = sum(closes[:50]) / 50.0 if len(closes) >= 50 else ma20

            mom = 0.0
            if current_p > ma20: mom += 2.5
            else: mom -= 2.5
            if current_p > ma50: mom += 2.5
            else: mom -= 2.5
            if ma20 > ma50: mom += 2.0
            else: mom -= 2.0

            if ret20 > 0.05: mom += 3.0
            elif ret20 > 0.0: mom += 1.0
            elif ret20 < -0.05: mom -= 3.0
            else: mom -= 1.0

            fund_data["price_momentum_score"] = max(-10.0, min(10.0, mom))

        eps = snap.get("per_share", {}).get("eps_ttm")
        bvps = snap.get("per_share", {}).get("bvps") or snap.get("bvps")
        val_data = {}
        val_status = "INSUFFICIENT_DATA"
        if latest_price and latest_price.raw_close:
            price_val = float(latest_price.raw_close)
            try:
                from services.valuation.builder import ValuationSnapshotBuilder
                val_builder = ValuationSnapshotBuilder(asset.symbol, resolved_sector)
                fund_for_val = {
                    "symbol": asset.symbol,
                    "sector": resolved_sector,
                    "eps_ttm": eps,
                    "bvps": bvps,
                    "shares_outstanding": dataset.get("shares_outstanding") or 1_000_000_000,
                    "revenue_ttm": snap.get("revenue_ttm") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
                    "net_income_ttm": snap.get("net_income_ttm") or (dataset["income_annual"][-1].get("net_income_parent") if dataset.get("income_annual") else None),
                    "net_debt": snap.get("balance_sheet", {}).get("net_debt", {}).get("value") if isinstance(snap.get("balance_sheet", {}).get("net_debt"), dict) else snap.get("balance_sheet", {}).get("net_debt"),
                    "roe": roe_val,
                }
                val_snap = val_builder.build(fund_for_val, price_val, as_of)
                if val_snap.margin_of_safety is not None:
                    val_data["margin_of_safety"] = val_snap.margin_of_safety
                    val_status = "AVAILABLE"
                if eps and eps > 0:
                    val_data["pe"] = price_val / eps
                    if val_status == "INSUFFICIENT_DATA":
                        val_status = "AVAILABLE"
            except Exception:
                if eps and eps > 0:
                    pe = price_val / eps
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
            sector=resolved_sector,
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
        sector=resolved_sector,
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
    db_sectors = [
        value for (value,) in session.query(Asset.sector).filter(
            Asset.status == "ACTIVE",
            Asset.asset_type.in_(["STOCK", "ETF", "MUTUAL_FUND"]),
            Asset.sector.is_not(None),
        ).distinct().all()
    ]
    all_sectors = set(COMPANY_SECTOR_MAP.values())
    for s in db_sectors:
        n = normalize_sector_name(s)
        if n:
            all_sectors.add(n)
    sector_options = sorted(list(all_sectors))

    universe_symbols = _universe_symbols(session, universe, as_of)
    query = session.query(Asset).filter(
        Asset.status == "ACTIVE",
        Asset.asset_type.in_(["STOCK", "ETF", "MUTUAL_FUND"]),
    )
    if universe_symbols is not None:
        query = query.filter(Asset.symbol.in_(universe_symbols)) if universe_symbols else query.filter(Asset.id == -1)
    if sector:
        norm_filter_sec = normalize_sector_name(sector) or sector.upper()
        matching_symbols = [sym for sym, sec in COMPANY_SECTOR_MAP.items() if sec == norm_filter_sec]
        query = query.filter(
            (Asset.sector.ilike(f"%{sector}%")) | (Asset.symbol.in_(matching_symbols))
        )
    if symbol:
        query = query.filter(Asset.symbol == symbol.upper())

    assets = query.order_by(Asset.symbol).all()
    asset_ids = [a.id for a in assets]

    # Pre-fetch latest prices and past 60 closes in a single indexed query
    latest_price_map: dict[int, Any] = {}
    past_closes_map: dict[int, list[float]] = {}
    if asset_ids:
        recent_prices = session.query(
            Price.asset_id, Price.observation_date, Price.raw_close, Price.source, Price.status
        ).filter(
            Price.asset_id.in_(asset_ids),
            Price.status == "VALID",
            Price.observation_date <= as_of,
        ).order_by(Price.asset_id, Price.observation_date.desc()).all()
        for p in recent_prices:
            aid = p.asset_id
            if aid not in latest_price_map:
                latest_price_map[aid] = p
                past_closes_map[aid] = []
            if len(past_closes_map[aid]) < 60 and p.raw_close is not None:
                past_closes_map[aid].append(float(p.raw_close))

    # Pre-fetch bank metrics in a single query for bank assets
    bank_metric_map: dict[int, Any] = {}
    bank_asset_ids = [a.id for a in assets if get_sector_for_symbol(a.symbol, a.sector) == "BANK"]
    if bank_asset_ids:
        try:
            from database.models import BankMetric
            bm_rows = session.query(BankMetric).filter(
                BankMetric.asset_id.in_(bank_asset_ids),
                BankMetric.fiscal_date <= as_of,
            ).order_by(BankMetric.asset_id, BankMetric.fiscal_date.desc()).all()
            for bm in bm_rows:
                if bm.asset_id not in bank_metric_map:
                    bank_metric_map[bm.asset_id] = bm
        except Exception:
            pass

    # Memory cache key
    cache_key = f"{universe}_{sector}_{symbol}_{as_of.isoformat()}_{horizon}"
    now = time.time()
    if cache_key in _SCANNER_CACHE and (now - _SCANNER_CACHE[cache_key][0] < _CACHE_TTL_SECONDS):
        items = list(_SCANNER_CACHE[cache_key][1])
    else:
        with FinancialRepository(session=session) as repository:
            items = []
            for asset in assets:
                try:
                    item = _item_for_asset(
                        session=session,
                        asset=asset,
                        as_of=as_of,
                        horizon=horizon,
                        repository=repository,
                        latest_price=latest_price_map.get(asset.id),
                        macro_data=object(),
                        past_closes=past_closes_map.get(asset.id),
                        bank_metric=bank_metric_map.get(asset.id),
                    )
                    items.append(item)
                except Exception:
                    items.append(ScannerItem(
                        symbol=asset.symbol,
                        name=asset.name,
                        asset_type=asset.asset_type,
                        sector=asset.sector,
                        opportunity_score=None,
                        confidence="INSUFFICIENT",
                        risk_score=None,
                        valuation_status="INSUFFICIENT_DATA",
                        factor_summary=None,
                        factor_status="INSUFFICIENT_DATA",
                        why_now=[],
                        why_not_now=[],
                        what_could_go_wrong=[],
                        data_status="INSUFFICIENT_DATA",
                        data_freshness={"status": "INSUFFICIENT_DATA", "as_of_date": None, "source": None},
                        horizon=horizon,
                        model_version="opportunity_medium_v1",
                    ))
        _SCANNER_CACHE[cache_key] = (now, list(items))

    if sector:
        norm_filter_sec = normalize_sector_name(sector) or sector.upper()
        matching_symbols = [sym for sym, sec in COMPANY_SECTOR_MAP.items() if sec == norm_filter_sec]
        items = [
            item for item in items
            if (item.sector and normalize_sector_name(item.sector) == norm_filter_sec)
            or (item.symbol in matching_symbols)
        ]

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