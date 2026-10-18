from fastapi import APIRouter
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from services.opportunity.scanner import (
    OpportunityScannerResponse,
    ScannerItem,
    build_opportunity_scanner,
)

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunity"])

@router.get("", response_model=OpportunityScannerResponse)
def get_opportunity_scanner(
    universe: Literal["ALL", "VN100", "VN300"] = Query("ALL"),
    sector: Optional[str] = Query(None),
    horizon: Literal["MEDIUM_TERM", "LONG_TERM"] = Query("MEDIUM_TERM"),
    score_min: Optional[float] = Query(None, ge=0, le=100),
    score_max: Optional[float] = Query(None, ge=0, le=100),
    risk_max: Optional[float] = Query(None, ge=0, le=100),
    confidence: Optional[Literal["HIGH", "MODERATE", "LOW", "INSUFFICIENT"]] = Query(None),
    factor: Optional[str] = Query(None),
    valuation_status: Optional[Literal["AVAILABLE", "INSUFFICIENT_DATA"]] = Query(None),
    session: Session = Depends(get_db),
) -> OpportunityScannerResponse:
    """Return canonical assets with engine-derived values only when inputs support them."""
    return build_opportunity_scanner(
        session=session,
        as_of=date.today(),
        universe=universe,
        sector=sector,
        horizon=horizon,
        score_min=score_min,
        score_max=score_max,
        risk_max=risk_max,
        confidence=confidence,
        factor=factor,
        valuation_status=valuation_status,
    )


@router.get("/{symbol}", response_model=ScannerItem)
def get_opportunity(symbol: str, session: Session = Depends(get_db)) -> ScannerItem:
    """Return one scanner item; numeric outputs remain null while inputs are insufficient."""
    response = build_opportunity_scanner(
        session=session,
        as_of=date.today(),
        universe="ALL",
        symbol=symbol,
    )
    if not response.results:
        raise HTTPException(status_code=404, detail=f"Active asset {symbol.upper()} was not found.")
    return response.results[0]
