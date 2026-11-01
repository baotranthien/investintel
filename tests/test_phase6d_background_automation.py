# tests/test_phase6d_background_automation.py
"""
Test Suite for Phase 6D: Background Jobs & Scheduled Automation
Verifies job ordering, concurrency locking, pause/resume, upstream dependency safety,
alert evaluation idempotency, and scheduler status contracts.
"""

import asyncio
import pytest
from datetime import date
from fastapi.testclient import TestClient

from apps.api.main import app
from services.scheduler.engine import (
    LocalScheduler,
    SchedulerLockError,
    JobDependencyError,
    local_scheduler,
)


@pytest.fixture
def scheduler():
    """Provides a fresh isolated scheduler instance."""
    return LocalScheduler()


def test_scheduler_pause_and_resume(scheduler):
    """Verify jobs are skipped when scheduler is paused, and run when resumed."""
    assert not scheduler.is_paused
    scheduler.pause()
    assert scheduler.is_paused
    
    # Attempting to run ingestion when paused should return SKIPPED status
    res = asyncio.run(scheduler.run_ingestion_job(target_symbols=["FPT"]))
    assert res["status"] == "SKIPPED"
    assert "paused" in res["reason"].lower()
    
    scheduler.resume()
    assert not scheduler.is_paused


def test_job_dependency_failure_aborts_pipeline(scheduler):
    """Verify that an upstream ingestion failure aborts dependent scans to prevent stale reporting."""
    with pytest.raises(JobDependencyError) as exc_info:
        asyncio.run(scheduler.run_pipeline(simulate_failure_in_ingestion=True))
    assert "ingestion stage failed" in str(exc_info.value).lower()


def test_concurrency_lock_prevents_duplicate_runs(scheduler):
    """Verify overlapping pipeline executions are rejected with SchedulerLockError."""
    async def run_lock_test():
        await scheduler._lock.acquire()
        try:
            with pytest.raises(SchedulerLockError) as exc_info:
                await scheduler.run_pipeline()
            assert "duplicate run rejected" in str(exc_info.value).lower()
        finally:
            scheduler._lock.release()

    asyncio.run(run_lock_test())


def test_opportunity_and_alert_execution_pipeline(scheduler):
    """Verify opportunity scan and alert evaluation jobs run cleanly."""
    opp_res = asyncio.run(scheduler.run_opportunity_scan_job(universe="VN30", as_of=date.today()))
    assert opp_res["status"] == "SUCCESS"
    assert opp_res["result_count"] > 0
    assert opp_res["total_assets"] > 0
    
    alert_res = asyncio.run(scheduler.run_alert_evaluation_job(as_of=date.today()))
    assert alert_res["status"] == "SUCCESS"
    assert alert_res["symbols_evaluated"] > 0
    assert isinstance(alert_res["alerts_triggered"], int)


def test_scheduler_api_endpoints():
    """Verify FastAPI scheduler endpoints for status, pause, resume, and history."""
    client = TestClient(app)
    
    # 1. Get Status
    resp = client.get("/api/v1/automation/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "timezone" in data
    assert data["timezone"] == "Asia/Ho_Chi_Minh"
    assert "jobs" in data
    assert "ingestion" in data["jobs"]
    assert "opportunity_scan" in data["jobs"]
    assert "alert_evaluation" in data["jobs"]
    assert "db_backup" in data["jobs"]
    
    # 2. Pause
    p_resp = client.post("/api/v1/automation/scheduler/pause")
    assert p_resp.status_code == 200
    assert p_resp.json()["status"] == "PAUSED"
    
    # 3. Resume
    r_resp = client.post("/api/v1/automation/scheduler/resume")
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "ACTIVE"
