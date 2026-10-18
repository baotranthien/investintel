from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from services.decision.engine import (
    build_decision_context,
    build_portfolio_decision_view,
    capture_asset_decision_snapshot,
)
from services.decision.schemas import DecisionContextResponse, DecisionSnapshotResponse, PortfolioDecisionResponse

router = APIRouter(prefix="/api/v1", tags=["decision"])


@router.get("/decision/{symbol}", response_model=DecisionContextResponse)
def get_asset_decision_context(
    symbol: str,
    as_of: date = Query(default_factory=date.today),
    session: Session = Depends(get_db),
):
    return build_decision_context(session, symbol, as_of)


@router.post("/decision/{symbol}/snapshot", status_code=201, response_model=DecisionSnapshotResponse)
def create_asset_decision_snapshot(
    symbol: str,
    as_of: date = Query(default_factory=date.today),
    session: Session = Depends(get_db),
):
    snapshot = capture_asset_decision_snapshot(session, symbol, as_of)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    session.commit()
    return {
        "id": snapshot.id,
        "symbol": symbol.upper(),
        "as_of_date": as_of.isoformat(),
        "captured_at": snapshot.captured_at,
    }


@router.get("/portfolio/decision", response_model=PortfolioDecisionResponse)
def get_portfolio_decision_context(
    as_of: date = Query(default_factory=date.today),
    session: Session = Depends(get_db),
):
    return build_portfolio_decision_view(session, as_of)
