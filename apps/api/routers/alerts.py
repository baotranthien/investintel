# -*- coding: utf-8 -*-
"""
Investment Alerts Router — Phase 5F.
Provides active fundamental monitoring, threshold breaches, and risk notification management.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import AnalystAlert
from services.alerts.engine import AlertRuleResult, InvestmentAlertsEngine

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertRuleResult])
def list_investment_alerts(
    symbol: Optional[str] = Query(None, description="Filter by stock ticker"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    limit: int = Query(50, ge=1, le=100),
    session: Session = Depends(get_db),
) -> List[AlertRuleResult]:
    """List generated investment alerts from database."""
    query = session.query(AnalystAlert)
    if symbol:
        query = query.filter(AnalystAlert.symbol == symbol.upper())
    if alert_type:
        query = query.filter(AnalystAlert.kind == alert_type.upper())

    rows = query.order_by(AnalystAlert.created_at.desc()).limit(limit).all()
    results = []
    for r in rows:
        payload = r.payload or {}
        results.append(AlertRuleResult(
            symbol=r.symbol,
            alert_type=r.kind,
            severity=payload.get("severity", "MEDIUM"),
            title=payload.get("title", f"Alert for {r.symbol}"),
            description=payload.get("description", ""),
            metrics=payload.get("metrics", {}),
            triggered_at=r.created_at,
            status=r.status,
        ))
    return results


@router.get("/{symbol}", response_model=List[AlertRuleResult])
def evaluate_symbol_alerts(
    symbol: str,
    as_of: date = Query(default_factory=date.today),
    session: Session = Depends(get_db),
) -> List[AlertRuleResult]:
    """Evaluate and return live alerts for a specific company."""
    engine = InvestmentAlertsEngine(session)
    return engine.evaluate_symbol(symbol, as_of=as_of)


@router.post("/scan", response_model=List[AlertRuleResult])
def run_alert_scan(
    limit: int = Query(20, ge=1, le=50),
    as_of: date = Query(default_factory=date.today),
    session: Session = Depends(get_db),
) -> List[AlertRuleResult]:
    """Run cross-asset alert evaluation across active universe."""
    engine = InvestmentAlertsEngine(session)
    return engine.scan_active_universe(as_of=as_of, limit=limit)


@router.patch("/{alert_id}/dismiss")
def dismiss_alert(alert_id: str, session: Session = Depends(get_db)):
    """Dismiss or resolve an active alert."""
    alert = session.query(AnalystAlert).filter(AnalystAlert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    alert.status = "DISMISSED"
    session.commit()
    return {"status": "success", "alert_id": alert_id, "state": "DISMISSED"}

