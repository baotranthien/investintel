"""Authenticated, idempotent cron endpoints for cloud-scheduled execution."""
import datetime
import hmac
import logging
import os
from typing import Any, Optional
from fastapi import APIRouter, Body, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import AnalystAutomationJob
from services.ai.scheduler import run_analyst_automation_cycle
from services.ingestion.scheduler import run_ingestion_cycle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system/cron", tags=["cron"])


class CronTriggerRequest(BaseModel):
    as_of_date: Optional[str] = None  # Format: YYYY-MM-DD
    force: bool = False
    symbols: Optional[list[str]] = None
    providers: Optional[list[str]] = None


def _verify_cron_secret(x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")):
    """Verify cron caller using constant-time comparison against CRON_SECRET env var."""
    expected_secret = os.getenv("CRON_SECRET")
    if not expected_secret or not expected_secret.strip():
        logger.warning("CRON_SECRET is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cron scheduler secret is not configured on this server.",
        )

    if not x_cron_secret or not hmac.compare_digest(x_cron_secret.strip(), expected_secret.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Cron-Secret header.",
        )
    return True


def _sanitize(val: Any) -> Any:
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _sanitize(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize(x) for x in val]
    return val


def _get_target_date(date_str: Optional[str]) -> datetime.date:
    if date_str:
        try:
            return datetime.date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")
    # Vietnam timezone UTC+7
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    return datetime.datetime.now(vn_tz).date()


@router.get("/history")
async def get_cron_history(
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    limit: int = 20,
):
    """Inspect persisted cron execution history, idempotency records, and data runs."""
    _verify_cron_secret(x_cron_secret)
    db: Session = SessionLocal()
    try:
        from sqlalchemy import func
        from database.models import DataRun, Price
        jobs = db.query(AnalystAutomationJob).order_by(AnalystAutomationJob.started_at.desc()).limit(limit).all()
        runs = db.query(DataRun).order_by(DataRun.started_at.desc()).limit(limit).all()
        
        total_jobs = db.query(AnalystAutomationJob).count()
        success_jobs = db.query(AnalystAutomationJob).filter_by(status="SUCCESS").count()
        failed_jobs = db.query(AnalystAutomationJob).filter_by(status="FAILED").count()
        
        dup_query = db.query(Price.asset_id, Price.observation_date, func.count(Price.id)).group_by(Price.asset_id, Price.observation_date).having(func.count(Price.id) > 1).all()
        duplicate_prices_count = len(dup_query)
        total_prices = db.query(Price).count()
        
        return {
            "summary": {
                "total_jobs": total_jobs,
                "success_jobs": success_jobs,
                "failed_jobs": failed_jobs,
                "total_prices": total_prices,
                "duplicate_prices_count": duplicate_prices_count,
            },
            "recent_jobs": [
                {
                    "id": j.id,
                    "job_key": j.job_key,
                    "job_type": j.job_type,
                    "status": j.status,
                    "started_at": j.started_at.isoformat() if j.started_at else None,
                    "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                    "error": j.error,
                    "result": j.result,
                }
                for j in jobs
            ],
            "recent_runs": [
                {
                    "run_id": r.run_id,
                    "provider": r.provider,
                    "dataset": r.dataset,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "records_fetched": r.records_fetched,
                    "records_inserted": r.records_inserted,
                    "records_rejected": r.records_rejected,
                    "errors": r.errors,
                }
                for r in runs
            ],
        }
    finally:
        db.close()


@router.post("/run-ingestion")
async def run_cron_ingestion(
    request: Request,
    payload: Optional[CronTriggerRequest] = Body(None),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
):
    """Idempotent cron-triggered EOD market & macro ingestion."""
    _verify_cron_secret(x_cron_secret)

    body = payload or CronTriggerRequest()
    target_date = _get_target_date(body.as_of_date)
    sub_key = ""
    if body.providers:
        sub_key += f"_{'_'.join(sorted(p.upper() for p in body.providers))}"
    if body.symbols:
        sub_key += f"_{'_'.join(sorted(s.upper() for s in body.symbols))}"
    idempotency_key = f"INGEST{sub_key}_{target_date.isoformat()}" if sub_key else f"INGEST_EOD_{target_date.isoformat()}"

    db: Session = SessionLocal()
    try:
        # Check existing job
        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        if job and job.status == "SUCCESS" and not body.force:
            logger.info(f"Cron ingestion [{idempotency_key}] already completed. Skipping.")
            return {
                "status": "ALREADY_COMPLETED",
                "idempotency_key": idempotency_key,
                "as_of_date": target_date.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "message": "Ingestion cycle already succeeded for this date. Redundant execution skipped.",
            }

        # Create or update job to RUNNING
        if not job:
            job = AnalystAutomationJob(
                job_key=idempotency_key,
                job_type="INGESTION_EOD",
                status="RUNNING",
                started_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(job)
        else:
            job.status = "RUNNING"
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
            job.finished_at = None
            job.error = None
        db.commit()

        # Execute existing ingestion cycle with targeted filters if provided
        run_results = await run_ingestion_cycle(
            session_factory=SessionLocal,
            target_symbols=body.symbols,
            target_providers=body.providers,
        )

        # Update job status honestly
        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        is_blocked = any(r.get("status") == "BLOCKED_FLAG_DISABLED" for r in run_results)
        has_success = any(r.get("status") == "SUCCESS" for r in run_results)

        job.status = "SUCCESS" if has_success else ("BLOCKED" if is_blocked else ("PARTIAL" if run_results else "SUCCESS"))
        job.finished_at = datetime.datetime.now(datetime.timezone.utc)
        job.result = _sanitize({"results": run_results, "total_providers": len(run_results)})
        if is_blocked and not has_success:
            job.error = "ENABLE_LOTUSMARKET_INGESTION is not enabled in environment."
        db.commit()

        return {
            "status": "SUCCESS",
            "idempotency_key": idempotency_key,
            "as_of_date": target_date.isoformat(),
            "results_count": len(run_results),
            "results": run_results,
        }

    except Exception as exc:
        db.rollback()
        logger.exception(f"Cron ingestion failed for [{idempotency_key}]: {exc}")
        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        if job:
            job.status = "FAILED"
            job.finished_at = datetime.datetime.now(datetime.timezone.utc)
            job.error = str(exc)[:4000]
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        )
    finally:
        db.close()


@router.post("/run-analyst")
async def run_cron_analyst(
    request: Request,
    payload: Optional[CronTriggerRequest] = Body(None),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
):
    """Idempotent cron-triggered analyst briefs and thesis review."""
    _verify_cron_secret(x_cron_secret)

    body = payload or CronTriggerRequest()
    target_date = _get_target_date(body.as_of_date)
    idempotency_key = f"DAILY_BRIEF_{target_date.isoformat()}"

    db: Session = SessionLocal()
    try:
        # Check existing job
        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        if job and job.status == "SUCCESS" and not body.force:
            logger.info(f"Cron analyst [{idempotency_key}] already completed. Skipping.")
            return {
                "status": "ALREADY_COMPLETED",
                "idempotency_key": idempotency_key,
                "as_of_date": target_date.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "message": "Analyst brief already succeeded for this date. Redundant execution skipped.",
            }

        if not job:
            job = AnalystAutomationJob(
                job_key=idempotency_key,
                job_type="DAILY_BRIEF",
                status="RUNNING",
                started_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(job)
        else:
            job.status = "RUNNING"
            job.started_at = datetime.datetime.now(datetime.timezone.utc)
            job.finished_at = None
            job.error = None
        db.commit()

        # Execute existing analyst automation cycle
        analyst_results = await run_analyst_automation_cycle(
            session_factory=SessionLocal,
            as_of=target_date,
        )

        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        job.status = "SUCCESS"
        job.finished_at = datetime.datetime.now(datetime.timezone.utc)
        job.result = _sanitize({"results": analyst_results})
        db.commit()

        return {
            "status": "SUCCESS",
            "idempotency_key": idempotency_key,
            "as_of_date": target_date.isoformat(),
            "results": analyst_results,
        }

    except Exception as exc:
        db.rollback()
        logger.exception(f"Cron analyst failed for [{idempotency_key}]: {exc}")
        job = db.query(AnalystAutomationJob).filter_by(job_key=idempotency_key).first()
        if job:
            job.status = "FAILED"
            job.finished_at = datetime.datetime.now(datetime.timezone.utc)
            job.error = str(exc)[:4000]
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analyst automation failed: {exc}",
        )
    finally:
        db.close()
