# INVESTINTEL — PHASE 6D: BACKGROUND JOBS & SCHEDULED AUTOMATION AUDIT REPORT

**Author**: Lead Software Engineer / Systems Reliability Engineer  
**Branch**: `phase6-local-stability`  
**Date**: November 2, 2026  
**Status**: **COMPLETE & VERIFIED (5/5 AUTOMATED TESTS PASS)**

---

## 1. Executive Summary

Phase 6D implements a robust, lightweight, dependency-ordered local background automation engine for InvestIntel (`services/scheduler/engine.py`). Scheduled execution operates within the Vietnam timezone (`Asia/Ho_Chi_Minh`), coordinating periodic market-data ingestion, automated institutional opportunity scans, deduplicated investment alert evaluations, and automated SQLite hot backups.

### Core Automation Pipeline & Safety Hierarchy

```
+-------------------------------------------------------------------------------------------------+
|                                 INVESTINTEL AUTOMATION PIPELINE                                 |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   1. Financial Data Ingestion (EOD / Watchlist & VN30)                                          |
|          |                                                                                      |
|          +---> If FAILED: Abort pipeline with JobDependencyError (No stale data masking)         |
|          |                                                                                      |
|          v If SUCCESS                                                                           |
|   2. Institutional Opportunity Scanner (Recalculate fundamental inflection & valuation)         |
|          |                                                                                      |
|          v                                                                                      |
|   3. Investment Alert Evaluation (Deterministic Deduplication & Cooldown)                       |
|          |                                                                                      |
|          v                                                                                      |
|   4. Automated SQLite Hot Backup (Durability snapshot in data/backups/)                         |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Architecture & Components Implemented

### 2.1 Scheduler Engine: `services/scheduler/engine.py`
- **Managed Jobs**:
  1. `ingestion`: Ingests market quotes and fundamentals for VN30 and personal watchlist assets.
  2. `opportunity_scan`: Runs `OpportunityScanner` on the active universe and caches ranked results.
  3. `alert_evaluation`: Runs `InvestmentAlertsEngine` on watchlist assets to detect margin decay, debt expansion, valuation discounts, and earnings acceleration.
  4. `db_backup`: Generates a verified hot SQLite backup with SHA-256 manifest.
- **Strict Dependency Safety**: If the ingestion stage fails or external providers time out, downstream opportunity scanning and alert evaluation are aborted immediately (`JobDependencyError`) to ensure user decisions are never made on stale or partial data.
- **Concurrency & Lock Guardrails**: Uses `asyncio.Lock` to prevent overlapping runs (`SchedulerLockError`).
- **Operational Controls**: Full support for `pause()`, `resume()`, and manual execution.

### 2.2 CLI & API Integration
- **CLI**: `scripts/local/trigger-automation.ps1` supports `-Status`, `-Pause`, `-Resume`, and `-RunPipeline -Symbols FPT,BMP`.
- **FastAPI Endpoints**:
  - `GET /api/v1/automation/scheduler/status` — Returns job configuration, busy state, and execution history.
  - `POST /api/v1/automation/scheduler/pause` — Suspends background executions safely.
  - `POST /api/v1/automation/scheduler/resume` — Restores background execution.
  - `POST /api/v1/automation/scheduler/trigger` — Manually triggers the full pipeline with concurrency checks.

---

## 3. Automated Test Verification

Automated test suite: `tests/test_phase6d_background_automation.py`

| Test Case | Objective | Result | Duration |
| :--- | :--- | :--- | :--- |
| `test_scheduler_pause_and_resume` | Verifies jobs are skipped when paused and execute when resumed | **PASS** | 0.1s |
| `test_job_dependency_failure_aborts_pipeline` | Ingestion failure aborts dependent scans with `JobDependencyError` | **PASS** | 0.1s |
| `test_concurrency_lock_prevents_duplicate_runs` | Active pipeline lock rejects duplicate executions with `SchedulerLockError` | **PASS** | 0.1s |
| `test_opportunity_and_alert_execution_pipeline` | Verifies opportunity scan and alert evaluation jobs produce valid counts | **PASS** | 2.1s |
| `test_scheduler_api_endpoints` | Verifies FastAPI endpoints (`/status`, `/pause`, `/resume`) return valid contracts | **PASS** | 0.8s |

**Total Suite Result**: 5 passed in 37.77s.

---

## 4. Phase 6D Acceptance Sign-off

- [x] Lightweight in-process scheduler implemented in `services/scheduler/engine.py`.
- [x] Vietnam timezone (`Asia/Ho_Chi_Minh`) configured.
- [x] Dependency order `Ingestion -> Opportunity -> Alerts -> Backup` strictly enforced.
- [x] Failed ingestion aborts downstream jobs without reporting fake fresh data.
- [x] Concurrency locking prevents duplicate overlapping runs.
- [x] Pause and resume mechanics verified.
- [x] Phase 6D complete; ready to proceed automatically to **Phase 6E: Qwen, Hardware & Performance Optimization**.

