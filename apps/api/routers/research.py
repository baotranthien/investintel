from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from services.research.backtest import BacktestConfig, BacktestResult, HistoricalBacktestEngine
from services.research.workspace import ResearchWorkspace, build_research_workspace

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post("/backtest", response_model=BacktestResult)
def run_backtest(
    config: BacktestConfig,
    session: Session = Depends(get_db),
) -> BacktestResult:
    """Execute point-in-time historical backtest and replay simulation."""
    engine = HistoricalBacktestEngine(session)
    return engine.run_backtest(config)


@router.get("/{symbol}", response_model=ResearchWorkspace)
def get_research_workspace(
    symbol: str,
    as_of: date = Query(default_factory=date.today, description="Point-in-time date (YYYY-MM-DD)"),
    session: Session = Depends(get_db),
) -> ResearchWorkspace:
    """Return a canonical, evidence-first asset research workspace."""
    result = build_research_workspace(session, symbol, as_of)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Asset {symbol.upper()} is not registered.")
    return result
