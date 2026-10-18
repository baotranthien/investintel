# InvestIntel — Executive Status & Deployment Summary

Authoritative as of: **2026-10-19**

## 1. Overall System Status
- **Architecture**: **Phase 0–6I + Multi-Provider Free Data Expansion + Cloud Deployment + UI Unicode Integrity + LotusMarket Integration + VN100/VN30 Real Index Candles + Financial News RSS Provider + Cloud AI Observability + Live End-to-End Production Validation COMPLETE**
- **Test Suite**: **226 / 226 PASSED (100% Pass Rate)** in 154s (`python -m pytest -q`)
- **Frontend**: **12 routes compiled cleanly** (Turbopack, TypeScript 100% clean, PWA active, 0 mojibake / 0 BOM)
- **Deployment Status**:
  - **Backend**: Render Free Web Service (`https://investintel-api.onrender.com`) — **LIVE at commit `d339473`** (`/health` & `/ready` HTTP 200 OK)
  - **Frontend**: Vercel Hobby Next.js PWA (`https://investintel-nine.vercel.app`) — **LIVE** (`/login` HTTP 200 OK)
  - **Database**: Neon PostgreSQL Free (SSL required, connection pooling limits, cold-start bounded retry) — **LIVE & VERIFIED**
  - **Scheduling**: `GET /api/v1/system/cron/history` & `POST /api/v1/system/cron/run-ingestion` — **LIVE & TESTED** with constant-time `X-Cron-Secret` verification and idempotency deduplication
- **Production Data Integrity**:
  - **434 Canonical Prices** (62 prices each for `FPT`, `VCB`, `MBB`, `MWG`, `HPG`, `VN100`, `VN30`)
  - **0 Duplicate Prices** verified in Neon database (`GROUP BY asset_id, observation_date HAVING count(id) > 1`)
  - **45 Canonical Events** (40 live Vietnamese financial news articles from CafeF & VnEconomy RSS feeds + 5 corporate/macro events)
  - **345 Financial Statements** (69 per ticker across FPT, VCB, MBB, MWG, HPG: 115 income, 115 balance sheets, 115 cash flows)
  - **2,272 Macro Observations** across 15 series (DGS10, CPI, GDP, SBV policy rates, USD/VND, World Bank)
  - **18 Index Memberships** active across VN100, VN30, VN300

---

## 2. Key Milestones Completed

### Verified End-to-End Production State & Audit (2026-10-19)
- **Resolved Ingestion Execution Uncertainty**:
  - Audited historical run evidence in `AnalystAutomationJob`, `DataRun`, and `DataQualityReportRecord` on Neon.
  - Confirmed that repeated historical POST requests hit the idempotency check and returned `ALREADY_COMPLETED`, preserving canonical prices without creating duplicate writes.
  - Exact price duplicate check returns **`duplicate_prices_count: 0`**.
- **Live Endpoint Security & Smoke Tests**:
  - `/health` $\rightarrow$ 200 OK `{"status":"ok"}`.
  - `/ready` $\rightarrow$ 200 OK `{"status":"ready"}`.
  - `/api/v1/system/info` $\rightarrow$ 200 OK (`git_commit: d339473`, `db: connected (postgresql, ~6ms)`).
  - `/api/v1/system/observability` $\rightarrow$ 200 OK (`total_price_records: 434`, 62 per ticker/index).
  - Unauthenticated access to private endpoints strictly returns **HTTP 401 Unauthorized**.

### Market Data Pipeline Completion (2026-10-19)
- **Index Data Ingestion Engine**:
  - Discovered that Entrade separates index candles at `https://services.entrade.com.vn/chart-api/v2/ohlcs/index` (scaled $1.0\times$ in index points).
  - Enhanced `services/ingestion/lotusmarket.py` and `services/ingestion/scheduler.py` to route `VN100` and `VN30` to `/ohlcs/index`, auto-create benchmark `Asset` records, and seed `IndexMembership` for `VN100` with the core constituents (`FPT`, `VCB`, `MBB`, `MWG`, `HPG`).
  - Successfully executed bounded cloud ingestion for `VN100` and `VN30`, storing **62 canonical daily candles for VN100** and **62 for VN30**.
- **Market Dashboard Activation**:
  - **Market Regime**: `NEUTRAL` (confidence 0.65).
  - **Market Breadth**: `80.0%` advancing (`4 advancing, 1 declining, 0 unchanged`) — marked **`AVAILABLE`**.
  - **20-Session Momentum**: `-5.87%` (`window_sessions: 20`) — marked **`AVAILABLE`**.
  - **Index Quotes**: `VN30: 1855.41` (`AVAILABLE`), `VN100: 1751.58` (`AVAILABLE`), `VN300: INSUFFICIENT_DATA` (honestly retained).

### Real Financial News RSS Ingestion Engine (2026-10-19)
- **Provider Architecture**: Implemented `services/ingestion/financial_news.py` (`FinancialNewsProvider`):
  - Ingests public, permitted RSS feeds from **CafeF** (Market & Corporate feeds) and **VnEconomy** (Stock feed).
  - Robust error handling: sanitizes malformed XML, strips HTML, handles network timeouts and HTTP 429 rate limits.
  - Point-In-Time deduplication: stable URL hashing to prevent duplicate articles.
  - Entity & Ticker Extraction: regex word-boundary mapping (`\b(FPT|VCB|MBB|MWG|HPG)\b`) with sector classifications (`BANK`, `MATERIALS`, `RETAIL`, `TECHNOLOGY`).
  - Sentiment & Materiality Classifier: rule-based Vietnamese financial dictionary (`tăng trưởng`, `lợi nhuận`, `thua lỗ`, `nợ xấu`, etc.).
  - Promotes articles to canonical `EventRecord`s with Point-In-Time timestamps, SHA-256 raw checksums, and `DataLineage` tracking.
- **Production Execution**: Bounded production run executed on Render: **40 real financial news articles** staged, promoted, and connected to the research timeline and market dashboard major events.
- **Test Suite**: Added `tests/test_financial_news.py` with 7 dedicated unit tests covering XML parsing, ticker matching, duplicate prevention, and pipeline promotion.

### Cloud AI Availability & Gateway Telemetry (2026-10-19)
- **Root Cause & Fix**:
  - Production observability previously reported AI as `UNAVAILABLE` because `apps/api/main.py` was hardcoded to probe `localhost:11434` Ollama, treating the cloud container as the user's personal machine.
  - Replaced loopback probe with dynamic `AIGateway().status()` telemetry.
  - Updated `services/ai/config.py` to support multi-variable detection (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_GENAI_API_KEY`, `GEMINI_KEY`), defaulting to `gemini-3.8-flash` with circuit breaker and bounded backoff.
- **Production Status**:
  - Telemetry cleanly reports `AI unavailable (none)` with HTTP 200 via `/api/v1/system/info` and `/api/v1/system/observability`.
  - Deterministic financial calculations, market regime, valuation models, and risk analysis operate completely independently of AI availability without crashing or timeouts.

### Cron & Idempotency Safeguards (2026-10-19)
- **Cron History Endpoint**: Added `GET /api/v1/system/cron/history` protected by `X-Cron-Secret` constant-time verification. Exposes job summaries, recent data runs, total prices, and duplicate price counts directly from the database.
- **Idempotency Guard**: Tested live on Render: repeating an ingestion request without `force: true` immediately returns `ALREADY_COMPLETED`, skipping redundant executions and preventing duplicate writes.
- **Sanitization Fix**: Moved `_sanitize()` to module level in `apps/api/routers/cron.py`, eliminating potential `NameError` during analyst brief execution.

---

## 3. Preserved Operational Gates & Real Limitations
- `LIVE_HOSE_PROVIDER`: **BLOCKED** (Official licensed commercial HOSE feed contract is not established; unauthenticated Entrade/VPS/LotusMarket used for personal research).
- `RECURRING_SCHEDULER`: **PENDING EXTERNAL ACTION** (Endpoints are ready and secured via `X-Cron-Secret`. Configuring the weekday post-market scheduled trigger requires external login to `cron-job.org` or an equivalent scheduling service).
- `VN300_BENCHMARK`: **INSUFFICIENT_DATA** (VN300 index candles are not available on Entrade; feature is honestly marked `INSUFFICIENT_DATA` rather than fabricating values).

---

## 4. Documentation References
- Canonical Project Status: [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- Complete Progress & Bottleneck Synthesis: [`docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md`](docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md)
- Cloud Deployment & Setup Guide: [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)
