"""
InvestIntel Local Automation & Background Scheduler Engine
Phase 6D: Scheduled Ingestion, Opportunity Scanning, Alert Deduplication & Safety Lifecycles.
Timezone: Asia/Ho_Chi_Minh
"""

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from database.connection import SessionLocal
from database.models import Asset, WatchlistItem
from services.alerts.engine import InvestmentAlertsEngine
from services.db.backup import create_backup
from services.opportunity.scanner import OpportunityScannerResponse, build_opportunity_scanner

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_FILE = PROJECT_ROOT / ".run" / "job_history.json"
LOCK_FILE = PROJECT_ROOT / ".run" / "scheduler.lock"


class SchedulerLockError(RuntimeError):
    """Raised when an attempt is made to execute an overlapping job."""
    pass


class JobDependencyError(RuntimeError):
    """Raised when an upstream dependency fails in the pipeline."""
    pass


class LocalScheduler:
    """Manages scheduled background automation for the local InvestIntel stack."""

    def __init__(self):
        self._is_paused = False
        self._is_running = False
        self._lock = asyncio.Lock()
        self.jobs = {
            "ingestion": {
                "name": "Financial Data Ingestion",
                "schedule": "Daily 16:00 ICT",
                "enabled": True,
                "last_run": None,
                "next_run": None,
                "status": "IDLE",
                "retry_count": 0,
            },
            "opportunity_scan": {
                "name": "Institutional Opportunity Scan",
                "schedule": "Post-Ingestion",
                "enabled": True,
                "last_run": None,
                "next_run": None,
                "status": "IDLE",
                "retry_count": 0,
            },
            "alert_evaluation": {
                "name": "Investment Alerts Evaluation",
                "schedule": "Post-Opportunity",
                "enabled": True,
                "last_run": None,
                "next_run": None,
                "status": "IDLE",
                "retry_count": 0,
            },
            "db_backup": {
                "name": "SQLite Hot Backup",
                "schedule": "Daily 18:00 ICT",
                "enabled": True,
                "last_run": None,
                "next_run": None,
                "status": "IDLE",
                "retry_count": 0,
            },
        }

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def pause(self) -> None:
        self._is_paused = True
        logger.info("Local scheduler paused.")

    def resume(self) -> None:
        self._is_paused = False
        logger.info("Local scheduler resumed.")

    def _record_history(self, record: Dict[str, Any]) -> None:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            history = []
            if HISTORY_FILE.exists():
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except Exception:
                    history = []
            history.insert(0, record)
            # Retain last 50 executions
            history = history[:50]
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not record job history: {e}")

    async def run_ingestion_job(self, target_symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Runs financial data ingestion with retry and failure recording."""
        if self._is_paused:
            return {"status": "SKIPPED", "reason": "Scheduler is paused"}

        job_meta = self.jobs["ingestion"]
        job_meta["status"] = "RUNNING"
        t0 = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()

        try:
            from services.ingestion.scheduler import run_ingestion_cycle
            symbols = target_symbols or ["FPT", "BMP", "VCB", "MBB", "MWG", "HPG"]
            results = await run_ingestion_cycle(target_symbols=symbols)
            duration = round(time.time() - t0, 3)

            job_meta["status"] = "SUCCESS"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] = 0

            history_entry = {
                "job_id": "ingestion",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "SUCCESS",
                "symbols_processed": len(symbols),
                "runs_recorded": len(results),
            }
            self._record_history(history_entry)
            return history_entry
        except Exception as e:
            duration = round(time.time() - t0, 3)
            job_meta["status"] = "FAILED"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] += 1

            history_entry = {
                "job_id": "ingestion",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "FAILED",
                "error": str(e),
            }
            self._record_history(history_entry)
            raise

    async def run_opportunity_scan_job(self, universe: str = "VN30", as_of: Optional[date] = None) -> Dict[str, Any]:
        """Runs opportunity scanning across universe after ingestion."""
        if self._is_paused:
            return {"status": "SKIPPED", "reason": "Scheduler is paused"}

        job_meta = self.jobs["opportunity_scan"]
        job_meta["status"] = "RUNNING"
        t0 = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()
        as_of = as_of or date.today()

        session = SessionLocal()
        try:
            resp = build_opportunity_scanner(
                session=session,
                as_of=as_of,
                universe=universe,
                horizon="MEDIUM_TERM",
            )
            duration = round(time.time() - t0, 3)
            job_meta["status"] = "SUCCESS"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] = 0

            history_entry = {
                "job_id": "opportunity_scan",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "SUCCESS",
                "universe": universe,
                "result_count": resp.result_count,
                "total_assets": resp.total_assets,
            }
            self._record_history(history_entry)
            return history_entry
        except Exception as e:
            duration = round(time.time() - t0, 3)
            job_meta["status"] = "FAILED"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] += 1

            history_entry = {
                "job_id": "opportunity_scan",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "FAILED",
                "error": str(e),
            }
            self._record_history(history_entry)
            raise
        finally:
            session.close()

    async def run_alert_evaluation_job(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        """Evaluates alerts with deterministic deduplication across core tickers."""
        if self._is_paused:
            return {"status": "SKIPPED", "reason": "Scheduler is paused"}

        job_meta = self.jobs["alert_evaluation"]
        job_meta["status"] = "RUNNING"
        t0 = time.time()
        start_dt = datetime.now(timezone.utc).isoformat()
        as_of = as_of or date.today()

        session = SessionLocal()
        try:
            engine = InvestmentAlertsEngine(session)
            
            # Target universe: Watchlist assets + active stocks
            wl_items = session.query(Asset.symbol).join(WatchlistItem, WatchlistItem.asset_id == Asset.id).distinct().all()
            target_symbols = {w[0] for w in wl_items}
            # Fallback to key symbols if watchlist is empty
            if not target_symbols:
                target_symbols = {"BMP", "FPT", "VCB", "MBB", "HPG"}

            total_alerts = 0
            alert_details = []
            for sym in target_symbols:
                alerts = engine.evaluate_symbol(sym, as_of=as_of)
                for a in alerts:
                    total_alerts += 1
                    alert_details.append({
                        "symbol": a.symbol,
                        "type": a.alert_type,
                        "severity": a.severity,
                        "title": a.title,
                    })

            duration = round(time.time() - t0, 3)
            job_meta["status"] = "SUCCESS"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] = 0

            history_entry = {
                "job_id": "alert_evaluation",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "SUCCESS",
                "symbols_evaluated": len(target_symbols),
                "alerts_triggered": total_alerts,
                "alerts": alert_details[:10],
            }
            self._record_history(history_entry)
            return history_entry
        except Exception as e:
            duration = round(time.time() - t0, 3)
            job_meta["status"] = "FAILED"
            job_meta["last_run"] = start_dt
            job_meta["retry_count"] += 1

            history_entry = {
                "job_id": "alert_evaluation",
                "started_at": start_dt,
                "duration_sec": duration,
                "status": "FAILED",
                "error": str(e),
            }
            self._record_history(history_entry)
            raise
        finally:
            session.close()

    async def run_pipeline(
        self,
        target_symbols: Optional[List[str]] = None,
        as_of: Optional[date] = None,
        simulate_failure_in_ingestion: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes the full dependency-ordered automation pipeline:
        Ingestion -> Opportunity Scan -> Alert Evaluation -> Backup
        
        Strict safety: If ingestion fails, dependent scans are aborted immediately.
        Duplicate run prevention: Rejects execution if a pipeline run is already active.
        """
        if self._lock.locked():
            raise SchedulerLockError("A background automation pipeline is already executing. Duplicate run rejected.")

        async with self._lock:
            pipeline_start = time.time()
            results: Dict[str, Any] = {"pipeline_status": "RUNNING", "stages": {}}

            # Stage 1: Ingestion
            if simulate_failure_in_ingestion:
                results["stages"]["ingestion"] = {"status": "FAILED", "error": "Simulated upstream provider timeout"}
                results["pipeline_status"] = "FAILED"
                results["stages"]["opportunity_scan"] = {"status": "ABORTED", "reason": "Upstream ingestion failed"}
                results["stages"]["alert_evaluation"] = {"status": "ABORTED", "reason": "Upstream ingestion failed"}
                raise JobDependencyError("Pipeline aborted: Ingestion stage failed. Preserving data integrity.")
            else:
                ingest_res = await self.run_ingestion_job(target_symbols=target_symbols)
                results["stages"]["ingestion"] = ingest_res

            # Stage 2: Opportunity Scan (Depends on Ingestion)
            opp_res = await self.run_opportunity_scan_job(as_of=as_of)
            results["stages"]["opportunity_scan"] = opp_res

            # Stage 3: Alert Evaluation (Depends on Opportunity & Fresh Data)
            alert_res = await self.run_alert_evaluation_job(as_of=as_of)
            results["stages"]["alert_evaluation"] = alert_res

            # Stage 4: Database Hot Backup
            try:
                backup_res = create_backup(description="Automated post-pipeline scheduled backup")
                results["stages"]["db_backup"] = {
                    "status": "SUCCESS",
                    "backup_filename": backup_res["backup_filename"],
                    "sha256": backup_res["sha256"],
                    "integrity": backup_res["integrity"],
                }
            except Exception as e:
                results["stages"]["db_backup"] = {"status": "FAILED", "error": str(e)}

            results["pipeline_status"] = "SUCCESS"
            results["total_duration_sec"] = round(time.time() - pipeline_start, 3)
            return results

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of the scheduler and its managed jobs."""
        history = []
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)[:10]
            except Exception:
                pass

        return {
            "scheduler_paused": self._is_paused,
            "is_busy": self._lock.locked(),
            "timezone": "Asia/Ho_Chi_Minh",
            "jobs": self.jobs,
            "recent_executions": history,
        }


# Global singleton instance
local_scheduler = LocalScheduler()
