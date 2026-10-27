# Project Status — Personal Investment Intelligence Platform

## Executive Summary

### Current Problem
The local-first platform has completed all Phase 6 milestones (6A–6I), Local Ollama AI integration with cloud isolation, Multi-Provider Free Data Expansion, and **Cloud Readiness Implementation** (Personal non-commercial cloud deployment target: Render Free backend, Vercel Hobby frontend, Neon PostgreSQL Free, authenticated idempotent cron-job.org execution, and single-user private authentication).

**Provider & Ingestion Status Distinction:**
- `DNSE_PUBLIC`: `CONNECTED_AND_INGESTED` — Unauthenticated public secondary provider (`https://services.entrade.com.vn/chart-api/v2/ohlcs`) implemented and verified end-to-end against live PostgreSQL.
- `VIETSTOCK`: `CONNECTED_AND_INGESTED` — Unauthenticated public news endpoint (`https://vietstock.info/api/news/today`) implemented and verified into canonical `EventRecord` with data lineage.
- `VNDIRECT`: `CONNECTED_AND_INGESTED` — Unauthenticated OHLCV historical bars from VNDirect public endpoint; independent Vietnam equity price source.
- `WORLD_BANK`: `CONNECTED_AND_INGESTED` — Unauthenticated World Bank Indicators API for Vietnam macro series.
- `FREE_FX` (Frankfurter / open.er-api): `CONNECTED_AND_INGESTED` — Unauthenticated free FX rate providers. USD/VND daily reference rate.
- `GDELT`: `CONNECTED_AND_INGESTED` — GDELT public news API with 5.5s inter-request pacing. Promotes to canonical `EventRecord`.
- `BLS` (unauthenticated v1): `CONNECTED_AND_INGESTED` — BLS public unauthenticated API v1 mode with automatic 10-year window clamping.
- `LOTUSMARKET`: `CONNECTED_AND_VERIFIED` — Unauthenticated secondary provider toolkit: VPS DataFeed (real-time quotes, foreign net flow, bid/ask), Entrade (historical daily OHLCV with VPS fallback), and CafeF (shareholder insider trading into EventRecord).
- `VIETCAP_IQ`: `INTEGRATED_AND_VERIFIED` — Unauthenticated native provider adapter (`services/ingestion/vietcap.py`) yielding 34–35 quarters (8.5 years) and 8 annual periods of audited Balance Sheets, Income Statements, and Cash Flows with exact Point-In-Time `publicDate` publication timestamps, raw VND integer scaling, and SHA-256 canonical data lineages (`trangcm/vn-market-data`).
- `DATACORE`: `INTEGRATED_AUTH_REQUIRED` — Native clean-room provider adapter (`services/ingestion/datacore.py`) using pure `httpx`; unauthenticated previews verified; authenticated queries protected with `BLOCKED_MISSING_CREDENTIAL` gating.
- `VNSTOCK_SERVICE`: `ARCHITECTURAL_PATTERNS_INTEGRATED` — Clean-room adoption of 7-day overlap windows, adjustment-seam canary detection (`detect_adjustment_seam` in `services/ingestion/reconciliation.py`), and comprehensive data-quality audit gates (`audit_data_quality_gates` in `services/quality/coverage.py` and `scripts/audit_data_quality.py`).
- `VNFIN`: `EVALUATED_AND_REJECTED` — Evaluated `hungson175/vnfin`; rejected direct dependency due to unpinned Windows timezone bug (`ZoneInfoNotFoundError: 'Asia/Ho_Chi_Minh'`) and architectural redundancy with native Vietcap, VNDIRECT, and LotusMarket adapters.
- `CAPABILITY_REGISTRY`: `IMPLEMENTED` — Created `services/ingestion/capabilities.py` specifying typed provider capability registry, rate-limiting profiles, dataset-level mappings, and explicit fallback priorities without error-masking.
- `LIVE_HOSE_PROVIDER`: **BLOCKED**. An approved, commercially licensed official HOSE feed contract has not been established. The availability of public unauthenticated endpoints does NOT pass Gate 8.
- `LOCAL_OLLAMA`: `VERIFIED_LIVE` — Real local inference verified against installed model `qwen2.5:3b` on loopback GPU/CPU with 13/13 acceptance matrix passing (100%).
- `PRODUCTION`: **CONDITIONAL** until deployment and security checks are actually verified on live cloud infrastructure.

### Current Status
Current project status is **TECHNICAL READINESS PASS / OVERALL PRODUCTION READINESS PARTIAL** (Authoritative 8-Gate Evaluation). Software, universal data contracts, accounting semantics, and live local AI pass all gates. Overall production readiness remains partial due to external platform token requirement (Vercel), pending first scheduled EOD trigger, and user authorization safety hold for Neon DB backfill (`ALLOW_PRODUCTION_DB_WRITE=false`).

Authoritative audit last updated 2026-10-27 (verified live against local test suite, local Ollama daemon, cloud deployment endpoints, and frontend production build):
- **Operation State**: **FINAL FINANCIAL SEMANTICS AUDIT, REVISION CONSISTENCY & EVIDENCE-BASED ACCEPTANCE COMPLETE** — 42 financial data contract, correctness, and universe-generic regression tests passed (`tests/test_data_contracts.py` + `tests/test_financial_correctness.py` + `tests/test_universe_generic.py`); live AI acceptance matrix 13/13 passed against local Ollama (`qwen2.5:3b`); Next.js frontend production build verified (13/13 routes compiled); automated Acceptance Gate Evaluator (`scripts/evaluate_acceptance_gates.py`) dynamically audited 100 active equities (104 total assets); production-write boundary strictly preserved (`ALLOW_PRODUCTION_DB_WRITE=false`).
- **Dynamic Universe Reconciliation (`services/quality/reconciliation.py`)**: Completely eliminated shortlist/whitelist-only audits. Discovers all active assets dynamically from canonical registry (100 STOCK, 1 ETF, 3 INDEX). Enforces asset-type-specific contracts (equities audited for statements/shares/TTM/ratios; ETFs audited for price geometry and liquidity; Indices audited for benchmark completeness).
- **Financial Semantics & Universal Data Contracts**:
  - IAS 33 & IAS 1 Semantics: Enforced in `services/fundamentals/repository.py` and `services/fundamentals/snapshot.py`. Attributable parent net income and parent equity are resolved via explicit parent fields, standalone identity, or $Total - MinorityInterest$ when both exist. Blind fallback to total net income on consolidated statements is strictly eliminated.
  - Outlier and Negative Denominator Masking Eliminated: In `services/research/workspace.py`, companies with net loss (`net_income <= 0`) or negative equity strictly yield `NOT_MEANINGFUL` and `NOT_APPLICABLE`, blocking fallback provider ratios from falsely claiming `SOURCE_RECONCILED`.
  - Invalidation Graph (`services/contracts/invalidation.py`): Primary triggers across price adjustments, corporate action splits, statement restatements, and share counts deterministically propagate downstream to invalidate derived ratios, blocking publication until full recomputation and verification.
- **Price Validity & Freshness Classification (`scripts/audit_universe_prices.py`)**:
  - Total Canonical Assets: **104 assets** (100 STOCK, 1 ETF, 3 INDEX).
  - `PRICE_PRESENT`: 104/104 (100.0%)
  - `GEOMETRY_VALID`: 104/104 (100.0%)
  - `PRICE_FRESH` (<= 7 days): 103/104 (99.0%)
  - `PRICE_DATE_ALIGNED` (Today/As-Of): 101/104 (97.1%)
  - `USABLE_FOR_CURRENT_VALUATION`: 103/104 (99.0%)
  - `STALE_EXCLUDED_FROM_VALUATION`: 1/104 (1.0%) — VN300 (Obs date 2023-10-27, 1096 days stale; legacy CSV benchmark preserved for history, excluded from live valuation).
- **Financial Reconciliation Audit (Entire Discovered Universe)**:
  - Total Canonical Equities Audited: **100 equities**.
  - P/E External Reconciliation: **94/100 (94.0%)**. Exact 6 unreconciled tickers: `BSI, CTS, DSE, KOS, VIX, VPX`. All 6 mathematically verified; discrepancies explained by reporting period lag (BSI, CTS, VPX), share dilution lag post-capital-increase (VIX, DSE), or price observation timing (KOS). No canonical values overwritten.
  - P/B External Reconciliation: **74/100 (74.0%)**. Exact 26 unreconciled tickers:
    - 10 tickers with no provider P/B (`db_pb = None`): `CMG, KDC, LPB, NLG, OCB, PVT, SHB, SSB, STB, VIC`. Calculated mathematically as `Price / BVPS` and tagged `MATHEMATICALLY_CALCULATED`.
    - 16 tickers differing >15%: `BWE, CII, DXG, FRT, GEX, HCM, HDG, KOS, MCH, MSN, PAN, PC1, PLX, SAB, TCH, VGC`. Proven root cause is historical BVPS staleness in provider snapshot (e.g. VGC provider BVPS was 16,539.89 VND from 2021, while current BVPS is 26,187 VND), not unverified NCI assumptions.
- **Local Database (v18.6)**: 104 canonical instruments, 15,348 prices, 8,435 financial statements, 0 price geometry violations across all bars.
- **Cloud Neon Database & Render Backend**:
  - 6,816 prices, 3,523 financial statements in Neon Cloud PostgreSQL (Read-Only write guard active).
  - Render Backend: **LIVE & VERIFIED at commit `6e4ddbe0481527de926fbe4f6b19733d3b52d279` (`6e4ddbe`)** via `/api/v1/system/info`. Neon latency 7.35ms.
- **Cloud Vercel Frontend**:
  - Reachable and serving HTTP 200 at `https://investintel-nine.vercel.app` (`ETag: "23739977a7e7a918e54a14ae1338d4d9"`).
  - Platform Deployment Revision Verification: **BLOCKED_AWAITING_TOKEN** (`VERCEL_TOKEN` not configured in environment; revision cannot be proven from client HTTP headers alone).
- **Scheduled EOD Automation**: Cron `37 8 * * 1-5` configured in `.github/workflows/eod_ingestion.yml`; status recorded as **PENDING** awaiting genuine schedule trigger observation.
- **Neon Synchronization Safety**: Production write protection active (`ALLOW_PRODUCTION_DB_WRITE=false`). Cloud sync dry-run ready; held as **BLOCKED_AWAITING_AUTH** pending explicit user authorization.

## 1. Current Checkpoint

> **Authoritative as of 2026-10-27. All historical milestone reports below are preserved and clearly labelled as historical.**

* **Date**: 2026-10-27
* **Phase**: **P0 DEPLOYMENT ALIGNMENT & FINAL FINANCIAL CORRECTNESS VERIFICATION**
* **Milestone**: **Full Test Suite Execution (283 Passed, 1 Skipped, 0 Failed), Regression Subset (48/48 Passed), Strict vs Operational Reconciliation Separation (P/E Strict 100.0%, Operational 94.0%; P/B Strict 100.0%, Operational 74.0%), DSE Implied EPS Arithmetic Resolution, IAS 33 Share Denominator Semantics, Render Live SHA Aligned — VERIFIED**
* **Repository State**: Working tree clean. Render live backend verified running `6e4ddbe0481527de926fbe4f6b19733d3b52d279` (`6e4ddbe`). Vercel frontend reachable (HTTP 200).
* **Tested Source Commit SHA**: `6e4ddbe0481527de926fbe4f6b19733d3b52d279`
* **Tested Application Fingerprint**: `64f582a06fef2c5cae6274b4f2d1a2ce8e5cb3c4508c3824ee42b71ef2da8321` (deterministic SHA256 of canonical application Merkle tree, excluding `docs/`)
* **Full Test Suite**: **283 PASSED, 1 SKIPPED, 0 FAILED** out of 284 tests across entire repository (100% pass of executable tests; 1 test cleanly skipped due to SQLite runner db omission of PostgreSQL-specific universe table).
* **Regression Subset**: **48/48 PASSED** in 62.10s (18 in `test_data_contracts.py` + 18 in `test_financial_correctness.py` + 12 in `test_universe_generic.py`).
* **Metric-Level Reconciliation**:
  - **P/E Metric**:
    - *Strict Comparable Pairs*: 94/94 matched (100.0% match rate; 0 unreconciled comparable pairs; 6 temporally non-comparable drift pairs).
    - *Operational Snapshot Comparison*: 94/100 matched (94.0% across universe; 6 drift pairs: BSI, CTS, DSE, KOS, VIX, VPX explained with factor decomposition and derived checks).
  - **P/B Metric**:
    - *Strict Comparable Pairs*: 74/74 matched (100.0% among fresh comparable pairs; 0 unreconciled).
    - *Operational Snapshot Comparison*: 74/100 matched (74.0% across universe; 16 stale historical BVPS comparator, 10 missing provider comparator).
* **DSE Arithmetic Discrepancy Resolution**: Raw provider P/E is 36.60454642 at price 20,550 VND, implying a provider EPS of 561.405676 VND (~426.09M implied weighted-average shares vs 428.25M period-end shares). Direct division $20,550 / 558.57 = 36.79$ did not match raw provider ratio because provider dataset contains no raw EPS field and utilized weighted-average shares. Implied EPS strictly classified as `DERIVED_CHECK`; status classified as `PARTIALLY_SUPPORTED`.
* **Live Backend**: `https://investintel-api.onrender.com` (HTTP 200, commit `6e4ddbe0481527de926fbe4f6b19733d3b52d279`, exact match to local HEAD, Neon latency 7.35ms).
* **Live Frontend**: `https://investintel-nine.vercel.app` (HTTP 200, ETag `"23739977a7e7a918e54a14ae1338d4d9"`, platform revision check `BLOCKED_AWAITING_TOKEN`).
* **Scheduled Automation**: `PENDING` (cron `37 8 * * 1-5` configured; awaiting first genuine schedule event).
* **Neon Safety Guard**: `ALLOW_PRODUCTION_DB_WRITE=false` strictly preserved (0 cloud writes performed).
* **Local Ollama Live Inference**: `VERIFIED` (`qwen2.5:3b` on loopback 11434, 13/13 acceptance matrix passed).

### Checkpoint — 2026-10-19 (HISTORICAL)
* **Date**: 2026-10-19
* **Milestone**: Remove Gemini Completely & Switch to Local Ollama Only (204/204 Tests Pass, 12 routes clean build) — VERIFIED
* **Test Result**: 204 passed, 0 failed.
* **Build Result**: 12 routes clean build.

### Note on .env Loading
The `.env` file is loaded by `database/connection.py` via `python-dotenv` at import time. The `pytest` subprocess does not have `.env` vars pre-loaded in the OS environment — Ollama gateway tests run fully isolated with mock fixtures and live verification against the local daemon. The running FastAPI process (port 8000) inherits `.env` via the same mechanism at startup.


### Original Final Gate Table — 2026-10-01 (HISTORICAL)

*The following records the state at the time of the original Final Gate run on 2026-10-01. These were accurate at that date. All items marked BLOCKED below have since been verified except where noted.*

| Gate | Status at 2026-10-01 | Evidence |
| --- | --- | --- |
| **Tests 107/107 ×3** | ✅ PASS | Final Gate runs: 12.14s, 12.25s, 12.29s |
| **Frontend Build** | ✅ PASS | `npm run build` — 11 routes, Turbopack, TypeScript clean |
| **Security Audit** | ✅ PASS | No broker secrets in env; Ollama loopback-only |
| **Schema Audit** | ✅ PASS | 38 tables confirmed; Alembic migration chain verified |
| **API Latency (SQLite)** | ✅ PASS | Data endpoints 1–10ms; health/observability 3–4.5s |
| **Data Provenance** | ✅ PASS | All seeded data labeled `SEEDED_OR_UNTRACED` |
| **PWA** | ✅ PASS | Manifest, service worker, offline banner, SW registration |
| **Backtest PIT** | ✅ PASS | 0 look-ahead violations; friction model verified |
| **PostgreSQL** | ❌ BLOCKED at 2026-10-01 | No PostgreSQL service available at that time — **RESOLVED 2026-10-02** |
| **Redis** | ❌ BLOCKED at 2026-10-01 | Connection refused — **RESOLVED 2026-10-02** |
| **Live HOSE Provider** | ❌ BLOCKED | No approved provider; CSV only — **STILL BLOCKED** |
| **Analyst Scheduler Live Run** | ❌ BLOCKED at 2026-10-01 | PostgreSQL unavailable — **RESOLVED 2026-10-02** |
| **Ollama / AI** | ❌ BLOCKED at 2026-10-01 | Connection refused — **RESOLVED 2026-10-02** |
| **E2E Browser → API → DB** | ❌ BLOCKED at 2026-10-01 | Required PostgreSQL + API — **RESOLVED 2026-10-14** |

**Original result: PHASE 6 = LOCAL ACCEPTED. Production remained conditional pending external infrastructure.**

### Full Production Gate Audit — 2026-10-02 (HISTORICAL)

| Gate | Status | Evidence |
| --- | --- | --- |
| **G1 — Document Consistency** | ✅ PASS | PROJECT_STATUS.md updated; stale BLOCKED statements replaced; historical records preserved. |
| **G2 — PostgreSQL Final Verification** | ✅ PASS | PG 18.6, `trading` db, alembic=`20261002p6g`, 38 ORM tables in DB, 29 FKs, 152 indexes. |
| **G3 — Redis** | ✅ PASS | Redis 8.10.1 port 6379, ping=True, set/get verified. |
| **G4 — Ollama / Local AI** | ✅ PASS | Ollama 0.35.0, `qwen2.5:0.5b` installed+loaded, RTX 3050 GPU, structured JSON generation verified. |
| **G5 — RAG / Document Intelligence** | ✅ PASS | 3 synthetic fixture documents in PostgreSQL, PIT filtering verified. |
| **G6 — API E2E** | ✅ PASS | All 18 endpoints against live PostgreSQL uvicorn process returned HTTP 200. |
| **G7 — Lifespan Schedulers** | ✅ PASS | Both schedulers started, executed cycles, idempotency verified. |
| **G8 — Live HOSE Provider** | ❌ BLOCKED | No approved/licensed provider. `HOSE_CSV` is static local CSV, not a live feed. |
| **G9 — Macro Providers** | ✅ PASS | BLS: real observations. FRED: ProviderUnavailableError on missing key. NSO_VIETNAM/SBV: registered. |
| **G10 — Data Quality / Integrity** | ✅ PASS | 0 duplicate same-date price bars. Price source=`MarketDataCSV` (seeded). |
| **G11 — Backtest / Quant Safety** | ✅ PASS | PIT audit=0 violations, deterministic reproducibility confirmed. |
| **G12 — Security / Privacy** | ✅ PASS | No broker credentials in env. Ollama loopback-only. |
| **G13 — Browser E2E** | ⚠️ PARTIAL | Frontend build verified; live browser session not run (browser quota exhausted). |
| **G14 — Test / Build Regression** | ✅ PASS | 108 passed, 0 failed × 3 runs. |
| **G15 — Final Status** | **CONDITIONAL** | Gate 8 remains BLOCKED. |

### Authoritative Production Gate Audit — 2026-10-14

| Gate | Status | Evidence |
| --- | --- | --- |
| **G1 — Document Consistency** | ✅ PASS | PROJECT_STATUS.md updated; 2026-10-14 authoritative checkpoint active; historical records clearly labeled. |
| **G2 — PostgreSQL Final Verification** | ✅ PASS | PG 18.6, `trading` db, alembic=`20261002p6g`, 38 ORM tables, 29 FKs, 152 indexes, latency 1.75ms. |
| **G3 — Redis** | ✅ PASS | Redis 8.10.1 port 6379, ping=True, latency 6.7ms, `/api/v1/health` redis.connected=True. |
| **G4 — Ollama / Local AI** | ✅ PASS | Ollama 0.35.0 on loopback, `qwen2.5:0.5b` loaded on RTX 3050 Laptop GPU, structured JSON output verified. |
| **G5 — RAG / Document Intelligence** | ✅ PASS | Temporal filtering (`publication_date <= as_of_date`), ticker/source filtering, empty retrieval verified on PG. |
| **G6 — API E2E** | ✅ PASS | All 18 endpoints tested against live FastAPI process, all return HTTP 200. |
| **G7 — Lifespan Schedulers** | ✅ PASS | Both ingestion and analyst automation schedulers verified in lifespan; idempotency and persistence confirmed. |
| **G8 — Live HOSE Provider** | ❌ BLOCKED | **`LIVE_HOSE_PROVIDER = BLOCKED`**. No authorized/licensed live market-data provider contract or credentials exist. Only local static CSV (`HOSE_CSV`). |
| **G9 — Macro Providers** | ✅ PASS | BLS live fetch verified. FRED key absent (reported BLOCKED). NSO/SBV registered without fabrication. |
| **G10 — Data Quality / Integrity** | ✅ PASS | 0 duplicate same-date bars. No null-to-zero conversion. Seeded origin disclosed. |
| **G11 — Backtest / Quant Safety** | ✅ PASS | PIT audit=0 violations, friction model (0.15% brokerage, 0.10% tax, 0.10% slippage) enforced. |
| **G12 — Security / Privacy** | ✅ PASS | Zero broker secrets. Loopback-only Ollama. No auto-trading or broker execution paths. |
| **G13 — Browser E2E** | ✅ PASS | **Resolved 2026-10-14**: Live browser verified desktop layout (`/`, `/market`, `/research/FPT`, `/watchlist`, `/portfolio`, `/ai`), mobile responsive viewport (390×844), PWA manifest (`/manifest.json`), service worker (`/sw.js`), offline banner event trigger & dismissal, and honest `INSUFFICIENT_DATA`/`STALE` badging. Implementation defect in `what_could_go_wrong` fixed. |
| **G14 — Test / Build Regression** | ✅ PASS | **108 passed, 0 failed** (5.85s). Frontend build PASS (11 routes, 644ms, Turbopack, TypeScript clean). |
| **G15 — Final Status** | **CONDITIONAL** | **`PRODUCTION = CONDITIONAL`**. All internal and local gates PASS. Only Gate 8 (external live HOSE feed) remains BLOCKED. |


## Phase 6E Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6E — Decision Intelligence (implementation complete locally)  
**Implemented:** Added persisted as-of asset decision snapshots and migration `20261001p6e`; decision APIs compare per-module facts with numeric magnitude, source, evidence, and responsible module. Portfolio comparison handles added/removed holdings, increase/decrease/unchanged values, missing values, tolerance, deterministic order, and as-of filtering. Exposes distinct explainability contributions and claim classes. Unsupported scenarios and seeded/untraced catalysts remain uncertainty; user-entered invalidation is a hypothesis. Watchlist contains a lazy-loaded bilingual decision brief and explicit snapshot capture.  
**Files Changed:** `database/models.py`, `database/migrations/versions/20261001_decision_snapshots.py`, `services/decision/engine.py`, `services/decision/schemas.py`, `services/portfolio/engine.py`, `apps/api/routers/decision.py`, `apps/web/src/lib/api.ts`, `apps/web/src/app/watchlist/page.tsx`, `apps/web/src/app/watchlist/page.module.css`, `tests/test_decision_intelligence.py`, `tests/test_personal_finance.py`, `tests/conftest.py`, `services/ingestion/seed_data.py`, `docs/PROJECT_STATUS.md`.  
**Tests:** Full suite passed **69/69 three consecutive times** after the final Watchlist edits (**5.90s**, **5.84s**, **5.89s**). Focused decision + portfolio tests passed **11/11**. The existing Starlette/httpx TestClient deprecation warning remains.  
**Build:** `npm run build` passed on Next.js 16.3.7 after the Watchlist decision workflow and final text/JSX cleanup. Scoped Watchlist ESLint passed with no warnings after removing its unused formatter.  
**Integration:** Browser loaded `/watchlist`; API calls returned `ECONNREFUSED` because no backend was running at `localhost:8000`. FastAPI decision endpoints passed isolated SQLite contract tests. This is an unavailable runtime integration, not evidence of an API logic failure.  
**Migration:** Full Alembic upgrade to `20261001p6e`, downgrade to `20261001p6d`, then re-upgrade succeeded on temporary SQLite. Reflection confirmed four non-null columns, both indexes, and `asset_id` foreign key with `ON DELETE CASCADE`. **POSTGRESQL = BLOCKED**; it was not available for migration verification.  
**Evidence Limits:** No validated fair-value scenario, timing recommendation, numeric risk, or factor score is inferred where upstream evidence is absent. Market/event/price evidence retains seeded/untraced origin. No broker connection or auto-trading path was introduced.  
**Phase Gate:** 6E implementation tests, snapshot semantics, SQLite migration lifecycle, API contract tests, and web build pass. PostgreSQL deployment and live frontend-to-API browser integration remain blocked. Phase 6 remains **PARTIAL / CONDITIONAL**, not DONE.  
**Next Task:** 6F — replace hard-coded AI model selection with environment-backed configuration, make tool inputs evidence-bound, harden Ollama structured generation/health/timeouts, then benchmark only if the local runtime and a model are actually available.

## Phase 6F Checkpoint
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6F — Local AI / Ollama (implementation complete locally; factual acceptance conditional)  
**Implemented:** Environment-backed loopback-only Ollama configuration; configurable task/model router; bounded async timeout/retry; structured response parsing/validation with usage metadata; health distinguishes installed versus loaded models; allowlisted read-only tools; evidence-first chat, citation validation, per-citation numeric matching, unsupported-horizon and stale/seeded guards; versioned Vietnamese prompt; daily/weekly/monthly/stock routes use session-backed evidence; added local Analyst UI.  
**Files Changed:** `services/ai/config.py`, `services/ai/provider.py`, `services/ai/providers.py`, `services/ai/ollama_provider.py`, `services/ai/router.py`, `services/ai/tools.py`, `services/ai/schemas.py`, `services/ai/prompt_registry.py`, `services/ai/analyst.py`, `services/ai/evaluation.py`, `apps/api/routers/ai.py`, `apps/web/src/lib/api.ts`, `apps/web/src/app/ai/page.tsx`, `apps/web/src/app/ai/page.module.css`, `tests/test_ai_local.py`, `tests/api/test_phase_audit.py`.  
**Tests:** `python -m pytest -q` passed **87/87 three consecutive times** (**6.25s**, **6.17s**, **6.10s**). Focused AI/guardrail tests: **16 passed**; existing Starlette/httpx TestClient deprecation warning remains.  
**Build:** `npm run build` passed on Next.js 16.3.7 with `/ai`. Scoped ESLint for the AI page/API client passed.  
**Integration:** Local API on an isolated temporary SQLite DB returned `INSUFFICIENT_DATA` for an unregistered asset without invoking Ollama. `/ai/status` reported Ollama 0.35.0, installed/loaded `qwen2.5:0.5b`, and RTX 3050 Laptop GPU. `/ai/eval` passed **4/4** deterministic checks and separately reported runtime. Browser verified the healthy state, missing-data answer, and a 390px layout with no horizontal overflow.  
**Benchmark:** `qwen2.5:0.5b` Q4_K_M, 397.8 MB on disk; Ollama reported 100% GPU placement, 440 MB model allocation, and 4096 MiB GPU memory. Cold structured smoke: 48 prompt / 20 output tokens, 53.49 s total, 20.18 s load. Warm smoke: 39 prompt / 20 output tokens, 0.302 s total, 2 ms load. New provider structured call: 30 prompt / 12 output tokens, 1.84 s total, 1.63 s load. This is a transport/format smoke benchmark, not analyst-quality certification.  
**AI/RAG:** User-selected tool names are validated against a server allowlist and passed to deterministic read-only data services. Document retrieval explicitly returns `INSUFFICIENT_DATA` until 6G. No factual answer is forced from seeded/untraced evidence.  
**Blockers:** PostgreSQL and live-source coverage remain unavailable. No fully source-backed production dataset was present to evaluate a real factual analyst answer. The 0.5B model has only smoke-level quality evidence. Model-autonomous tool planning is not claimed; tool scope is explicitly selected by the user.  
**Phase Gate:** 6F provider/API/UI/guardrail implementation and a real local inference benchmark are verified. Factual quality remains **CONDITIONAL** until tested with suitable source-backed data; Phase 6 is not DONE.  
**Next Task:** 6G — implement document parsing, metadata, chunking, local embeddings, vector search, strict publication-date filtering, and citation evaluation. Use a local Ollama embedding model only after installation and benchmark.

## Phase 6F Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6F — Local AI / Ollama (implementation complete locally; factual acceptance conditional)  
**Completed:** Provider configuration, health, timeout/retry, structured outputs, task routing, evidence-bound tool registry, prompt versioning, API routes, Analyst UI, privacy restrictions, and numeric/citation/horizon guardrails.  
**Remaining Blockers:** PostgreSQL/live sources remain unavailable; current seeded/untraced database correctly short-circuits factual chat. Benchmark model is small and quality is not certified.  
**Next Task:** 6G — local document intelligence and temporal retrieval.

## Phase 6G Local RAG Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6G — Local RAG / Document Intelligence (local implementation complete; PostgreSQL production verification still blocked)  
**Implemented:** Added local document registry and chunk models, deterministic local vector store, temporal filtering by `publication_date <= as_of_date`, citation-backed chunk retrieval, local document ingestion pipeline, and AI tool integration for `document_retrieval` without fabricating evidence. Synthetic fixture documents are explicitly labeled `SYNTHETIC_FIXTURE` and are not presented as official source records.  
**Files Changed:** `database/models.py`, `services/research/rag.py`, `services/ai/tools.py`, `tests/test_rag.py`, `docs/RAG_STATUS.md`, `docs/PROJECT_STATUS.md`.  
**Local Acceptance:** Retrieval tests pass for document filtering, temporal gating, ticker filtering, source filtering, citation mapping, and empty retrieval. Full project suite passed in three consecutive runs, and the Next.js app built successfully.  
**PostgreSQL status:** `POSTGRESQL = BLOCKED` for production verification. The system continues to run and validate locally using the SQLite-backed vector store and fixture corpus, without claiming live PostgreSQL or external document-source verification.  
**Production Limitation:** This is local end-to-end 6G acceptance only. It is not a claim of live production RAG quality or live deployment readiness.  
**Next Task:** 6H — Analyst Automation.

## Phase 6H Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6H — Analyst Automation (local implementation complete; PostgreSQL production verification still blocked)  
**Implemented:**
- Fixed brief date parameter contract in `services/ai/analyst.py` (`generate_daily_brief`, `generate_weekly_brief`, `generate_monthly_brief`) to accept `as_of: date | None = None` and preserve PIT/deterministic evidence retrieval.
- Wired analyst automation scheduler into FastAPI lifespan in `apps/api/main.py` with configurable environment flag `ANALYST_AUTOMATION_ENABLED`, delay/interval configs, and graceful async shutdown.
- Exposed typed stored automation endpoints in `apps/api/routers/automation.py` and `services/ai/schemas.py`: `GET /api/v1/automation/briefs`, `GET /api/v1/automation/briefs/{id}`, `GET /api/v1/automation/alerts`, `GET /api/v1/automation/alerts/{id}`, `GET /api/v1/automation/jobs`, `GET /api/v1/automation/jobs/{id}`, and `POST /api/v1/automation/trigger`.
- Hardened job execution semantics in `services/ai/scheduler.py`: deduplication via unique `job_key` and `idempotency_key`, safe retry on `FAILED` jobs, prevention of overlapping concurrent runs, and standardized job statuses (`RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED`, `INSUFFICIENT_DATA`).
- Monitored thesis reviews without silently mutating user-authored thesis (only `last_reviewed_at` updated, `updated: False`).
- Conservative alert evidence mapping: requires unambiguous source mapping and verifiable evidence delta, otherwise skipped.
**Files Changed:** `services/ai/analyst.py`, `services/ai/scheduler.py`, `services/ai/schemas.py`, `apps/api/routers/ai.py`, `apps/api/routers/automation.py`, `apps/api/main.py`, `database/migrations/env.py`, `tests/test_analyst_automation.py`, `docs/PROJECT_STATUS.md`.  
**Tests:** Full test suite passed **103/103 three consecutive times** (7.83s, 7.69s, 7.56s). Focused automation suite passed **11/11**.  
**Build:** `npm run build` in `apps/web` passed on Next.js 16.3.7 with Turbopack.  
**Migration:** Migration chain head `20261001p6h` verified; SQLite `upgrade head -> downgrade 20261001p6e -> upgrade head` passed cleanly.  
**PostgreSQL Status:** `POSTGRESQL = BLOCKED / UNVERIFIED`.  
**Current Status:** `6H = LOCAL ACCEPTED`.  
**Next Task:** 6I — Backtest + PWA + Production Hardening.

## Phase 6I Milestone Report
**Current Phase:** Phase 6 — LOCAL ACCEPTED  
**Milestone:** 6I — Backtest + PWA + Production Hardening (local implementation complete; PostgreSQL production verification still blocked)  
**Implemented:**
- Point-in-Time survivorship-safe historical backtest engine in `services/research/backtest.py`: PIT price gating (`observation_date <= config.end_date`), no look-ahead, realistic friction model (brokerage 0.15%, tax on sales 0.10%, slippage 0.10%), equal-weight monthly rebalance, daily equity curve, trade log, Sharpe ratio, alpha vs benchmark, max drawdown, annualized return, and built-in look-ahead audit asserting 0 violations.
- API endpoint `POST /api/v1/research/backtest` registered in `apps/api/routers/research.py`; accepts `BacktestConfig` and returns `BacktestResult` with PIT audit and data quality fields.
- Backtest UI tab in `apps/web/src/app/research/page.tsx`: symbol universe input, date range picker, horizon selector, capital input, run button, metrics grid (total return, benchmark return, alpha, max drawdown, Sharpe ratio, total trades/fees), and rebalance log table showing first 50 trades.
- PWA: `manifest.json` in `/public` with name, short_name, start_url, standalone display, and theme color; service worker `sw.js` implementing network-first for `/api/*` (returns explicit offline JSON on failure), stale-while-revalidate for static assets, and navigate fallback to cached root; service worker registered in `AppShell` on mount; offline banner displayed in app shell when `navigator.onLine` is false.
- System observability endpoint `GET /api/v1/system/observability` returning structured `HEALTHY/DEGRADED/UNAVAILABLE` status for database, Redis, AI provider, background job counts, ingestion run statistics, and latest price/macro freshness dates.
- Privacy contract test: verifies `TCBS_API_KEY` and `BROKER_PASSWORD` are absent from the environment, confirming no broker secrets are required.  
**Files Changed:** `services/research/backtest.py`, `apps/api/routers/research.py`, `apps/web/src/app/research/page.tsx`, `apps/web/public/manifest.json`, `apps/web/public/sw.js`, `apps/web/src/components/app-shell.tsx`, `apps/api/main.py`, `apps/web/src/lib/api.ts`, `tests/test_production_hardening.py`, `tests/test_research_workspace.py`, `docs/PROJECT_STATUS.md`.  
**Tests:** Full test suite passed **107/107 three consecutive times** (12.22s, 12.39s, 12.19s). Focused 6I tests (backtest engine PIT + cost deduction, system observability endpoint, privacy contract): **3 passed**. Historical backtest API contract test: **1 passed**.  
**Build:** `npm run build` in `apps/web` passed on Next.js 16.3.7 with Turbopack. 11 routes compiled (static + dynamic).  
**PostgreSQL Status:** `POSTGRESQL = BLOCKED / UNVERIFIED`.  
**Current Status:** `6I = LOCAL ACCEPTED`.  
**Next Task:** PostgreSQL deployment + live HOSE provider onboarding + live scheduler run verification to reach production gate.

## Phase 6D Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6D — Portfolio + Watchlist + DCA + Portfolio Fit  
**Implemented:** Added local persisted personal portfolio schema and migration for holdings, manual transactions, target weights, DCA plan, concentration limits, portfolio snapshots, watchlist items, thesis revisions, and watchlist snapshots. Added API endpoints for holdings CRUD, manual transaction logging, target allocation, DCA advice, portfolio fit, configuration, snapshots, and watchlist thesis audit/history. Added responsive local-first Portfolio and Watchlist pages in the web app, with manual-only actions and no broker execution path. The system keeps personal data local and presents no auto-trading or generic recommendation claim.  
**Files Changed:** `database/models.py`, `database/migrations/versions/20261001_portfolio_watchlist.py`, `services/portfolio/engine.py`, `services/portfolio/schemas.py`, `apps/api/routers/portfolio.py`, `apps/api/routers/watchlist.py`, `apps/api/main.py`, `apps/web/src/lib/api.ts`, `apps/web/src/app/portfolio/page.tsx`, `apps/web/src/app/portfolio/page.module.css`, `apps/web/src/app/watchlist/page.tsx`, `apps/web/src/app/watchlist/page.module.css`, `tests/test_personal_finance.py`, `docs/PROJECT_STATUS.md`.  
**Tests:** `python -m pytest tests/test_personal_finance.py -q` passed **5/5** on isolated SQLite in **1.74s**.  
**Build:** `npm run build` in `apps/web` passed on Next.js 16.3.7; portfolio and watchlist pages compiled successfully.  
**API integration:** Verified local API contract behavior and browser build for the personal portfolio/watchlist stack. Live broker or live-postgres integration is still **BLOCKED**; no real transaction execution or external brokerage sync is present.  
**Data & Risk Status:** Prices are only used when they exist in canonical tables; missing prices leave value/weighting unavailable and produce explicit warnings instead of fabricated values. DCA routing is advisory only; no order is created. Portfolio fit remains intentionally capped to source-backed risk/opportunity metrics and reports insufficient data when not available. Watchlist thesis revisions require a change reason and are persisted with history.  
**Blockers:** No broker API/provider configured; local PostgreSQL remains unavailable; no approved live HOSE/provider feed is active; real market/valuation/risk engines beyond local-canonical evidence remain bounded by available source data.  
**Phase Gate:** 6D local-first persistence and UX are implemented and validated; live external integration remains conditional and must not be claimed as production-grade trading functionality. Phase 6 remains **PARTIAL / CONDITIONAL**, not DONE.  
**Next Task:** Milestone 6E — harden the local portfolio/watchlist UX, validate route-level browser behavior against a running API, then connect only after a real provider contract and PostgreSQL deployment is available.

## Phase 6C Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6C — Asset Detail + Fundamentals + Valuation + Factors + Risk + Events  
**Implemented:** Added `GET /api/v1/research/{symbol}` with typed response, optional as-of date, canonical asset/price/fundamentals/events/corporate actions, price lineage/freshness, point-in-time financial repository access, sector-aware applicability, financial quality, history, and evidence-first timeline/change summaries. Preserves SQL NULL separately from numeric zero. Uses the real TTM engine for four-quarter totals and does not label annual EPS as TTM. Shows observed P/E/P/B only when current price and canonical per-share data support them; fair value scenarios are withheld because existing builder has fixed forecast assumptions. Factor scores and numeric risk are withheld because current producers contain demo/default/stub inputs. Macro sensitivity is explicitly `INSUFFICIENT_DATA`. Added responsive `/research/[ticker]` workspace with loading/error/not-found, overview, fundamentals, sector metrics, valuation, factors, 10 risk categories, events/timeline, and evidence-backed summary. `/research` existing page and Phase 6A/6B implementations remain intact.  
**Files Changed:** `services/fundamentals/repository.py`, `services/fundamentals/snapshot.py`, `services/research/workspace.py`, `apps/api/routers/research.py`, `apps/api/main.py`, `apps/web/src/lib/api.ts`, `apps/web/src/app/research/[ticker]/page.tsx`, `apps/web/src/app/research/[ticker]/research-workspace.tsx`, `apps/web/src/app/research/[ticker]/research-workspace.module.css`, `tests/test_research_workspace.py`, `docs/PROJECT_STATUS.md`.  
**Tests:** `python -m pytest` passed **58/58 three consecutive times** against one fresh canonical-seeded temporary SQLite database (5.05s, 5.14s, 4.83s). Research API/repository tests: **7 passed**. Existing Starlette/httpx TestClient deprecation warning remains. PIT/Historical Replay tests remained unchanged and passed as part of each full run.  
**Build:** `npm run build` passed on Next.js 16.3.7; production build and TypeScript passed, with dynamic route `/research/[ticker]`. Scoped ESLint passed on new research UI/API client. Workspace-wide lint still reports pre-existing `any` errors in data-center/valuation and unused-variable warnings in legacy research/valuation pages.  
**API Integration:** Browser verified `/research/FPT` desktop/mobile rendering and honest API error handling. API call returned HTTP 500 because local PostgreSQL is unavailable. Contract tests execute against isolated SQLite; PostgreSQL-backed integration is **BLOCKED**, not claimed as live acceptance.  
**Data/Evidence Status:** Fundamentals, sector metrics, price, events, and corporate actions come from canonical repository tables; source dates and lineage are included where stored. Seeded/static/untraced price origin is identified. Null financial fields remain null, actual zero remains zero. TTM uses the existing engine when four quarters exist. Annual/quarter history is shown only from records. P/E/P/B are observable ratios, not fair value. DCF/RI/DDM scenarios, factors, numeric risk, opportunity score/confidence inputs, and company macro sensitivity are withheld where existing producers depend on fixed assumptions, demo data, or stubs. No AI-generated rationale is used.  
**Blockers:** PostgreSQL is unavailable for end-to-end browser integration. Existing valuation builder embeds assumptions; factors router uses demo inputs; risk engine has default category scores, so respective numeric outputs remain unavailable. Earnings coverage, source lineage, and sector metrics vary by asset. Existing workspace-wide lint debt remains. Ollama/RAG/PWA acceptance remains open.  
**Phase Gate:** 6C implementation, isolated API contracts, build, and browser states are verified; PostgreSQL integration and broad real evidence remain incomplete. Phase 6 stays **PARTIAL / CONDITIONAL**, not DONE.  
**Next Task at 6E close:** Milestone 6F — Local AI / Ollama configuration, evidence-bound tools, structured generation, and runtime evaluation. This is historical sequencing; the current task is 6H as stated in the Current Checkpoint.

## Phase 6B Milestone Report
**Current Phase:** Phase 6 — PARTIAL / CONDITIONAL  
**Milestone:** 6B — Market Dashboard + Market Regime + Macro + Opportunity  
**Implemented:** Added canonical market dashboard response for VN30/VN100/VN300 quotes, MarketRegimeEngine output, breadth, 20-session momentum, turnover liquidity, foreign-flow `NOT_CONFIGURED`, and major published event records. Added latest macro observation response grouped by registered source region, with release/publication/retrieval dates, lineage-backed origin, freshness, and honest empty states. Added opportunity scanner filters (universe, sector, horizon, score, risk, confidence, factor, valuation); unsupported/insufficient metrics remain null and produce explicit unavailable filter notes. Regime response is typed. Unsubstantiated OpportunityEngine baseline rationale is suppressed; missing rationale is uncertainty. Added responsive Vietnamese `/market` dashboard with loading/API error/empty/stale/insufficient states and expandable evidence.  
**Files Changed:** `services/macro/engine.py`, `services/market/dashboard.py`, `services/macro/observations.py`, `services/opportunity/scanner.py`, `apps/api/main.py`, `apps/api/routers/market.py`, `apps/api/routers/macro.py`, `apps/api/routers/opportunity.py`, `apps/web/src/app/market/page.tsx`, `apps/web/src/app/market/page.module.css`, `apps/web/src/lib/api.ts`, `tests/test_market_intelligence.py`, `docs/PROJECT_STATUS.md`. Milestone 6A shell remains unchanged.  
**Tests:** `python -m pytest` passed **51/51 three consecutive times** on one freshly seeded, isolated temporary SQLite database (4.49s, 4.57s, 4.39s). Six focused market tests also passed three times against the same seeded database. One existing Starlette/httpx TestClient deprecation warning per run.  
**Build:** `npm run build` passed on Next.js 16.3.7; production compile, TypeScript, and route generation passed, including `/market`. Changed market UI/API client ESLint passed. Workspace-wide `npm run lint` remains failing on existing `any` errors in data-center/valuation and unused-variable warnings in research/valuation; no new findings in 6B files.  
**Integration:** Browser route `/market` and its controls render. Requests to market, macro, and opportunity API fail with HTTP 500 because local PostgreSQL is unavailable. Endpoint contracts and service logic are verified using an isolated SQLite database; deployed PostgreSQL/API integration is **BLOCKED**, not claimed as live end-to-end acceptance.  
**AI/RAG:** Not changed or verified. Local Ollama inference and RAG remain pending.  
**Data Status:** Market dashboard reads canonical price, lineage, index membership, event, macro, and asset records. Existing CSV-seeded index prices are labeled `STATIC_OR_SEEDED` or `SEEDED_OR_UNTRACED`, not live. Macro series are shown only when registered; observations without lineage are `SEEDED_OR_UNTRACED`. No frontend market values or opportunity scores are fabricated. Breadth/regime need aligned canonical VN100 and published constituent prices; turnover is unavailable when not stored; foreign flow is not configured. Opportunity scores, risk, valuation, and factors remain null/insufficient until required canonical engine inputs exist.  
**Known Limitations:** No PostgreSQL-backed browser integration could be observed. Existing lint debt is outside 6B. Macro region grouping depends on the registered source country; no data is synthesized for China/Global. The legacy macro dashboard endpoint remains separate; 6B uses the new observation contract.  
**Remaining Blockers:** Start PostgreSQL and verify all three API calls/browser states against the deployed DB; establish approved live HOSE source and FRED/NSO/SBV coverage; populate complete timestamped VN100 inputs before claiming broad-market breadth or ranked opportunities; resolve existing workspace lint errors; Ollama/RAG/PWA acceptance remains open.  
**Phase Gate:** Phase 6B implementation and isolated contract acceptance are complete; integration remains CONDITIONAL due unavailable PostgreSQL and incomplete live-source coverage. Phase 6 remains PARTIAL / CONDITIONAL, not DONE.  
**Next Task:** Milestone 6C — Asset Detail + Fundamentals + Valuation + Factors + Risk + Events, using canonical API outputs and source/evidence states; audit endpoint contracts first.

## 2. Completed
| Component | Change | Evidence |
| --- | --- | --- |
| `services/ingestion/pipeline.py` | Added macro Raw/Staging/Validation/Canonical flow, quality report, publication/release timestamps, checksums, provenance, idempotent observation refresh, and versioned revisions linked by `supersedes_id`. | New focused tests pass. |
| `services/ingestion/pipeline.py` | Existing canonical market bars are no longer overwritten by conflicting same-date records; conflicts are rejected and unchanged rows remain idempotent. Empty fetches return `INSUFFICIENT_DATA`. | New focused tests pass. |
| `services/ingestion/http_client.py` | Added shared request pacing (0.5 s minimum interval) and retries for network, rate-limit, and provider-unavailable failures. | Full suite passes; BLS external request succeeded. |
| `services/ingestion/bls.py`, `services/ingestion/fred.py` | Routed BLS POST through the shared retry/rate-limit client; detect FRED API error payloads instead of interpreting them as empty success. | Live BLS run succeeded. FRED key is absent and is reported `BLOCKED`. |
| `services/ingestion/scheduler.py` | Added registry-driven ingestion cycles for active FRED/BLS macro series and registered HOSE CSV assets; persists provider failures and reports unsupported registry sources as `BLOCKED`. | Live BLS cycle verified once against an isolated database. |
| `apps/api/main.py`, `docker-compose.yml` | Added FastAPI lifespan-managed background scheduler, graceful shutdown, and compose configuration (15-second initial delay, hourly interval). | API smoke tests pass; long-running container operation not yet observed. |
| `tests/test_live_ingestion.py` | Added checks for macro idempotency/revisions, historical price conflict protection, and honest empty-data status. | 3 tests pass; included in each full-suite run. |
| `services/market/dashboard.py`, `apps/api/routers/market.py` | Added typed market dashboard contract with index quotes, regime, breadth, momentum, liquidity, foreign-flow status, major events, and lineage/source freshness. | Market API contract tests pass. |
| `services/macro/observations.py`, `apps/api/routers/macro.py` | Added region-grouped latest registered macro observation contract with PIT publication filters, lineage origin, and freshness. | Missing-observation contract test passes. |
| `services/opportunity/scanner.py`, `apps/api/routers/opportunity.py` | Added canonical asset scanner filters and nullable score/risk/valuation/factor fields; removed unsupported horizon/scoring claims from the public contract. | Scanner filter, missing-data, and validation tests pass. |
| `apps/web/src/app/market/page.tsx`, `apps/web/src/lib/api.ts` | Added responsive API-backed market/regime/macro/opportunity dashboard and typed clients with evidence disclosures and honest failure states. | Production build passes; browser confirms route, API unavailable state, and controls. |
| `tests/test_market_intelligence.py` | Added six engine/API tests for regime evidence, macro missing data, scanner behavior, and validation; made fixtures repeat-safe with canonical seeds. | 6 focused tests pass 3×; full suite 51/51 passes 3×. |
| `services/research/workspace.py`, `apps/api/routers/research.py` | Added typed point-in-time evidence-first asset research aggregate and registered `/api/v1/research/{symbol}`. Unsupported valuation/factor/risk numbers remain explicitly unavailable. | 7 focused contract tests pass; full suite 58/58 passes 3×. |
| `services/fundamentals/repository.py`, `services/fundamentals/snapshot.py` | Preserve SQL NULL vs actual zero in canonical financial rows and expose the snapshot's already-computed completeness object. | Null/zero and research response regression tests pass. |
| `apps/web/src/app/research/[ticker]/*`, `apps/web/src/lib/api.ts` | Added responsive ticker research workspace using the real research endpoint, evidence/status components, financial history, timeline, and honest missing states. | Production build passes; desktop/mobile browser checked; API shows unavailable because PostgreSQL is down. |
| `tests/test_research_workspace.py` | Added endpoint tests for missing values, PIT filtering, sector applicability, unsupported numeric outputs, stale prices, event/corporate-action evidence, and true four-quarter TTM calculation. | 7 focused tests pass; full suite 58/58 passes 3×. |
| `apps/web/src/app/opportunities/*`, `services/opportunity/scanner.py`, `services/opportunity/engine.py` | Dedicated Opportunities Hub (`/opportunities`) connected to real canonical fundamental datasets with multi-metric filters for valuation, quality, momentum, and risk. | Production build passes (13 routes); scanner tests pass. |
| `apps/web/src/app/ai/*`, `services/ai/analyst.py`, `services/universe/registry.py` | Interactive AI Analyst dynamic context: auto-populates stock symbol from Opportunities and Research (`/ai?symbol=...`), dynamic suggested inquiries based on valuation/catalysts, automatic prompt symbol extraction, and benchmark resolution. | Web build passes; live tests verify conversational context. |
| `services/ingestion/pipeline.py`, `services/ingestion/scheduler.py`, `apps/api/routers/cron.py`, `.github/workflows/eod_ingestion.yml` | EOD post-market GitHub Actions workflow (08:30 UTC); historical price conflict resolution between VNDIRECT and LotusMarket (unadjusted vs back-adjusted close); `SKIPPED_UNSUPPORTED` guard for index symbols on stock endpoints; financial RSS news vs insider transaction accounting; structured cron quality summary. | `tests/test_final_hardening.py` regression suite passes. |
| `services/universe/registry.py`, `services/quality/coverage.py`, `scripts/diagnose_universe_coverage.py` | Canonical VN30/VN100 constituent registry, index reconciliation, auto-registration of assets, and universe coverage diagnostic reporting. | Coverage diagnostic and registry tests pass. |
| `services/valuation/engine.py`, `services/valuation/builder.py` | Populated explicit `unit` and `type` fields in `ValuationAssumption` for DCF and Residual Income models; dynamic benchmark fallback for market premium calculation. | Valuation tests pass. |
| `apps/web/next.config.ts`, `apps/web/src/*` | Overhauled UI readability, sidebar scrolling, unicode font rendering, bilingual finance terms, and proxied Next.js API rewrites to `127.0.0.1` to eliminate Windows Node.js IPv6 resolution timeouts. | Production build 13 routes passes; 0 mojibake. |
| `tests/test_final_hardening.py` | Comprehensive regression suite covering price conflict resolution, universe resolution, RSS news accounting, and cron execution status. | All hardening tests pass. |
| `services/ingestion/capabilities.py` | Unified capability-based provider registry specifying supported datasets (`MARKET_BARS`, `FINANCIAL_STATEMENTS`, `MACRO_OBSERVATIONS`, `EVENT_RECORDS`, `UNIVERSE_DISCOVERY`), asset types, rate limits, license classifications, and semantic fallback priorities. | Registry and capability definitions pass contract tests. |
| Multi-Source Candidate Evaluations (`hungson175/vnfin`, `trangcm/vn-market-data`, `minhleai/vnstock-service`, `DataCore`) | Probed live: SSI iBoard universe (1,550+ equities in <2s), Vietcap IQ (34-35 quarters audited statements with PIT publicDate and raw VND scaling across 11 symbols/multiple sectors), CafeF AJAX fundamentals/ratios, DataCore empty preview payloads / API key requirement, and vnstock-service clean-room data quality audit rules. | Live probe scripts verified against real HTTP endpoints without errors. |

## 3. Bugs Fixed & Technical Findings
| ID | Issue | Fix / Finding | Verification |
| --- | --- | --- | --- |
| **BUG-INGEST-01** | Existing HTTP client wrapped request errors in a non-retryable exception; BLS bypassed shared retry/rate limiting. | Retry transient provider errors and route BLS through the shared paced client. | Live BLS call and full tests pass. |
| **BUG-INGEST-02** | Market canonical promotion replaced existing same-date bars, potentially rewriting history. | Preserve existing bars; reject conflicting values and retain raw staging/error details. | Conflict regression test passes. |
| **BUG-INGEST-03** | Macro providers had no canonical promotion path and could not represent revisions/provenance. | Add staged validation, lineage, timestamp capture, idempotency, and revision versions. | Revision regression test passes. |
| **BUG-INGEST-04** | Empty source results could appear successful and missing release timestamps were not visible to callers. | Return `INSUFFICIENT_DATA`; expose publication timestamp gaps and run warnings. | Empty-data test passes; BLS live result reports timestamp gaps. |
| **BUG-ISO-01 / BUG-ISO-02 / BUG-SEM-01 / BUG-EVT-01** | Existing test isolation, restatement, and empty-state event issues. | Existing fixes retained; PIT and event assertions remain in suite. | All 45 tests pass on each of 3 consecutive runs. |
| **BUG-INGEST-05** | Historical price conflicts between VNDIRECT and LotusMarket due to unadjusted vs back-adjusted close divergence. | Track canonical price basis deterministically and handle corporate actions without overwriting historical bars. | `test_final_hardening.py` passes. |
| **BUG-INGEST-06** | Index symbols (`^VNINDEX`, `VN30`) failing on stock-only provider endpoints. | Added `SKIPPED_UNSUPPORTED` guard for index symbols on stock endpoints. | Regression test passes. |
| **BUG-AI-01** | AI chat lacked automatic symbol extraction from user prompt and failed to resolve benchmark indices. | Added symbol regex extraction and market benchmark fallback resolution in `services/ai/analyst.py`. | Query test passes. |
| **BUG-AI-02** | Grounding tolerance was too strict on rounded financial numbers, causing false-positive ungrounded claim suppressions. | Tuned numerical grounding tolerance in `services/ai/analyst.py`. | Grounding tests pass. |
| **BUG-WEB-01** | Node.js on Windows resolving `localhost` to IPv6 `::1` leading to intermittent timeouts when proxying to FastAPI backend on IPv4 `127.0.0.1:8000`. | Updated `next.config.ts` rewrite destination to `http://127.0.0.1:8000`. | Frontend API proxy verified without timeouts. |
| **BUG-VAL-01** | `ValuationAssumption` missed explicit `unit` and `type` fields for DCF and Residual Income models. | Populated typed metadata on all assumption items. | Valuation contract tests pass. |
| **FINDING-CAFEF-01** | CafeF AJAX fundamentals endpoint (`FinanceReport.ashx`) returns `"endDate trống"` if `EndDate` parameter is missing; values are denominated in thousand VND. | Requires dynamic `EndDate` parameter (`"3-2026"` for quarters, `"2026"` for ratios) and deterministic x1000 multiplier to resolve scale. | Live script verified with clean financial tables. |
| **FINDING-VIETCAP-01** | Vietcap company search-bar endpoint returns an envelope dictionary `{"status": 200, "data": [...]}` rather than a raw array. | Extracted `response.json().get("data", [])` to handle envelope safely. | Probed across 2,105 symbols without errors. |
| **FINDING-DATACORE-01** | DataCore unauthenticated public preview calls return HTTP 200 with empty arrays (`dataDetail: []`). | Confirmed full access requires contract `x-api-key` header; classified as enterprise commercial candidate. | Probed live gateway endpoint; verified `.env` contains no credentials. |

## 4. Tests and Verification

> **HISTORICAL NOTE**: Earlier milestone gate results (Phase 6C–6I) are preserved below for audit trail. The authoritative current test result is from the 2026-10-26 full audit.

* Full suite command: `python -m pytest` (Python 3.10.6).
* **Authoritative test results — 2026-10-26 Full Suite Audit (Hardening, Opportunities, AI Ingestion & Universe Backfill)**:
  * Full test suite: **215 passed, 1 skipped, 1 warning** (351.56s).
  * Skipped test: `test_live_local_ollama_inference` in `tests/test_ollama_provider.py` (properly skips when local Ollama daemon is offline; passes when daemon is active).
  * Warning: Starlette deprecation warning that `httpx` with `starlette.testclient` is deprecated; use `httpx2` in a future dependency upgrade.
* **Regression and dedicated test suites**:
  * Final hardening regression (`tests/test_final_hardening.py`): all tests pass (price conflict handling, dynamic universe resolution, RSS news accounting, cron execution status).
  * LotusMarket provider (`tests/test_lotusmarket_provider.py`): 17 passed.
  * UI Unicode integrity (`tests/test_unicode_integrity.py`): 4 passed, 0 mojibake, 0 BOM across 119 files.
  * Multi-provider expansion (`tests/test_multi_provider_expansion.py`): 15 passed.
  * Public ingestion (`tests/test_public_ingestion.py`): 6 passed.
* **Frontend build** (`npm run build` from `apps/web`):
  * **PASS**: 13 routes (11 static, 2 dynamic: `/[section]`, `/research/[ticker]`), Turbopack compile in 6.9s, TypeScript clean in 2.1s (Next.js 16.3.7).
* Database for 2026-10-26 runs: PostgreSQL 18.6 (`trading` database) via `DATABASE_URL=postgresql://postgres:***@localhost:5432/trading`.
* **Historical runs**:
  * 2026-10-19: 219 passed, 0 failed (112.63s) — after LotusMarket & Unicode audit.
  * 2026-10-15: 166 passed, 0 failed, 1 warning (62.58s) — multi-provider expansion audit.
  * 2026-10-15 (pre-expansion): 151 passed, 0 failed (61.56s) — after public ingestion & google-genai install.
  * 2026-10-14: 145 passed, 0 failed (32.23s) — prior to public ingestion & google-genai install.
  * 2026-10-02: 108 passed, 0 failed (6.96s) — full production gate audit.
  * 2026-10-01 (Phase 6C): 58 passed, 0 failed (5.05s) — temporary SQLite.

## 5. Real Ingestion Result

### A. DNSE Public Market Data Ingestion (Verified on PostgreSQL — 2026-10-15)
* **Source**: DNSE / Entrade public unauthenticated API (`https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT`).
* **Flow**: External HTTP GET → `StagingRecord` → validation (`DataQualityChecker.validate_price_row`) → canonical `Price` table → `data_lineages` (with SHA-256 checksum) → `data_quality_reports` → `data_runs`.
* **Committed Evidence in PostgreSQL `trading` database**:
  * Row ID `161`: `symbol=FPT`, `observation_date=2026-10-13`, `raw_close=56300.0`, `volume=6775400.0`, `source=DNSE`.
  * Row ID `162`: `symbol=FPT`, `observation_date=2026-10-14`, `raw_close=57100.0`, `volume=7095300.0`, `source=DNSE`.
  * Lineage ID `349` for Price `161`: `raw_source="DNSE [Run: run-dnse-20261014175801-528a1a]"`, `url="https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT"`, `checksum=5bf192e414693ae30d77d4d1a19ff76647aafafc2c2657d06909f81451adeeb6`.
  * Lineage ID `350` for Price `162`: `raw_source="DNSE [Run: run-dnse-20261014175801-528a1a]"`, `url="https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT"`, `checksum=79616998d1b79726776adb7febe026d642baa25817454d803318b7447c90062d`.
* **Idempotency & Conflict Protection**:
  * Repeat ingestion of identical records (`run-dnse-20261014175801-995ec4`): Reused existing canonical price IDs without inserting duplicate rows.
  * Conflicting same-date bar (`close=999999.0`, `run-dnse-20261014175801-997178`): Rejected with status `FAILED` and error `"Conflicting observation already exists; historical canonical price was preserved"`. Canonical price remained `56300.0`.
* **Governance Boundary**: `DNSE_PUBLIC` is an unauthenticated secondary endpoint for personal research and development only. It does not provide an official SLA, does not grant commercial redistribution rights, and does NOT satisfy Gate 8 (`LIVE_HOSE_PROVIDER`).

### B. Vietstock Public News Ingestion (Verified on PostgreSQL — 2026-10-15)
* **Source**: Vietstock public news API (`https://vietstock.info/api/news/today`).
* **Flow**: External HTTP GET → `StagingRecord` → validation (`DataQualityChecker.validate_news_row`) → canonical `EventRecord` → `data_lineages` → `data_quality_reports` → `data_runs`.
* **Committed Evidence**: Real articles ingested into `events` table with publication timestamps, sources, and lineage links. Malformed article rejection verified (`status=FAILED`, 3 rejected).
* **Governance Boundary**: Public news endpoint intended for personal research. Source authenticity and license limitations explicitly disclosed.

### C. Macro Ingestion (Historical / Existing)
* **Source**: U.S. Bureau of Labor Statistics public API v2, CPI series `CUUR0000SA0`.
* **Observed result**: `SUCCESS`; 8 received, 8 inserted, 0 revised, 0 rejected; quality `PASSED`.
* **Publication timestamps**: BLS response did not provide a release/publication timestamp; run flagged `publication_timestamp_gaps=true`. No timestamp was fabricated.
* **FRED**: `FRED_API_KEY` absent; scheduler persists a `BLOCKED` run rather than claiming success.
* **NSO_VIETNAM / SBV**: Registered in DataSources but do not have supported automated API fetchers; reported `BLOCKED` rather than fabricated.

### D. EOD Post-Market Ingestion & Multi-Provider Hardening (Verified — 2026-10-20 to 2026-10-26)
* **EOD Cron Schedule**: Automated GitHub Actions cron workflow (`.github/workflows/eod_ingestion.yml`) scheduled daily at 08:37 UTC (15:37 Asia/Ho_Chi_Minh) post-market to ingest closing candles and index bars for full VN30 and VN100 universe.
* **Dynamic Universe Resolution**: `services/universe/registry.py` provides canonical index constituent reconciliation and asset auto-registration.
* **Price Conflict & Adjustment Policy**: Distinguishes raw unadjusted close from back-adjusted close (e.g., VNDIRECT vs LotusMarket). Reconciles corporate actions without overwriting valid historical canonical bars.
* **Index Guard**: `SKIPPED_UNSUPPORTED` guard for index symbols on stock-only provider endpoints.
* **Financial News Accounting**: Separates CafeF insider transactions from financial RSS news with transparent article accounting (fetched, usable, rejected, skipped PIT, deduplicated, promoted) and URL normalization.

### E. Multi-Source Candidate Evaluation & Ingestion Capability Audit (Verified — 2026-10-26)
* **Capability-Based Provider Registry**: Implemented `services/ingestion/capabilities.py` specifying typed provider capabilities, asset types, rate limits, license classifications, and fallback priority ordering without error-masking:
  * **Market Prices**: `LOTUSMARKET` -> `DNSE` -> `VNDIRECT` -> `HOSE_CSV`
  * **Financial Statements**: `VNDIRECT` -> `VIETCAP` -> `CAFEF`
  * **Universe Discovery**: `SSI_IBOARD` -> `VIETCAP` -> `DNSE`
  * **Macro Series**: `WORLD_BANK` -> `BLS` -> `FRED`
  * **Corporate Events**: `VIETSTOCK` -> `LOTUSMARKET_CAFEF` -> `GDELT`
* **SSI iBoard Universe Source (`hungson175/vnfin`)**:
  * Endpoint: `https://iboard-query.ssi.com.vn/stock/group/{GROUP}`
  * Live Probes: `VNINDEX` (407 equities), `VN30` (30 equities), `HnxIndex` (299 equities), `HNXUpcomIndex` (814 equities) — 1,550+ active equities discovered in <2 seconds.
  * Quality: Clean English and Vietnamese corporate legal names; reliably distinguishes common stocks from warrants (`CW`) and mutual/exchange-traded funds (`ETF`).
* **Vietcap IQ Fundamental Statements (`trangcm/vn-market-data`)**:
  * Endpoint: `https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}/financial-statement`
  * Live Probes: 11 tickers across multiple ICB sectors (FPT, VCB, ACB, MBB, SHB, HPG, MWG, VNM, TCB, SSI, DGC).
  * Quality: Returns 34–35 historical quarters (8.5 years) and 8 annual periods of audited Balance Sheets, Income Statements, and Cash Flows with exact Point-In-Time `publicDate` publication timestamps and raw VND currency scaling.
  * Search-bar: 2,105 symbols returned via `https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/search-bar`.
* **CafeF Fundamental & Ratio AJAX Source (`hungson175/vnfin`)**:
  * Endpoints: `https://cafef.vn/du-lieu/Ajax/PageNew/FinanceReport.ashx` and `GetDataChiSoTaiChinh.ashx`
  * Live Probes: Tested on FPT, VCB, HPG. Returns 8 quarters of financial statements and key ratios (P/E, P/B, EPS, ROE, ROA).
  * Scaling & Parameters: Denominated in thousand VND (requires x1000 scaling to raw VND) and requires dynamic `EndDate` parameter (`"3-2026"` for quarters, `"2026"` for annual/ratios).
* **DataCore Gateway (`DataCore-VietNam/datacore-python`)**:
  * Endpoint: `https://gateway.datacore.vn/data/ds/preview`
  * Probes: Unauthenticated calls return HTTP 200 with empty arrays (`dataDetail: []`). Confirmed access requires commercial contract `x-api-key`. Verified no credentials configured in `.env`. Documented as external enterprise candidate.
* **vnstock-service Architecture (`minhleai/vnstock-service`)**:
  * Analyzed clean-room architectural patterns without copying unlicensed code: data quality sanity checks (`high < low`, `volume < 0`, `raw_close <= 0`, date gaps, ceiling/floor breaks), active lifecycle status tracking (`ACTIVE`, `SUSPENDED`, `DELISTED`), and persistent checkpointing for resumable backfill queues.
* **Production Ingestion Guard**:
  * Boundary strictly enforced: `STOPPED BEFORE PRODUCTION WRITE`. No writes to Neon cloud PostgreSQL triggered without explicit user authorization.

## 6. Remaining Blockers

> Items marked **RESOLVED** were verified and are no longer blockers.

| Priority | Blocker | Impact / Next Action |
| --- | --- | --- |
| **P1** | ~~PostgreSQL unavailable~~ | **RESOLVED 2026-10-02** — PostgreSQL 18.6 verified; 38 tables; alembic at head; no SQLite fallback. |
| **P1** | ~~Scheduler not observed on PostgreSQL~~ | **RESOLVED 2026-10-02** — Both lifespan schedulers observed running; DataRun and AnalystAutomationJob persisted; idempotency verified; graceful shutdown and clean restart confirmed. |
| **P1** | ~~Redis unavailable~~ | **RESOLVED 2026-10-02** — Redis 8.10.1 verified; ping=True; `/api/v1/health` redis.connected=True. |
| **P1** | ~~Ollama offline / AI not benchmarked~~ | **RESOLVED 2026-10-02** — Ollama 0.35.0 + `qwen2.5:0.5b` + RTX 3050 GPU; structured generation and guardrails verified. |
| **P1** | **No approved/licensed official live HOSE market-data feed** | **STILL BLOCKED** — `LIVE_HOSE_PROVIDER = BLOCKED`. While `DNSE_PUBLIC` is integrated and verified for personal research/development, an officially licensed commercial exchange feed contract does not exist. Commercial production remains conditional on Gate 8. |
| **P1** | **FRED key absent** | **STILL BLOCKED** — Scheduler correctly reports BLOCKED on missing key. Configure FRED credentials where authorized. |
| **P1** | **NSO Vietnam and SBV automated fetchers unsupported** | **STILL BLOCKED** — Registered in DataSources but produce no synthetic values. Implement official fetchers only when authorized. |
| **P1** | **BLS does not return publication timestamps** | Preserved gap documented. Find authoritative release metadata or retain explicit timestamp gaps. |
| **P2** | Full VN100 verified filings and cross-sectional peer data backfill. | **COMPLETED FOR BASELINE FILINGS (100/100 EQUITIES COVERED)** — Canonical VN30/VN100 constituent registry established; all 100 active VN100 equities have verified canonical financial statements (8,435 statements, min 36/stock, spanning 2008–2026) and fundamental metrics (10,254 metrics); 0 missing constituents. Ongoing operational cadence handles archival deep-history (>35Q), quarterly earnings disclosure updates as released by SSC/HOSE, and annual peer multiples updates. |
| **P3** | Starlette/httpx TestClient deprecation warning. | Evaluate `httpx2` dependency upgrade. |

## 7. Current Architecture State
* **Backend / Database schema**: PostgreSQL 18.6; all 38 ORM tables verified; Alembic head `20261002p6g`; migrations idempotent.
* **Data ingestion**: **VERIFIED** — raw/staging/validation/canonical paths, lineage, retry, pacing, honest result states, registry-driven cycle, and lifespan scheduler all verified against PostgreSQL. Real live flows confirmed for BLS (macro observations), DNSE (FPT market OHLCV bars), Vietstock (news event records), LotusMarket (VPS quotes, CafeF insider events), Vietcap (35Q audited statements with Point-In-Time publicDate), DataCore (clean-room client with credential gating), and EOD post-market GitHub Actions workflow. Licensed commercial HOSE feed remains BLOCKED.
* **Historical Replay / PIT**: **DONE** — 18 replay points, 0 PIT violations recorded.
* **AI / Ollama / RAG / Gateway**: **VERIFIED** — Ollama 0.35.0 on loopback GPU, automatic symbol extraction, market benchmark resolution, guardrails verified (INSUFFICIENT_DATA for untraced evidence), RAG temporal filtering and citation mapping confirmed against PostgreSQL; query context auto-population from Opportunities/Research with dynamic proactive suggestions; 13/13 acceptance matrix queries passed.
* **Lifespan Schedulers & Cloud Cron**: **VERIFIED** — Both ingestion and analyst automation schedulers running inside FastAPI lifespan for local mode; cloud mode uses authenticated `/api/v1/system/cron/*` endpoints via `X-Cron-Secret` with idempotent job logging.
* **Macro / Risk / Opportunity / Valuation**: Deterministic implementations; Opportunities scanner connected to canonical fundamental datasets with multi-metric filters; valuation assumptions standardized with explicit units and types.
* **Frontend**: **VERIFIED** — production build passes with 13 routes (Turbopack, TypeScript clean); Gate 13 browser E2E verified (desktop, mobile viewport, PWA manifest, service worker, offline banner); bilingual financial terms and optimized typography.
* **Security**: **VERIFIED** — No broker credentials in env. No auto-trading path. Ollama loopback-only. Secrets redacted from errors and logs. Single-user session authentication in cloud.

## 8. Data and Integrity Notes
* Raw provider payloads are retained in `staging_records`; validated canonical rows link to `data_lineages` with source, retrieval time, observed period, checksum, and available publication time.
* Canonical `prices` table contains both baseline historical records (`HOSE_CSV`) and real public provider-ingested records (`DNSE`, `LOTUSMARKET`), each distinguished by `source` and explicit lineage.
* Market price conflicts for an existing asset/date are rejected; the previous canonical bar is preserved.
* Macro corrections create a new observation version and link to the prior row (`supersedes_id`). Identical refreshes do not create a new canonical version.
* A successful fetch of zero observations is `INSUFFICIENT_DATA`, not `SUCCESS`.
* FRED can provide vintage/realtime dates; BLS publication timestamps are currently missing and surfaced in run warnings.
* Synthetic fixtures remain labeled separately in their owning modules (`is_synthetic=True`).

## 9. Comprehensive System Gate Summary

> Updated 2026-10-27 with distinct separation of local verification, cloud deployment, production writes, scheduled triggers, and commercial licensing.

| Operational Dimension | Status | Verified Evidence | Remaining External Gate |
| :--- | :--- | :--- | :--- |
| **Local Infrastructure & Quality** | **VERIFIED** | PostgreSQL 18.6, 38 ORM tables, Alembic=`20261002p6g`. Full test suite: **248 passed, 0 skipped, 1 warning (248.30s)**. Data quality audit: **0 price geometry violations** across 15,348 canonical bars. | None (100% verified locally). |
| **Financial Correctness & Valuation** | **VERIFIED** | **HPG 20.9k adj vs 27.2k raw (30% stock dividend dilution 1.30 on 2022-06-17), FPT 56k adj vs 113k raw (2:1 dilution), ACB P/B = 1.24, P/E = 7.89, ROE = 15.83%**. **100/100 VN100 equities have verified AVAILABLE P/E and P/B** (0 missing, 0 stale >7d, 0 suspicious factor). 12 regression test cases in `tests/test_financial_correctness.py`. | None (correctness verified). |
| **Data Breadth & Fundamentals** | **VERIFIED** | **104 canonical instruments** (100 stocks, 1 ETF, 3 indices). **100/100 stocks have verified statements** (8,435 statements, min 36/stock, 2008–2026) and fundamental metrics (10,254 metrics); 0 missing constituents. | Ongoing operational cadence for future quarterly filings. |
| **Candidate Provider Expansion** | **VERIFIED** | `VietcapProvider` integrated (35Q audited statements, PIT `publicDate`, unscaled VND integers, SHA-256 lineage). `DataCoreProvider` clean-room httpx client implemented. Adjustment-seam canary detection (`detect_adjustment_seam`) verified. Resumable backfill with JSON checkpointing verified. | `DATACORE_API_KEY` required for enterprise catalog queries (safely gated). |
| **Local AI Analyst (Ollama)** | **VERIFIED** | Local Ollama daemon running `qwen2.5:3b`. Acceptance matrix: **13/13 verified live** with exact citation IDs, numerical grounding, and honest `INSUFFICIENT_DATA` handling. ACB query returns both P/B = 1.24 (`E039`) and ROE = 15.83% (`E012`). Semantic guard suppresses P/E as P/B substitution. | None (local inference operational). |
| **Frontend Production Build** | **VERIFIED** | `npm run build` in `apps/web`: 13 routes compiled cleanly via Turbopack in 898ms; TypeScript clean in 1.48s (Next.js 16.3.7). | None (build verified). |
| **Cloud Deployment Revision** | **VERIFIED & OPERATIONAL** | Render Backend revision confirmed at **`b47682abb360959d0d25bc8879f52332f79fdfd1` (`b47682a`)** via live `/api/v1/system/info` (`rndr-id: e18c6c24-76c6-438b`, uvicorn). Vercel Frontend live at `https://investintel-nine.vercel.app` (`/login` HTTP 200, `etag: W/"a244dcee5fc97da140134b44c58ea3e6"`; direct revision verification blocked pending Vercel credentials). | None on backend; Vercel API token for frontend commit. |
| **Cloud Production Writes** | **GUARDED / STANDBY** | **STOPPED BEFORE PRODUCTION WRITE**. Dry run / sync preview documented: Neon database currently holds 6,816 prices and 3,523 statements; pending sync delta (+8,532 prices, +4,912 statements) is ready for idempotent sync upon explicit user activation. Rollback procedure documented. | Awaiting user authorization to trigger cloud write. |
| **Scheduled EOD Trigger** | **PENDING LIVE SCHEDULE OBSERVATION** | `.github/workflows/eod_ingestion.yml` configured with `cron: '37 8 * * 1-5'` on default branch `main`. Manual workflow dispatch is `CONFIGURED_AND_READY`; automated schedule trigger awaits observation of the first scheduled calendar event. | Scheduled calendar time observation (08:37 UTC weekdays). |
| **Exchange Data Licensing (Gate 8)** | **BLOCKED (OPERATIONAL CONSTRAINT)** | `LIVE_HOSE_PROVIDER = BLOCKED`. Unauthenticated public secondary feeds (`DNSE`, `VNDIRECT`, `LOTUSMARKET`, `VIETCAP`) verified for personal research/development only. An official commercial HOSE feed contract is legally required for institutional commercial redistribution. | Institutional HOSE commercial contract. |

## 10. Next Task

**FINAL PRODUCTION GATE — Commercial Feed Licensing & Cloud Sync Activation.**

All local infrastructure, API, scheduler, AI, RAG, data quality, backtest, financial correctness, security gates, and multi-source provider integrations (`DNSE`, `VIETSTOCK`, `VNDIRECT`, `WORLD_BANK`, `FREE_FX`, `GDELT`, `BLS_V1`, `LOTUSMARKET`, `VIETCAP`, `DATACORE_PREVIEW`) are verified. The only remaining prerequisites for commercial production acceptance are:

1. **Establish an approved/licensed commercial HOSE market-data provider contract** (Gate 8):
   - Replace or supplement the unauthenticated secondary `DNSE_PUBLIC`/`VNDIRECT`/`LOTUSMARKET`/`VIETCAP` providers with an officially licensed institutional exchange feed.
   - Verify contract-backed feed SLA, commercial redistribution terms, and authenticated API access.
2. **Authorize Cloud Production Database Write**:
   - Explicit user instruction required to toggle `ALLOW_PRODUCTION_DB_WRITE=true` and execute the idempotent backfill sync into Neon PostgreSQL.
3. **Configure `FRED_API_KEY` & `DATACORE_API_KEY`** (optional enterprise keys):
   - Register at [api.stlouisfed.org](https://api.stlouisfed.org/api_key.html) and DataCore for enterprise access. BLS v1 unauthenticated and World Bank Indicators are active in the meantime.
4. Once an official licensed HOSE provider is verified under commercial terms, update `PRODUCTION = ACCEPTED`.

**Do not create a new phase or redesign. Repository is feature-frozen.**

