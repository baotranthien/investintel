"""
Analyst Automation Router — Phase 6H endpoints.

Endpoints:
  GET  /api/v1/automation/briefs          — List stored briefs
  GET  /api/v1/automation/briefs/{id}     — Get a stored brief by ID
  GET  /api/v1/automation/alerts          — List generated analyst alerts
  GET  /api/v1/automation/alerts/{id}     — Get an alert by ID or alert_id
  GET  /api/v1/automation/jobs            — List automation job executions
  GET  /api/v1/automation/jobs/{id}       — Get a job by ID or job_key
  POST /api/v1/automation/trigger         — Run automation cycle on demand
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import AnalystAlert, AnalystAutomationJob, AnalystBrief
from services.ai.scheduler import run_analyst_automation_cycle
from services.ai.schemas import (
    AnalystAlertListResponse,
    AnalystAlertRead,
    AnalystBriefListResponse,
    AnalystBriefRead,
    AnalystJobListResponse,
    AnalystJobRead,
)

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


class TriggerRequest(BaseModel):
    as_of_date: Optional[date] = None


@router.get("/briefs", response_model=AnalystBriefListResponse)
def list_briefs(
    brief_type: Optional[str] = Query(default=None),
    as_of_date: Optional[date] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    query = session.query(AnalystBrief)
    if brief_type:
        query = query.filter(AnalystBrief.brief_type == brief_type.upper())
    if as_of_date:
        query = query.filter(AnalystBrief.as_of_date == as_of_date)
    if status:
        query = query.filter(AnalystBrief.status == status.upper())
    total = query.count()
    items = query.order_by(AnalystBrief.as_of_date.desc(), AnalystBrief.id.desc()).offset(offset).limit(limit).all()
    return AnalystBriefListResponse(
        total=total,
        items=[
            AnalystBriefRead(
                id=item.id,
                brief_type=item.brief_type,
                as_of_date=item.as_of_date,
                status=item.status,
                payload=item.payload,
                idempotency_key=item.idempotency_key,
                created_at=item.created_at,
            )
            for item in items
        ],
    )


@router.get("/briefs/{id}", response_model=AnalystBriefRead)
def get_brief(id: int, session: Session = Depends(get_db)):
    item = session.query(AnalystBrief).filter(AnalystBrief.id == id).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Analyst brief {id} not found")
    return AnalystBriefRead(
        id=item.id,
        brief_type=item.brief_type,
        as_of_date=item.as_of_date,
        status=item.status,
        payload=item.payload,
        idempotency_key=item.idempotency_key,
        created_at=item.created_at,
    )


@router.get("/alerts", response_model=AnalystAlertListResponse)
def list_alerts(
    symbol: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    query = session.query(AnalystAlert)
    if symbol:
        query = query.filter(AnalystAlert.symbol == symbol.upper())
    if kind:
        query = query.filter(AnalystAlert.kind == kind)
    if status:
        query = query.filter(AnalystAlert.status == status.upper())
    total = query.count()
    items = query.order_by(AnalystAlert.created_at.desc(), AnalystAlert.id.desc()).offset(offset).limit(limit).all()
    return AnalystAlertListResponse(
        total=total,
        items=[
            AnalystAlertRead(
                id=item.id,
                alert_id=item.alert_id,
                symbol=item.symbol,
                kind=item.kind,
                status=item.status,
                payload=item.payload,
                created_at=item.created_at,
                resolved_at=item.resolved_at,
            )
            for item in items
        ],
    )


@router.get("/alerts/{id}", response_model=AnalystAlertRead)
def get_alert(id: str, session: Session = Depends(get_db)):
    item = None
    if id.isdigit():
        item = session.query(AnalystAlert).filter(AnalystAlert.id == int(id)).first()
    if item is None:
        item = session.query(AnalystAlert).filter(AnalystAlert.alert_id == id).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Analyst alert {id} not found")
    return AnalystAlertRead(
        id=item.id,
        alert_id=item.alert_id,
        symbol=item.symbol,
        kind=item.kind,
        status=item.status,
        payload=item.payload,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
    )


@router.get("/jobs", response_model=AnalystJobListResponse)
def list_jobs(
    job_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    query = session.query(AnalystAutomationJob)
    if job_type:
        query = query.filter(AnalystAutomationJob.job_type == job_type)
    if status:
        query = query.filter(AnalystAutomationJob.status == status.upper())
    total = query.count()
    items = query.order_by(AnalystAutomationJob.started_at.desc(), AnalystAutomationJob.id.desc()).offset(offset).limit(limit).all()
    return AnalystJobListResponse(
        total=total,
        items=[
            AnalystJobRead(
                id=item.id,
                job_key=item.job_key,
                job_type=item.job_type,
                status=item.status,
                started_at=item.started_at,
                finished_at=item.finished_at,
                result=item.result,
                error=item.error,
            )
            for item in items
        ],
    )


@router.get("/jobs/{id}", response_model=AnalystJobRead)
def get_job(id: str, session: Session = Depends(get_db)):
    item = None
    if id.isdigit():
        item = session.query(AnalystAutomationJob).filter(AnalystAutomationJob.id == int(id)).first()
    if item is None:
        item = session.query(AnalystAutomationJob).filter(AnalystAutomationJob.job_key == id).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Analyst job {id} not found")
    return AnalystJobRead(
        id=item.id,
        job_key=item.job_key,
        job_type=item.job_type,
        status=item.status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        result=item.result,
        error=item.error,
    )


@router.post("/trigger")
async def trigger_cycle(
    req: TriggerRequest = TriggerRequest(),
    session: Session = Depends(get_db),
):
    """Trigger an analyst automation cycle manually."""
    results = await run_analyst_automation_cycle(
        session_factory=lambda: session,
        as_of=req.as_of_date,
    )
    return {"status": "SUCCESS", "results": results}
