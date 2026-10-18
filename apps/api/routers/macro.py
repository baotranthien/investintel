from fastapi import APIRouter, Depends
from datetime import date
from sqlalchemy.orm import Session
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.connection import get_db
from services.macro.engine import MacroEngine, MarketRegimeEngine
from services.macro.observations import MacroLatestResponse, get_latest_macro_series

router = APIRouter(prefix="/api/v1/macro", tags=["macro", "regime"])

@router.get("/dashboard")
def get_macro_dashboard():
    """Returns the consolidated Macro Dashboard with regime states and variables."""
    return MacroEngine.get_dashboard(date.today())

@router.get("/market-regime")
def get_market_regime():
    """Returns the current market regime (e.g. EXPANSION, RISK_OFF)."""
    return MarketRegimeEngine.determine_regime(date.today())


@router.get("/observations/latest", response_model=MacroLatestResponse)
def get_latest_macro_observations(session: Session = Depends(get_db)) -> MacroLatestResponse:
    """Return the latest published canonical observation for each registered macro series."""
    return get_latest_macro_series(session, date.today())
