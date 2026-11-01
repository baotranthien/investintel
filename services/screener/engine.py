# -*- coding: utf-8 -*-
"""
Multi-Filter Financial Stock Screener Engine — Phase 5A.
Allows institutional cross-asset screening against real fundamental, valuation, and quality metrics:
- Valuation: P/E, P/B, Margin of Safety
- Profitability: ROE, Gross Margin, Net Margin
- Financial Health: Debt/Equity, Debt/Assets, Current Ratio
- Growth: Revenue YoY, Net Income YoY
- Size: Market Capitalization
- Universe: ALL, VN30, VN100
"""
from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, Price, IndexMembership
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.valuation.builder import ValuationSnapshotBuilder


class ScreenerCriteria(BaseModel):
    universe: str = "ALL"  # ALL, VN30, VN100
    sector: Optional[str] = None
    pe_min: Optional[float] = None
    pe_max: Optional[float] = None
    pb_min: Optional[float] = None
    pb_max: Optional[float] = None
    roe_min: Optional[float] = None
    gross_margin_min: Optional[float] = None
    net_margin_min: Optional[float] = None
    de_ratio_max: Optional[float] = None
    current_ratio_min: Optional[float] = None
    margin_of_safety_min: Optional[float] = None
    market_cap_min_bil: Optional[float] = None
    limit: int = 50


class ScreenedStock(BaseModel):
    symbol: str
    name: str
    sector: str
    current_price: Optional[float] = None
    market_cap_billion_vnd: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    de_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    composite_fair_value_base: Optional[float] = None
    margin_of_safety_pct: Optional[float] = None
    passed_filters: List[str] = []
    data_status: str = "CANONICAL_DATABASE"


class ScreenerResult(BaseModel):
    as_of_date: date
    total_screened: int
    matched_count: int
    criteria_applied: ScreenerCriteria
    matches: List[ScreenedStock]


class StockScreenerEngine:
    """Evaluates multi-dimensional financial and valuation screens deterministically."""

    def __init__(self, session: Session):
        self.session = session
        self.repo = FinancialRepository(session)

    def screen(self, criteria: ScreenerCriteria, as_of: Optional[date] = None) -> ScreenerResult:
        as_of = as_of or date.today()

        # 1. Resolve asset universe
        query = self.session.query(Asset).filter(Asset.status == "ACTIVE")
        if criteria.universe in ("VN30", "VN100"):
            query = query.join(IndexMembership, Asset.id == IndexMembership.asset_id).filter(
                IndexMembership.index_symbol == criteria.universe,
                IndexMembership.start_date <= as_of,
                (IndexMembership.end_date.is_(None)) | (IndexMembership.end_date >= as_of),
            )

        if criteria.sector:
            query = query.filter(Asset.sector.ilike(f"%{criteria.sector}%"))

        assets = query.all()
        matched_stocks: List[ScreenedStock] = []

        for asset in assets:
            sym = asset.symbol.upper()
            if not sym or sym.startswith("^"):
                continue

            # Load Price
            p_row = (
                self.session.query(Price)
                .filter(Price.asset_id == asset.id, Price.status == "VALID", Price.observation_date <= as_of)
                .order_by(Price.observation_date.desc())
                .first()
            )
            price = float(p_row.adjusted_close if p_row.adjusted_close is not None else p_row.raw_close) if p_row else None

            # Load Fundamentals
            dataset = self.repo.get_financial_dataset(sym, as_of_date=as_of)
            if not dataset or not dataset.get("income_annual"):
                continue

            sec = asset.sector or dataset.get("sector") or "GENERAL"
            builder = FundamentalSnapshotBuilder(sym, sec)
            snap = builder.build_snapshot(
                income_quarters=dataset["income_quarters"],
                income_annual=dataset["income_annual"],
                balance_annual=dataset["balance_annual"],
                cashflow_annual=dataset["cashflow_annual"],
                shares_outstanding=dataset.get("shares_outstanding"),
                as_of_date=as_of,
            )

            eps = snap.get("eps_ttm") or snap.get("eps_basic")
            bvps = snap.get("bvps")
            shares = dataset.get("shares_outstanding")

            mcap = round((price * shares) / 1e9, 2) if (price and shares) else None
            pe_val = round(price / eps, 2) if (price and eps and eps > 0) else None
            pb_val = round(price / bvps, 2) if (price and bvps and bvps > 0) else None

            def _mval(d, k):
                res = d.get(k) if isinstance(d, dict) else None
                return res.get("value") if isinstance(res, dict) else res

            gm = _mval(snap.get("profitability", {}), "gross_margin")
            nm = _mval(snap.get("profitability", {}), "net_margin")
            roe = _mval(snap.get("profitability", {}), "roe")
            de = _mval(snap.get("balance_sheet", {}), "de_ratio")
            cr = _mval(snap.get("balance_sheet", {}), "current_ratio")

            # Valuation Fair Value & Margin of Safety (lazy evaluation)
            val_builder = ValuationSnapshotBuilder(sym, sec)
            comp_fv = None
            mos_pct = None

            # Filter checks
            passed: List[str] = []
            matched = True

            # Market Cap filter
            if criteria.market_cap_min_bil is not None:
                if mcap is not None and mcap >= criteria.market_cap_min_bil:
                    passed.append(f"Market Cap >= {criteria.market_cap_min_bil:,.0f}B")
                else:
                    matched = False

            # P/E filters
            if matched and criteria.pe_min is not None:
                if pe_val is not None and pe_val >= criteria.pe_min:
                    passed.append(f"P/E >= {criteria.pe_min}")
                else:
                    matched = False
            if matched and criteria.pe_max is not None:
                if pe_val is not None and pe_val <= criteria.pe_max:
                    passed.append(f"P/E <= {criteria.pe_max}")
                else:
                    matched = False

            # P/B filters
            if matched and criteria.pb_min is not None:
                if pb_val is not None and pb_val >= criteria.pb_min:
                    passed.append(f"P/B >= {criteria.pb_min}")
                else:
                    matched = False
            if matched and criteria.pb_max is not None:
                if pb_val is not None and pb_val <= criteria.pb_max:
                    passed.append(f"P/B <= {criteria.pb_max}")
                else:
                    matched = False

            # Profitability filters
            if matched and criteria.roe_min is not None:
                if roe is not None and roe >= criteria.roe_min:
                    passed.append(f"ROE >= {criteria.roe_min}%")
                else:
                    matched = False

            if matched and criteria.gross_margin_min is not None:
                if gm is not None and gm >= criteria.gross_margin_min:
                    passed.append(f"Gross Margin >= {criteria.gross_margin_min}%")
                else:
                    matched = False

            if matched and criteria.net_margin_min is not None:
                if nm is not None and nm >= criteria.net_margin_min:
                    passed.append(f"Net Margin >= {criteria.net_margin_min}%")
                else:
                    matched = False

            # Financial Health filters
            if matched and criteria.de_ratio_max is not None:
                if de is not None and de <= criteria.de_ratio_max:
                    passed.append(f"D/E <= {criteria.de_ratio_max}")
                else:
                    matched = False

            if matched and criteria.current_ratio_min is not None:
                if cr is not None and cr >= criteria.current_ratio_min:
                    passed.append(f"Current Ratio >= {criteria.current_ratio_min}")
                else:
                    matched = False

            # Margin of Safety filter & fair value computation only if passed earlier filters
            if matched and price and eps:
                try:
                    from apps.api.routers.valuation import _load_fundamentals_for_valuation
                    funds = _load_fundamentals_for_valuation(sym, as_of) or {}
                    val_snap = val_builder.build(funds, price, as_of)
                    if val_snap and val_snap.composite_fair_value:
                        base = val_snap.composite_fair_value.range.base
                        if base and base > 0:
                            comp_fv = round(base, 0)
                            mos_pct = round(((base - price) / base) * 100, 1)
                except Exception:
                    pass

            if matched and criteria.margin_of_safety_min is not None:
                if mos_pct is not None and mos_pct >= criteria.margin_of_safety_min:
                    passed.append(f"Margin of Safety >= {criteria.margin_of_safety_min}%")
                else:
                    matched = False

            if matched:
                matched_stocks.append(ScreenedStock(
                    symbol=sym,
                    name=asset.name or f"{sym} Corporation",
                    sector=sec,
                    current_price=price,
                    market_cap_billion_vnd=mcap,
                    pe=pe_val,
                    pb=pb_val,
                    roe=round(roe, 2) if roe is not None else None,
                    gross_margin=round(gm, 2) if gm is not None else None,
                    net_margin=round(nm, 2) if nm is not None else None,
                    de_ratio=round(de, 4) if de is not None else None,
                    current_ratio=round(cr, 2) if cr is not None else None,
                    composite_fair_value_base=comp_fv,
                    margin_of_safety_pct=mos_pct,
                    passed_filters=passed,
                    data_status="CANONICAL_DATABASE",
                ))

            if len(matched_stocks) >= criteria.limit:
                break

        return ScreenerResult(
            as_of_date=as_of,
            total_screened=len(assets),
            matched_count=len(matched_stocks),
            criteria_applied=criteria,
            matches=matched_stocks,
        )

