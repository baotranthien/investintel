# INVESTINTEL — PHASE 6: LOCAL STABILITY, RELIABILITY & OPERATIONAL READINESS PLAN

**Author**: Lead Autonomous Engineer / Senior System Architect  
**Target Branch**: `phase6-local-stability`  
**Accepted Baseline Commit**: `26b2f8d9303354e1008403451b6e78497d368456`  
**Annotated Tag**: `phase3-5-accepted-2026-11-02`  
**Date**: November 2, 2026  
**Environment**: Local Windows Workstation, Local SQLite, Ollama v0.35.0 (Qwen3.5 9B Q4_K_M), FastAPI, Next.js 16 Turbopack  
**Production Guardrail**: `ALLOW_PRODUCTION_DB_WRITE=false` strictly enforced. Zero production database writes.

---

## 1. Executive Summary & Objectives

With Phases 3, 4, and 5 successfully implemented, verified, and passing all 38 regression tests and 10 end-to-end user workflows, **Phase 6** transitions InvestIntel from feature-complete development into a robust, self-healing, locally autonomous financial intelligence platform.

### Core Philosophy
1. **Local-Only Autonomy**: The platform operates entirely on the local developer workstation without relying on external cloud APIs or write access to production databases.
2. **Deterministic Lifecycle**: Every service (Ollama daemon, Uvicorn API server, Next.js dev server) must have unambiguous startup, health verification, graceful degradation, and teardown mechanics.
3. **Operational Transparency**: Zero silent failures. Resource exhaustion, slow LLM token generation, missing data ingestion, and unhandled exceptions must be surfaced through structured logging and dashboard diagnostics.
4. **Resilience & Data Durability**: The local SQLite database must be automatically backed up, verified, and restorable within seconds.

---

## 2. The 10 Operational Dimensions

```
+--------------------------------------------------------------------------------------------------+
|                              INVESTINTEL LOCAL RUNTIME TOPOLOGY                                  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-----------------------+     REST / SSE      +--------------------+     HTTP / JSON API       |
|   |   Next.js 16 Web UI   | <-----------------> |  FastAPI Backend   | <---------------------+   |
|   |  Port 3000 (Node.js)  |                     |  Port 8000 (.venv) |                       |   |
|   +-----------------------+                     +--------------------+                       |   |
|               ^                                      |            |                          |   |
|               |                                      v            v                          v   |
|       Browser Sessions                      +-------------+  +------------+        +-------------+
|                                             | Local SQLite|  | Background |        | Ollama LLM  |
|                                             | DB & Backups|  | Schedulers |        | Port 11434  |
|                                             +-------------+  +------------+        | Qwen3.5 9B  |
|                                                                                    +-------------+
+--------------------------------------------------------------------------------------------------+
```

---

### Topic 1: Local Service Lifecycle Management (Ollama, FastAPI, Next.js)

**Current Reality**:
Services are spawned ad-hoc in terminal sessions or background tasks. When ports are in use or processes become orphaned, duplicate or conflicting processes cause socket errors (`10048`) or frozen connections.

**Phase 6 Architecture & Deliverables**:
1. **Process Orchestration Contract**:
   - Centralize service discovery and supervision in `scripts/supervise_local.ps1`.
   - Distinct PID tracking via `.run/pids.json` recording `service`, `pid`, `port`, `startTime`.
   - Explicit state transitions: `STOPPED` -> `STARTING` -> `HEALTHY` -> `DEGRADED` -> `STOPPING`.
2. **Deterministic Teardown & Port Reclamation**:
   - Safe process termination: check PID ownership, send graceful break signal, wait 3 seconds, terminate if uncooperative.
   - Guard against killing unrelated Windows processes sharing system ports.

---

### Topic 2: Startup Automation & Health Checks

**Current Reality**:
Checking a port before a service is listening previously returned exit code 1, which tools misinterpreted as service crashes.

**Phase 6 Architecture & Deliverables**:
1. **Multi-Stage Health Probing**:
   - **Stage 1 (Socket Listening)**: Poll TCP port up to 30 seconds with 1-second backoff.
   - **Stage 2 (HTTP Protocol Ready)**: Verify HTTP response code (Ollama: `GET /api/tags` -> 200; API: `GET /health` -> 200; Next.js: `GET /` -> 200 or 307).
   - **Stage 3 (Functional Ready)**:
     - Ollama: Ensure `qwen3.5:9b-q4_K_M` is loaded into memory or ready for warm inference.
     - FastAPI: Verify SQLite connection pool and read-only schema validation.
2. **Unified Startup Script**:
   - Single command `pwsh ./scripts/start_all.ps1` with flag `-WarmUpLLM` to pre-load models into GPU VRAM.

---

### Topic 3: SQLite Backup & Point-in-Time Restore Routines

**Current Reality**:
The local SQLite database (`storage/investintel.db`) stores user watchlists, portfolio snapshots, alert histories, financial history caches, and valuation scenario overrides. A corrupt write or schema migration error could lose hours of work.

**Phase 6 Architecture & Deliverables**:
1. **Online Non-Blocking Backups**:
   - Use SQLite Online Backup API (`sqlite3.connect().backup(...)` or SQLite CLI `.backup`) to snapshot `investintel.db` without locking read queries.
   - Periodic auto-backup service running hourly and on clean shutdown.
2. **Snapshot Retention Policy**:
   - Store snapshots in `storage/backups/investintel_YYYYMMDD_HHMMSS.db`.
   - Retain last 24 hourly snapshots and last 7 daily snapshots. Automatic cleanup of older files.
3. **One-Command Restore & Verification**:
   - `pwsh ./scripts/restore_db.ps1 -Snapshot <timestamp_or_latest>` with pre-flight integrity check (`PRAGMA integrity_check`).

---

### Topic 4: Local Environment & Secret Management

**Current Reality**:
Configuration is split across `.env`, system environment variables, and fallback constants. Development keys or sensitive tokens could inadvertently be committed if `.gitignore` rules slip.

**Phase 6 Architecture & Deliverables**:
1. **Environment Strict Validation**:
   - Enforce Pydantic BaseSettings validator at FastAPI boot in `packages/core/config.py`.
   - Boot fails immediately if `ALLOW_PRODUCTION_DB_WRITE=true` in local development mode without explicit production flags.
2. **Secret Containment Audit**:
   - Pre-commit hook / test assertion verifying `.env`, `.env.local`, and SQLite DBs are not staged.
   - Comprehensive `.env.example` documenting all non-sensitive configuration parameters.

---

### Topic 5: Scheduled Financial-Data Ingestion

**Current Reality**:
Financial statements, ratios, and quotes are ingested on-demand when visiting research pages. High cache miss rates cause slow initial page loads.

**Phase 6 Architecture & Deliverables**:
1. **Deterministic Local Background Ingestion Engine**:
   - Implement `services/ingestion/scheduler.py` using `APScheduler` or native lightweight async loop.
   - Target universe: VN30 / Top 50 core tickers (e.g. BMP, FPT, VNM, HPG, MBB, VCB).
   - Schedule: Daily post-market ingestion (16:00 ICT) and morning pre-market ratio recalculation (08:30 ICT).
2. **Idempotent Upsert & Rate Limiting**:
   - Respect upstream rate limits (exponential backoff, max 3 req/sec).
   - Upsert financial records with deterministic hashing to avoid duplicate statement rows.

---

### Topic 6: Autonomous Opportunities and Alerts Background Jobs

**Current Reality**:
The Opportunity Scanner and Alert Engine run synchronously when user requests hit `/api/v1/opportunities` or `/api/v1/alerts`.

**Phase 6 Architecture & Deliverables**:
1. **Periodic Evaluation Worker**:
   - Run opportunistic screening hourly during market hours.
   - Evaluate alert conditions: Price targets, Valuation discount > 15%, Negative Earnings Surprise, Margin Compression, Leverage Spikes.
2. **Deduplicated Alert Dispatch**:
   - Generate persistent records in `alerts` table using deterministic hash `ALERT-{symbol}-{kind}-{YYYYMMDD}`.
   - Emit SSE / WebSocket events or in-app notification badges when unread alerts trigger.

---

### Topic 7: Qwen3.5 9B & Ollama Performance Monitoring

**Current Reality**:
Inference latency fluctuates based on prompt length, context window size (4K vs 8K), and concurrent requests.

**Phase 6 Architecture & Deliverables**:
1. **Token Throughput & Latency Telemetry**:
   - Track `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration` returned by Ollama `/api/generate` and `/api/chat`.
   - Calculate Tokens Per Second (TPS) and Time To First Token (TTFT).
   - Log performance metrics to `logs/ollama_metrics.jsonl`.
2. **Prompt Optimization & Context Budgeting**:
   - Maintain semantic pruning of input prompts to keep context under 6,000 tokens for sub-2.5 second TTFT.
   - Benchmark caching for system prompts.

---

### Topic 8: GPU/RAM & Inference Diagnostics

**Current Reality**:
Windows memory limits or VRAM pressure can cause Ollama to offload layers from GPU to CPU, silently dropping inference speed from 35 tok/s to 4 tok/s.

**Phase 6 Architecture & Deliverables**:
1. **Resource Profiler**:
   - Windows PowerShell helper querying `nvidia-smi` (or DXGI/WMI) for GPU VRAM utilization and temperature.
   - System RAM usage monitoring to detect memory leaks in FastAPI or Node dev server.
2. **Adaptive Fallback & Layer Warning**:
   - Endpoint `/api/v1/system/diagnostics` exposing Ollama model placement (`layers_on_gpu` vs `layers_on_cpu`).
   - Warning banner in Next.js UI when GPU acceleration is degraded or unavailable.

---

### Topic 9: Local Error Logging & Recovery Runbooks

**Current Reality**:
Log files are scattered in temporary test logs, background task files, and console windows.

**Phase 6 Architecture & Deliverables**:
1. **Centralized Structured Logging**:
   - Standardize JSON / structured text logging across API (`logs/api.log`) and background workers (`logs/workers.log`).
   - Automatic log rotation (10 MB max size, 5 backups).
2. **Automated Recovery Runbooks**:
   - Runbook 1: *Ollama daemon frozen or unresponsive* -> force restart daemon, re-ping `/api/tags`.
   - Runbook 2: *FastAPI port conflict or stale lock* -> identify owning process, clean lockfile, restart.
   - Runbook 3: *Corrupt SQLite WAL journal* -> clean checkpoint, run integrity check, rollback to last snapshot if corrupted.

---

### Topic 10: Final Local-Only Acceptance Testing Framework

**Current Reality**:
Acceptance requires manual execution of multiple test scripts and manual browser navigation.

**Phase 6 Architecture & Deliverables**:
1. **Automated End-to-End Test Suite**:
   - Comprehensive test harness `tests/e2e/test_phase6_operational_acceptance.py`.
   - Validates all 10 operational areas without manual intervention.
   - Executes live API calls, verifies background job executions, validates database backups, and measures Ollama response latency.
2. **One-Click Acceptance Command**:
   - `pytest tests/e2e/test_phase6_operational_acceptance.py -v --tb=short` providing a clean pass/fail certificate.

---

## 3. Execution Roadmap & Milestones

| Milestone | Key Deliverables | Verification Criteria |
| :--- | :--- | :--- |
| **M6.1: Service Supervision & Health** | `scripts/supervise_local.ps1`, `scripts/start_all.ps1`, `scripts/stop_all.ps1` | Zero port collisions; 100% reliable 3-stage health detection |
| **M6.2: SQLite Backup & Durability** | `services/db/backup.py`, `scripts/backup_db.ps1`, `scripts/restore_db.ps1` | Non-blocking snapshot in < 200ms; integrity check PASS |
| **M6.3: Background Schedulers & Jobs** | `services/scheduler/`, periodic ingestion & alert evaluation | Automated run every 60m; idempotent upsert; zero duplicate alerts |
| **M6.4: AI Diagnostics & Telemetry** | Ollama metrics tracker, `/api/v1/system/diagnostics` endpoint | TPS & TTFT logged; GPU VRAM layer offload detection |
| **M6.5: Logging & Operational Runbooks** | Centralized rotating logs in `logs/`, structured error capture | Structured JSON log output; runbooks documented and verified |
| **M6.6: Phase 6 Final Acceptance** | `tests/e2e/test_phase6_operational_acceptance.py` | 10/10 operational dimensions PASS; regression suite 38/38 PASS |

---

## 4. Verification Checkpoint Table

```markdown
| Reference | Expected Hash / Value | Target Status |
| :--- | :--- | :--- |
| `origin/main` | `eb4b6344c45db3c5e8900a229ed9610faf8bb2cd` | Frozen & Untouched |
| `origin/backup/phase3-5-accepted-2026-11-02` | `26b2f8d9303354e1008403451b6e78497d368456` | Preserved |
| `phase3-5-accepted-2026-11-02` (tag) | `26b2f8d9303354e1008403451b6e78497d368456` | Frozen Baseline Tag |
| `origin/phase6-local-stability` | Initial: `26b2f8d9303354e1008403451b6e78497d368456` | Active Development Branch |
| `ALLOW_PRODUCTION_DB_WRITE` | `false` | Zero production writes |
```
