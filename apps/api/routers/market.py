from datetime import date, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from services.market.dashboard import MarketDashboard, build_market_dashboard
from services.ingestion.reconciliation import MarketDataReconciliationEngine

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/dashboard", response_model=MarketDashboard)
def get_market_dashboard(session: Session = Depends(get_db)) -> MarketDashboard:
    """Return market values and evidence from canonical database records only."""
    try:
        return build_market_dashboard(session, date.today())
    except Exception as exc:
        import traceback
        trace = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {str(exc)} | TRACE: {trace.replace(chr(10), ' ;; ')}"
        )


@router.get("/reconciliation/{symbol}")
async def get_market_reconciliation(
    symbol: str,
    lookback_days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns independent cross-provider reconciliation report between DNSE and VNDIRECT.
    Surfaces matching sessions, missing dates, and SOURCE_DISAGREEMENT status.
    """
    engine = MarketDataReconciliationEngine()
    start_date = date.today() - timedelta(days=lookback_days)
    end_date = date.today()
    report = await engine.compare_providers(symbol, start_date=start_date, end_date=end_date)
    return report.to_dict()