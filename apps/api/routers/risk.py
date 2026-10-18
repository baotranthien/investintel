from fastapi import APIRouter
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.risk.engine import RiskEngine

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

@router.get("/{symbol}")
def get_risk_profile(symbol: str):
    """Returns the comprehensive 10-category risk profile for a stock."""
    # Using dummy fundamentals and valuation for now
    return RiskEngine.calculate_profile(symbol, {}, {}, date.today())
