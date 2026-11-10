from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.risk.engine import RiskEngine
from services.market.trading_hours import get_effective_trading_date
from apps.api.routers.valuation import _load_fundamentals_for_valuation, get_valuation_snapshot

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

@router.get("/{symbol}")
def get_risk_profile(symbol: str, as_of: Optional[date] = None):
    """Returns the comprehensive 10-category risk profile for a stock with real fundamentals and valuation."""
    sym = symbol.upper()
    target_date = as_of or get_effective_trading_date()
    fund_dict = _load_fundamentals_for_valuation(sym, target_date) or {}
    val_dict = {}
    try:
        val_snapshot = get_valuation_snapshot(sym, as_of=target_date.isoformat() if target_date else None)
        if val_snapshot and isinstance(val_snapshot, dict):
            val_dict = val_snapshot
    except Exception:
        pass

    return RiskEngine.calculate_profile(sym, fund_dict, val_dict, target_date)
