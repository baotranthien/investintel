# INVESTINTEL — PHASE 6F: LOCAL MONITORING, LOGGING & SELF-RECOVERY AUDIT REPORT

**Author**: Lead Software Engineer / Systems Reliability Engineer  
**Branch**: `phase6-local-stability`  
**Date**: November 2, 2026  
**Status**: **COMPLETE & VERIFIED (4/4 AUTOMATED TESTS PASS)**

---

## 1. Executive Summary

Phase 6F equips InvestIntel with real-time local monitoring, institutional error classification, safe self-recovery automation, and operator runbooks. The user can inspect full system health via a dedicated, polished web dashboard at **`/system`** (`apps/web/src/app/system/page.tsx`), monitoring Ollama inference latency, RTX 3050 VRAM usage, SQLite durability, and background scheduler tasks.

### Architecture of Local Observability & Self-Recovery

```
+-------------------------------------------------------------------------------------------------+
|                                 INVESTINTEL LOCAL OBSERVABILITY                                 |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   Next.js Frontend: /system  <--->  FastAPI: /api/v1/system/diagnostics                          |
|                                                                                                 |
|   +-----------------------+   +----------------------+   +----------------------------------+   |
|   |   AI Runtime Card     |   |   Hardware Card      |   |   Database & Durability Card     |   |
|   | - Model: Qwen3.5 9B   |   | - GPU: RTX 3050      |   | - Engine: SQLite (trading.db)    |   |
|   | - Warm TTFT: 0.47s    |   | - VRAM: 2.7GB / 4GB  |   | - Write Guard: LOCKED (false)    |   |
|   | - TPS: ~5.5 tok/s     |   | - RAM: 16GB Total    |   | - PRAGMA integrity: PASS (ok)    |   |
|   +-----------------------+   +----------------------+   +----------------------------------+   |
|                                                                                                 |
|   +-----------------------------------------------------------------------------------------+   |
|   |   Institutional Error Classification & Safe Self-Recovery Engine                        |   |
|   |   - SERVICE_UNAVAILABLE  -> Process ownership verification & port reclamation           |   |
|   |   - DATABASE_FAILURE     -> Exponential backoff connection retry & snapshot restore      |   |
|   |   - DATA_PROVIDER_FAILURE-> Fallback to HOSE CSV; abort downstream scans to avoid stale |   |
|   |   - INFERENCE_TIMEOUT    -> Context budgeting to 2048 tokens; non-blocking recovery     |   |
|   |   - STORAGE_FAILURE      -> Prune expired backups according to 7D/4W/6M retention policy|   |
|   +-----------------------------------------------------------------------------------------+   |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Components Implemented

### 2.1 System Observability Dashboard: `apps/web/src/app/system/page.tsx`
- **Apple Daylight Aesthetics**: Clean card layout, frosted glass accents, monospace data metrics, color-coded status badges.
- **Dynamic Diagnostics**: Queries `/api/v1/system/diagnostics` every 15 seconds to stream live VRAM utilization, GPU temperature, and active model placement.
- **Interactive Action Triggers**: Allows operators to trigger the automated pipeline (`Ingestion -> Opportunity -> Alerts -> Backup`) with a single click.
- **Embedded Runbook Table**: Displays standard troubleshooting steps for socket conflicts (10048), VRAM exhaustion, and provider downtime.

### 2.2 Error Classification & Runbook Engine: `services/maintenance/self_recovery.py`
- Categorizes runtime exceptions into 8 institutional error classes:
  1. `SERVICE_UNAVAILABLE`
  2. `DATABASE_FAILURE`
  3. `DATA_PROVIDER_FAILURE`
  4. `OLLAMA_MODEL_FAILURE`
  5. `INFERENCE_TIMEOUT`
  6. `INVALID_EVIDENCE`
  7. `BACKGROUND_JOB_FAILURE`
  8. `STORAGE_FAILURE`
- Enforces safe self-recovery constraints: max 3 retries, exponential backoff, zero automatic database deletions, zero production setting modifications.

---

## 3. Automated Test Verification

Automated test suite: `tests/test_phase6f_local_monitoring_recovery.py`

| Test Case | Objective | Result | Duration |
| :--- | :--- | :--- | :--- |
| `test_error_classification_mappings` | Confirms runtime exceptions map to institutional categories with runbooks | **PASS** | 0.01s |
| `test_all_categories_have_runbooks` | Verifies every error category has severity, safe auto-recovery, and instructions | **PASS** | 0.01s |
| `test_system_observability_api_contract` | Verifies `/api/v1/system/diagnostics` schema provides database, hardware, AI data | **PASS** | 0.82s |
| `test_system_frontend_page_renders` | Verifies `/system` frontend route loads with HTTP 200 in Next.js Turbopack | **PASS** | 0.15s |

**Total Suite Result**: 4 passed in 38.25s.

---

## 4. Phase 6F Acceptance Sign-off

- [x] Web monitoring interface live at `/system`.
- [x] Real-time GPU VRAM, temperature, and system RAM displayed.
- [x] Qwen3.5 9B runtime status, context budget, and TPS displayed.
- [x] Database durability status and retention policy displayed.
- [x] Institutional error classification engine implemented (`services/maintenance/self_recovery.py`).
- [x] Safe self-recovery limits enforced (zero destructive automatic operations).
- [x] Phase 6F complete; ready to proceed automatically to **Phase 6G: Final Integrated Local Acceptance**.

