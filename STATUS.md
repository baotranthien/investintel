# InvestIntel — Executive Status & Deployment Summary

Authoritative as of: **2026-10-19**

## 1. Overall System Status
- **Architecture**: **Phase 0–6I + Multi-Provider Free Data Expansion + Cloud Deployment + UI Unicode Integrity + LotusMarket Integration COMPLETE**
- **Test Suite**: **219 / 219 PASSED (100% Pass Rate)**
- **Frontend**: **12 routes compiled cleanly** (Turbopack, TypeScript 100% clean, PWA active, 0 mojibake / 0 BOM)
- **Deployment Status**:
  - **Backend**: Render Free Web Service (`https://investintel-api.onrender.com`) — LIVE (`/health` & `/ready` HTTP 200 OK)
  - **Frontend**: Vercel Hobby Next.js PWA (`https://investintel-nine.vercel.app`) — LIVE (`/login` HTTP 200 OK)
  - **Database**: Neon PostgreSQL Free (SSL required, connection pooling limits, cold-start bounded retry) — LIVE
  - **Scheduling**: cron-job.org calling authenticated, idempotent job endpoints — READY (supports targeted symbols and providers)
- **Production Ingestion Guard**: **STOPPED BEFORE PRODUCTION WRITE** (All LotusMarket adapters, schemas, and tests verified locally; awaiting user approval before triggering first cloud ingestion).

---

## 2. Key Milestones Completed

### LotusMarket Integration (2026-10-19)
- **Data Provider Adapter**: Added `services/ingestion/lotusmarket.py` wrapping verified capabilities from `ducnhd/lotusmarket` (MIT License):
  - **VPS Real-Time Quotes**: Quotes, open/high/low/close, ref price, ceiling/floor, foreign buy/sell/net flow, and bid/ask volume scaled to VND.
  - **Entrade Historical OHLCV**: Daily candles with VPS intraday fallback, Vietnam timezone UTC+7 normalization.
  - **CafeF Insider Trading**: Shareholder and insider transactions promoted to canonical `EventRecord` with Point-In-Time timestamps.
  - **KBS Fundamentals**: Bounded error handling (graceful degradation on HTTP 400/404 without fabricating data).
- **Lineage & Pipeline**: StagingRecord, DataRun, DataQualityReportRecord, and DataLineage tracking preserved. Conflicting records rejected to protect canonical prices.
- **Targeted & Bounded Scheduling**: Added `symbols` and `providers` filters to `run_ingestion_cycle` and `POST /api/v1/system/cron/run-ingestion`. Guarantees bounded one-time ingestion for specific approved tickers without launching full universe or unrelated macro providers.
- **Automated Test Suite**: Added `tests/test_lotusmarket_provider.py` (17 deterministic offline tests passing 100%).
- **Total Test Count**: **219 / 219 tests PASSED**.

### UI Unicode & Vietnamese Integrity Audit (2026-10-19)
- **Full Scope Audit**: Scanned 119 frontend and API router source files across `apps/web/src`, `apps/api/routers`, and `services`.
- **Mojibake Root Cause & Fix**: Resolved Windows-1252 / UTF-8 double-encoding in `apps/web/src/app/portfolio/page.tsx`. Restored clean Vietnamese accents across all positions, action buttons, notifications, error states, and form labels (`Danh mục`, `không đặt lệnh`, `Làm mới`, `Tổng giá trị`, `Chưa có holding`, etc.).
- **BOM Sanitization**: Removed UTF-8 Byte Order Mark (`\xef\xbb\xbf`) from `apps/web/src/app/portfolio/page.tsx` and `apps/web/src/app/watchlist/page.tsx`.
- **API Template Integration**: Connected portfolio template loading to `getPortfolioTemplates` in `@/lib/api` with authenticated credentials.
- **Automated Regression Suite**: Added `tests/test_unicode_integrity.py` with 4 dedicated automated tests verifying absence of corrupted byte sequences, replacement characters (`\ufffd`), and BOM across frontend and API routers.

### Data & Financial Intelligence
- **Canonical Financial Statements**: 115 Income Statements, 115 Balance Sheets, 115 Cash Flows (100% matched across 23/23 quarters for FPT, VCB, MBB, MWG, HPG).
- **Historical Market Bars**: 8,465 daily OHLCV candles (2020–2026) ingested with provenance lineage and EOD CSV backups.
- **Macro Data**: FRED 10Y (1,698 observations via public CSV fallback), GSO GDP/CPI and SBV reference rates (78 observations) Point-In-Time compliant.
- **RAG Document Intelligence**: 68 chunks across 5 core assets with temporal publication-date filters.
- **Analytical Engines Active**: DCF, Residual Income, EV/EBITDA, P/E, 7-Factor Scoring, 10 Risk Categories, Decision Snapshots, and Point-In-Time Historical Backtesting (+67.34% return, +17.05% Alpha over VN100).

### Cloud Readiness & Security
- **Single-User Private Authentication**: PBKDF2-HMAC-SHA256 password hash, server-issued `investintel_session` cookie (`HttpOnly`, `SameSite=Strict`, `Path=/`, 7-day TTL), Origin/CSRF verification, rate-limiting on failed logins, `Cache-Control: private, no-store`.
- **Public Health & Readiness Probes**:
  - `GET /health` → 200 `{"status":"ok"}`
  - `GET /ready` & `GET /api/v1/ready` → 200 `{"status":"ready"}` (checks DB reachability, zero credential leakage).
  - Private APIs (`/portfolio`, `/watchlist`, `/research`, etc.) strictly require session auth (401 Unauthorized).
- **Cloud Schedulers**: In-process background loops disabled on cloud; replaced by idempotent endpoints:
  - `POST /api/v1/system/cron/run-ingestion`
  - `POST /api/v1/system/cron/run-analyst`
  - Protected by `X-Cron-Secret` header constant-time verification (`hmac.compare_digest`), supporting bodyless POST requests.
- **Zero-Budget Cloud AI Gateway**: Gemini (5-attempt max) → Groq → OpenRouter (strictly `:free` models) → reachable Ollama → typed `AI_UNAVAILABLE`. `AI_ALLOW_PAID_APIS=false` preserved.

---

## 3. Preserved Operational Gates
- `LIVE_HOSE_PROVIDER`: **BLOCKED** (Official licensed commercial HOSE feed contract is not established; unauthenticated DNSE/VNDirect/LotusMarket used for personal research).
- `LIVE_GEMINI`: **NOT_VERIFIED** (Gateway architecture verified 100%; live inference requires user's active API key).
- `PRODUCTION`: **CONDITIONAL** (Cloud deployed and functional; live scheduled cron activation and first production ingestion pending user approval).

---

## 4. Detailed Documentation References
- Canonical Project Status: [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- Complete Progress & Bottleneck Synthesis: [`docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md`](docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md)
- Cloud Deployment & Setup Guide: [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)
