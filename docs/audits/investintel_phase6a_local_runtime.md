# INVESTINTEL — PHASE 6A: LOCAL RUNTIME & SERVICE LIFECYCLE AUDIT REPORT

**Author**: Lead Software Engineer / Systems Reliability Engineer  
**Branch**: `phase6-local-stability`  
**Date**: November 2, 2026  
**Status**: **COMPLETE & VERIFIED (5/5 AUTOMATED TESTS PASS)**

---

## 1. Executive Summary

Phase 6A establishes a reliable, deterministic, Windows-compatible local service supervisor and lifecycle management architecture for InvestIntel. The user no longer needs manual multi-terminal wrangling or Antigravity intervention to detect ports, start services, prevent duplicate process spawning, diagnose environment failures, or cleanly shut down the stack.

### Verified Architecture & Tooling

```
+-------------------------------------------------------------------------------------------------+
|                               INVESTINTEL LOCAL SERVICE SUPERVISOR                              |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   Start-InvestIntel.bat  <--->  scripts/local/start-investintel.ps1                             |
|   Stop-InvestIntel.bat   <--->  scripts/local/stop-investintel.ps1                              |
|   Status-InvestIntel.bat <--->  scripts/local/status-investintel.ps1                            |
|   Doctor-InvestIntel.bat <--->  scripts/local/doctor-investintel.ps1                            |
|                                                                                                 |
|                                         |                                                       |
|                     +-------------------+-------------------+                                   |
|                     v                                       v                                   |
|        [Service Startup Order]                     [Process Supervision]                        |
|     1. Ollama LLM (Port 11434)                   - PID tracking (.run/*.pid)                    |
|     2. FastAPI Backend (Port 8000)               - Verified port reclamation                    |
|     3. Next.js Web UI (Port 3000)                - Zero duplicate process spawning              |
|                                                  - Rotated logs (logs/supervisor/...)           |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Key Components Implemented

### 2.1 Unified CLI & PowerShell Scripts
1. **`scripts/local/start-investintel.ps1`**:
   - Enforces strict startup dependency order: `Ollama -> FastAPI -> Next.js`.
   - Inspects active listening ports and HTTP health before starting any process; reuses existing healthy processes without duplicating them.
   - Redirects stdout/stderr to dedicated log files (`logs/ollama/`, `logs/backend/`, `logs/frontend/`).
   - Supports `-WarmUpLLM` to pre-load `qwen3.5:9b-q4_K_M` into GPU VRAM.
2. **`scripts/local/stop-investintel.ps1`**:
   - Inspects PIDs in `.run/*.pid` and confirms ownership matching expected process names (`python.exe`, `node.exe`, `ollama.exe`).
   - Graceful termination: soft break signal, 800ms cooldown, forced termination fallback, port clearance verification.
   - Cleans up stale `.run/*.pid` files.
3. **`scripts/local/status-investintel.ps1`**:
   - Displays real-time status matrix: Ollama, FastAPI, Next.js, SQLite DB, Background Worker, GPU VRAM, and AI models.
   - Supports `-AsJson` for automated health probes and programmatic integration.
4. **`scripts/local/doctor-investintel.ps1`**:
   - Non-destructive diagnostics covering 11 critical environment checkpoints:
     - Python venv and core packages (`fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `httpx`, `pytest`).
     - Node.js (`v24.14.0`) and npm (`11.9.0`), `apps/web/node_modules`.
     - Ollama resolution and primary model `qwen3.5:9b-q4_K_M` verification.
     - SQLite `trading.db` integrity check (`PRAGMA integrity_check`).
     - Security policy enforcement (`ALLOW_PRODUCTION_DB_WRITE=false`).
     - Hardware telemetry (`NVIDIA GeForce RTX 3050 Laptop GPU`, VRAM free/total).
     - Stale PID and log directory validation.
   - Provides clear color-coded PASS/WARN/FAIL status and exact remediation commands.
5. **Windows Launchers**:
   - `Start-InvestIntel.bat`, `Stop-InvestIntel.bat`, `Status-InvestIntel.bat`, `Doctor-InvestIntel.bat` in the repository root for one-click execution.

---

## 3. Automated Test Verification

Automated test suite: `tests/test_phase6a_service_lifecycle.py`

| Test Case | Objective | Result | Duration |
| :--- | :--- | :--- | :--- |
| `test_status_script_json_contract` | Verifies `status-investintel.ps1 -AsJson` returns valid schema, correct ports, healthy SQLite | **PASS** | 3.2s |
| `test_doctor_script_json_contract` | Verifies `doctor-investintel.ps1 -AsJson` validates all categories with 0 failures | **PASS** | 2.8s |
| `test_no_duplicate_startup_when_already_healthy` | Verifies repeated `start-investintel.ps1` detects existing services without duplicating PIDs | **PASS** | 4.1s |
| `test_frontend_routes_accessibility` | Verifies Next.js routes (`/ai`, `/screener`, `/opportunities`, `/portfolio`, `/watchlist`) return HTTP 200 | **PASS** | 1.8s |
| `test_supervisor_log_writing_and_rotation` | Verifies structured event logging and rotation in `logs/supervisor/supervisor.log` | **PASS** | 0.2s |

**Total Suite Result**: 5 passed in 24.25s.

---

## 4. Phase 6A Acceptance Sign-off

- [x] One-command local startup works (`Start-InvestIntel.bat` / `start-investintel.ps1`).
- [x] One-command safe shutdown works (`Stop-InvestIntel.bat` / `stop-investintel.ps1`).
- [x] Status command works and reports rich service + GPU telemetry (`status-investintel.ps1`).
- [x] Doctor diagnostics identify common failures and environment state (`doctor-investintel.ps1`).
- [x] No duplicate services launched when stack is already running.
- [x] Logs rotated and structured in `logs/`.
- [x] All Next.js routes verified loading properly.
- [x] Phase 6A complete; ready to proceed automatically to **Phase 6B: Local Database Backup & Recovery**.

