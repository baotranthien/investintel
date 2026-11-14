# -*- coding: utf-8 -*-
"""
Stock Screener Router — Phase 5A.
Provides multi-criteria screening across market valuation, profitability, growth, and financial health.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from services.screener.engine import ScreenerCriteria, ScreenerResult, StockScreenerEngine
from services.market.trading_hours import get_effective_trading_date

router = APIRouter(prefix="/api/v1/screener", tags=["screener"])


@router.get("", response_model=ScreenerResult)
def screen_stocks(
    universe: str = Query("ALL", description="Universe: ALL, VN30, VN100"),
    sector: Optional[str] = Query(None, description="Sector filter"),
    pe_min: Optional[float] = Query(None, description="Minimum P/E"),
    pe_max: Optional[float] = Query(None, description="Maximum P/E"),
    pb_min: Optional[float] = Query(None, description="Minimum P/B"),
    pb_max: Optional[float] = Query(None, description="Maximum P/B"),
    roe_min: Optional[float] = Query(None, description="Minimum ROE (%)"),
    gross_margin_min: Optional[float] = Query(None, description="Minimum Gross Margin (%)"),
    net_margin_min: Optional[float] = Query(None, description="Minimum Net Margin (%)"),
    de_ratio_max: Optional[float] = Query(None, description="Maximum Debt-to-Equity ratio"),
    current_ratio_min: Optional[float] = Query(None, description="Minimum Current Ratio"),
    margin_of_safety_min: Optional[float] = Query(None, description="Minimum Margin of Safety (%)"),
    market_cap_min_bil: Optional[float] = Query(None, description="Minimum Market Cap (Billion VND)"),
    limit: int = Query(200, ge=1, le=500),
    as_of: date = Query(default_factory=get_effective_trading_date),
    session: Session = Depends(get_db),
) -> ScreenerResult:
    """Execute real-time multi-dimensional stock screening grounded in canonical database metrics."""
    criteria = ScreenerCriteria(
        universe=universe,
        sector=sector,
        pe_min=pe_min,
        pe_max=pe_max,
        pb_min=pb_min,
        pb_max=pb_max,
        roe_min=roe_min,
        gross_margin_min=gross_margin_min,
        net_margin_min=net_margin_min,
        de_ratio_max=de_ratio_max,
        current_ratio_min=current_ratio_min,
        margin_of_safety_min=margin_of_safety_min,
        market_cap_min_bil=market_cap_min_bil,
        limit=limit,
    )
    engine = StockScreenerEngine(session)
    return engine.screen(criteria, as_of=as_of)

