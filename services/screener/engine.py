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
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.models import Asset, Price, IndexMembership
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.valuation.builder import ValuationSnapshotBuilder


_SCREENER_BASE_CACHE: dict[str, tuple[float, int, list["ScreenedStock"]]] = {}
_SCREENER_CACHE_TTL = 1800.0  # 30 minutes TTL in seconds


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
        cache_key = f"{criteria.universe}:{criteria.sector or ''}:{as_of.isoformat()}"
        use_cache = "PYTEST_CURRENT_TEST" not in os.environ

        base_stocks: List[ScreenedStock] = []
        total_screened: int = 0

        if use_cache and cache_key in _SCREENER_BASE_CACHE:
            cached_time, cached_total, cached_list = _SCREENER_BASE_CACHE[cache_key]
            if time.time() - cached_time < _SCREENER_CACHE_TTL:
                base_stocks = cached_list
                total_screened = cached_total

        if not base_stocks:
            # 1. Resolve asset universe
            query = self.session.query(Asset).filter(Asset.status == "ACTIVE")
            if criteria.universe in ("VN30", "VN100"):
                query = query.join(IndexMembership, Asset.symbol == IndexMembership.symbol).filter(
                    IndexMembership.index_symbol == criteria.universe,
                    IndexMembership.start_date <= as_of,
                    (IndexMembership.end_date.is_(None)) | (IndexMembership.end_date >= as_of),
                )

            if criteria.sector:
                query = query.filter(Asset.sector.ilike(f"%{criteria.sector}%"))

            assets = query.all()
            total_screened = len(assets)

            # Canonical market price batch resolution
            from services.market.canonical_price import CanonicalPriceResolver
            asset_ids = [a.id for a in assets]
            canonical_prices = CanonicalPriceResolver.resolve_prices_batch(self.session, asset_ids=asset_ids, as_of=as_of)
            latest_prices = {cp.symbol: cp.price for cp in canonical_prices.values()}

            def _mval(d, k):
                res = d.get(k) if isinstance(d, dict) else None
                return res.get("value") if isinstance(res, dict) else res

            computed_base: List[ScreenedStock] = []
            for asset in assets:
                sym = asset.symbol.upper()
                if not sym or sym.startswith("^"):
                    continue

                # Load Price from canonical resolver
                price = latest_prices.get(sym)

                # Load Fundamentals
                dataset = self.repo.get_financial_dataset(sym, as_of_date=as_of)
                if not dataset or not dataset.get("income_annual"):
                    continue

                from services.fundamentals.sector_models import get_sector_for_symbol
                raw_sec = asset.sector or dataset.get("sector") or "GENERAL"
                sec = get_sector_for_symbol(sym, raw_sec)
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

                gm = _mval(snap.get("profitability", {}), "gross_margin")
                nm = _mval(snap.get("profitability", {}), "net_margin")
                op_m = (
                    _mval(snap.get("profitability", {}), "operating_margin")
                    or _mval(snap.get("profitability", {}), "ebit_margin")
                    or nm
                )
                rev_yoy = _mval(snap.get("growth", {}), "revenue_yoy")
                rev_cagr_3y = _mval(snap.get("growth", {}), "revenue_cagr_3y")
                roe = _mval(snap.get("profitability", {}), "roe")
                de = _mval(snap.get("balance_sheet", {}), "de_ratio")
                cr = _mval(snap.get("balance_sheet", {}), "current_ratio")

                # Valuation Fair Value & Margin of Safety via in-memory dataset/snap
                comp_fv = None
                mos_pct = None
                if price and eps:
                    try:
                        fund_for_val = {
                            "symbol": sym,
                            "sector": sec,
                            "eps_ttm": eps,
                            "bvps": bvps,
                            "shares_outstanding": shares or 1_000_000_000,
                            "revenue_ttm": snap.get("revenue_ttm") or (dataset["income_annual"][-1].get("revenue") if dataset.get("income_annual") else None),
                            "net_income_ttm": snap.get("net_income_ttm") or (dataset["income_annual"][-1].get("net_income_parent") if dataset.get("income_annual") else None),
                            "net_debt": snap.get("balance_sheet", {}).get("net_debt", {}).get("value") if isinstance(snap.get("balance_sheet", {}).get("net_debt"), dict) else snap.get("balance_sheet", {}).get("net_debt"),
                            "roe": roe,
                            "use_dynamic_assumptions": True,
                            "operating_margin": op_m,
                            "revenue_yoy": rev_yoy,
                            "revenue_cagr_3y": rev_cagr_3y,
                        }
                        val_snap = ValuationSnapshotBuilder(sym, sec).build(fund_for_val, price, as_of)
                        if val_snap and val_snap.composite_fair_value:
                            base = val_snap.composite_fair_value.range.base
                            if base and base > 0:
                                comp_fv = round(base, 0)
                                mos_pct = round(((base - price) / base) * 100, 1)
                    except Exception:
                        pass

                computed_base.append(ScreenedStock(
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
                    passed_filters=[],
                    data_status="CANONICAL_DATABASE",
                ))

            base_stocks = computed_base
            if use_cache:
                _SCREENER_BASE_CACHE[cache_key] = (time.time(), total_screened, base_stocks)

        # 2. Filter base stocks in memory
        matched_stocks: List[ScreenedStock] = []
        for stk in base_stocks:
            passed: List[str] = []
            matched = True

            # Market Cap filter
            if criteria.market_cap_min_bil is not None:
                if stk.market_cap_billion_vnd is not None and stk.market_cap_billion_vnd >= criteria.market_cap_min_bil:
                    passed.append(f"Market Cap >= {criteria.market_cap_min_bil:,.0f}B")
                else:
                    matched = False

            # P/E filters (strict boundary: P/E < pe_max)
            if matched and criteria.pe_min is not None:
                if stk.pe is not None and stk.pe > criteria.pe_min:
                    passed.append(f"P/E > {criteria.pe_min}")
                else:
                    matched = False
            if matched and criteria.pe_max is not None:
                if stk.pe is not None and stk.pe < criteria.pe_max:
                    passed.append(f"P/E < {criteria.pe_max}")
                else:
                    matched = False

            # P/B filters
            if matched and criteria.pb_min is not None:
                if stk.pb is not None and stk.pb >= criteria.pb_min:
                    passed.append(f"P/B >= {criteria.pb_min}")
                else:
                    matched = False
            if matched and criteria.pb_max is not None:
                if stk.pb is not None and stk.pb <= criteria.pb_max:
                    passed.append(f"P/B <= {criteria.pb_max}")
                else:
                    matched = False

            # Profitability filters (strict boundary: ROE > roe_min)
            if matched and criteria.roe_min is not None:
                if stk.roe is not None and stk.roe > criteria.roe_min:
                    passed.append(f"ROE > {criteria.roe_min}%")
                else:
                    matched = False

            if matched and criteria.gross_margin_min is not None:
                if stk.gross_margin is not None and stk.gross_margin >= criteria.gross_margin_min:
                    passed.append(f"Gross Margin >= {criteria.gross_margin_min}%")
                else:
                    matched = False

            if matched and criteria.net_margin_min is not None:
                if stk.net_margin is not None and stk.net_margin >= criteria.net_margin_min:
                    passed.append(f"Net Margin >= {criteria.net_margin_min}%")
                else:
                    matched = False

            # Financial Health filters
            if matched and criteria.de_ratio_max is not None:
                if stk.de_ratio is not None and stk.de_ratio <= criteria.de_ratio_max:
                    passed.append(f"D/E <= {criteria.de_ratio_max}")
                else:
                    matched = False

            if matched and criteria.current_ratio_min is not None:
                if stk.current_ratio is not None and stk.current_ratio >= criteria.current_ratio_min:
                    passed.append(f"Current Ratio >= {criteria.current_ratio_min}")
                else:
                    matched = False

            # Margin of Safety filter
            if matched and criteria.margin_of_safety_min is not None:
                if stk.margin_of_safety_pct is not None and stk.margin_of_safety_pct >= criteria.margin_of_safety_min:
                    passed.append(f"Margin of Safety >= {criteria.margin_of_safety_min}%")
                else:
                    matched = False

            if matched:
                item = (
                    stk.model_copy(update={"passed_filters": passed})
                    if hasattr(stk, "model_copy")
                    else stk.copy(update={"passed_filters": passed})
                )
                matched_stocks.append(item)

            if len(matched_stocks) >= criteria.limit:
                break

        return ScreenerResult(
            as_of_date=as_of,
            total_screened=total_screened,
            matched_count=len(matched_stocks),
            criteria_applied=criteria,
            matches=matched_stocks,
        )

