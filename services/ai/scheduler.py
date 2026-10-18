from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import AnalystAlert, AnalystAutomationJob, AnalystBrief, Asset, WatchlistItem
from services.ai.analyst import AIAnalyst
from services.ai.automation import AnalystAutomationService
from services.ai.tools import AITools

logger = logging.getLogger(__name__)


async def _run_brief(session: Session, analyst: AIAnalyst, brief_type: str, as_of: date) -> dict[str, Any]:
    method = {
        "DAILY": analyst.generate_daily_brief,
        "WEEKLY": analyst.generate_weekly_brief,
        "MONTHLY": analyst.generate_monthly_brief,
    }[brief_type]
    return await method(session, as_of=as_of)


def _claim_job(session: Session, job_type: str, job_key: str) -> AnalystAutomationJob | None:
    job = session.query(AnalystAutomationJob).filter_by(job_key=job_key).first()
    if job and job.status == "SUCCESS":
        return None
    if job and job.status == "RUNNING":
        now = datetime.now(timezone.utc)
        started = job.started_at
        if started:
            started_utc = started if started.tzinfo else started.replace(tzinfo=timezone.utc)
            if (now - started_utc).total_seconds() < 300:
                return None
    if job is None:
        job = AnalystAutomationJob(job_key=job_key, job_type=job_type, status="RUNNING")
        session.add(job)
    else:
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = None
        job.error = None
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        job = session.query(AnalystAutomationJob).filter_by(job_key=job_key).first()
        if job is None or job.status == "SUCCESS":
            return None
        if job.status == "RUNNING":
            now = datetime.now(timezone.utc)
            started = job.started_at
            if started:
                started_utc = started if started.tzinfo else started.replace(tzinfo=timezone.utc)
                if (now - started_utc).total_seconds() < 300:
                    return None
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        session.commit()
    return job


def _finish_job(
    session: Session,
    job: AnalystAutomationJob,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    status: str | None = None,
) -> None:
    if status:
        job.status = status
    elif error:
        job.status = "FAILED"
    else:
        job.status = "SUCCESS"
    job.result = result
    job.error = error[:4000] if error else None
    job.finished_at = datetime.now(timezone.utc)
    session.commit()


def _metric_snapshot(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tools = {item.get("name"): item.get("data") for item in context.get("tools", [])}
    evidence = context.get("evidence", [])
    snapshot: dict[str, dict[str, Any]] = {}
    for name, value_key in (("valuation", "score"), ("risk", "overall_score"), ("opportunity", "score")):
        data = tools.get(name)
        if not isinstance(data, dict):
            continue
        value = data.get(value_key)
        if value is None and value_key != "score":
            value = data.get("score")
        related = [
            item for item in evidence
            if str(item.get("responsible_module", "")).casefold() == name
            and AnalystAutomationService._is_evidence_usable(item)
        ]
        sources = sorted({item.get("source") for item in related if item.get("source")})
        if value is not None and len(sources) == 1:
            snapshot[name] = {"score": value, "source": sources[0]}
    return snapshot


async def run_analyst_automation_cycle(
    session_factory: Callable[[], Session] = SessionLocal,
    *,
    as_of: date | None = None,
    analyst: AIAnalyst | None = None,
) -> list[dict[str, Any]]:
    """Run due briefs, source-backed thesis reviews, and deduplicated watchlist alerts."""
    today = as_of or date.today()
    analyst = analyst or AIAnalyst()
    results: list[dict[str, Any]] = []

    due_briefs = ["DAILY"]
    if today.weekday() == 0:
        due_briefs.append("WEEKLY")
    if today.day == 1:
        due_briefs.append("MONTHLY")

    for brief_type in due_briefs:
        job_key = f"brief:{brief_type}:{today.isoformat()}"
        session = session_factory()
        try:
            job = _claim_job(session, f"{brief_type}_BRIEF", job_key)
            if job is None:
                results.append({"job_key": job_key, "status": "SKIPPED", "reason": "Already running or completed"})
                continue
            try:
                payload = await _run_brief(session, analyst, brief_type, today)
                brief_key = f"scheduled:{brief_type}:{today.isoformat()}"
                brief = AnalystAutomationService(session).persist_brief(brief_type, today, payload, idempotency_key=brief_key)
                job = session.query(AnalystAutomationJob).filter_by(job_key=job_key).one()
                _finish_job(session, job, result={"brief_id": brief.id, "brief_status": brief.status})
                results.append({"job_key": job_key, "status": "SUCCESS", "brief_id": brief.id, "brief_status": brief.status})
            except Exception as error:
                session.rollback()
                job = session.query(AnalystAutomationJob).filter_by(job_key=job_key).one()
                _finish_job(session, job, error=str(error), status="FAILED")
                logger.exception("Analyst brief job failed: %s", job_key)
                results.append({"job_key": job_key, "status": "FAILED", "reason": str(error)})
        finally:
            session.close()

    monitor_key = f"thesis-review:{today.isoformat()}"
    session = session_factory()
    try:
        job = _claim_job(session, "THESIS_REVIEW", monitor_key)
        if job is None:
            results.append({"job_key": monitor_key, "status": "SKIPPED", "reason": "Already running or completed"})
        else:
            item_rows = session.query(WatchlistItem, Asset).join(Asset, WatchlistItem.asset_id == Asset.id).all()
            reviewed = []
            for item, asset in item_rows:
                context = AITools.get_context(asset.symbol, today, ["evidence"], session)
                review = AnalystAutomationService(session).monitor_thesis(
                    item,
                    evidence=context.get("evidence", []),
                    contradicting_evidence=[],
                    catalysts=[],
                    invalidation=item.invalidation,
                    confidence=0.0,
                )
                reviewed.append({"symbol": asset.symbol, "status": review["status"], "updated": review["updated"]})
            job = session.query(AnalystAutomationJob).filter_by(job_key=monitor_key).one()
            _finish_job(session, job, result={"reviews": reviewed})
            results.append({"job_key": monitor_key, "status": "SUCCESS", "reviews": len(reviewed)})
    except Exception as error:
        session.rollback()
        job = session.query(AnalystAutomationJob).filter_by(job_key=monitor_key).first()
        if job:
            _finish_job(session, job, error=str(error), status="FAILED")
        logger.exception("Thesis review job failed")
        results.append({"job_key": monitor_key, "status": "FAILED", "reason": str(error)})
    finally:
        session.close()

    alert_key = f"alert-scan:{today.isoformat()}"
    session = session_factory()
    try:
        job = _claim_job(session, "ALERT_SCAN", alert_key)
        if job is None:
            results.append({"job_key": alert_key, "status": "SKIPPED", "reason": "Already running or completed"})
        else:
            previous_job = session.query(AnalystAutomationJob).filter(
                AnalystAutomationJob.job_type == "ALERT_SCAN",
                AnalystAutomationJob.status == "SUCCESS",
                AnalystAutomationJob.job_key != alert_key,
            ).order_by(AnalystAutomationJob.started_at.desc()).first()
            previous_snapshots = (previous_job.result or {}).get("snapshots", {}) if previous_job else {}
            current_snapshots: dict[str, Any] = {}
            created = 0
            rows = session.query(WatchlistItem, Asset).join(Asset, WatchlistItem.asset_id == Asset.id).all()
            for _, asset in rows:
                context = AITools.get_context(asset.symbol, today, ["valuation", "risk", "opportunity", "evidence"], session)
                current = _metric_snapshot(context)
                current_snapshots[asset.symbol] = current
                prior = session.query(AnalystAlert).filter_by(symbol=asset.symbol, status="OPEN").all()
                alerts = AnalystAutomationService.evaluate_alerts(
                    current,
                    previous=previous_snapshots.get(asset.symbol),
                    evidence=context.get("evidence", []),
                    prior_alerts=[{"alert_id": alert.alert_id} for alert in prior],
                )
                for alert in alerts:
                    session.add(AnalystAlert(
                        alert_id=alert["alert_id"],
                        symbol=asset.symbol,
                        kind=alert["kind"],
                        status=alert["status"],
                        payload=alert,
                    ))
                    created += 1
            session.flush()
            job = session.query(AnalystAutomationJob).filter_by(job_key=alert_key).one()
            _finish_job(session, job, result={"snapshots": current_snapshots, "alerts_created": created})
            results.append({"job_key": alert_key, "status": "SUCCESS", "alerts_created": created})
    except Exception as error:
        session.rollback()
        job = session.query(AnalystAutomationJob).filter_by(job_key=alert_key).first()
        if job:
            _finish_job(session, job, error=str(error), status="FAILED")
        logger.exception("Analyst alert scan failed")
        results.append({"job_key": alert_key, "status": "FAILED", "reason": str(error)})
    finally:
        session.close()

    return results


async def scheduled_analyst_automation_loop(stop_event: asyncio.Event) -> None:
    initial_delay = max(0, int(os.getenv("ANALYST_AUTOMATION_INITIAL_DELAY_SECONDS", "30")))
    interval = max(60, int(os.getenv("ANALYST_AUTOMATION_INTERVAL_SECONDS", "3600")))
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        try:
            results = await run_analyst_automation_cycle()
            logger.info("Scheduled analyst automation cycle completed: %s", results)
        except Exception:
            logger.exception("Scheduled analyst automation cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
