# InvestIntel — Executive Status & Deployment Summary

Authoritative as of: **2026-10-28 / 2026-11-01**

## 1. Overall System Status
- **Architecture**: **Phase 0–6I + Multi-Provider Free Data Expansion + Cloud Deployment + UI Unicode Integrity + LotusMarket Integration + VN100/VN30 Real Index Candles + Financial News RSS Provider + Complete Gemini Removal & Local Ollama Only + Cloud AI Isolation + Point-in-Time Data Integrity & IAS 33 Dynamic Audit + Local AI Analyst Multi-Ticker Repair + Banking & Macro Commodity Expansion + True Apple Daylight & Warm Neutral Minimalism Redesign + Local AI Analyst Qwen3.5 9B Model Upgrade COMPLETE**
- **Test Suite**: **323 / 323 PASSED (100% Pass Rate)** across entire repository (`python -m pytest tests -q`)
- **Frontend**: **13 routes compiled cleanly** (Next.js 16.3.7, React 19.2.8, Turbopack, TypeScript 100% clean, 0 errors, 0 warnings, 0 mojibake / 0 BOM)
- **Deployment Status**:
  - **Backend**: Render Free Web Service (`https://investintel-api.onrender.com`) — **LIVE at commit `eb4b634`** (`/health` & `/ready` HTTP 200 OK, Neon latency 11.16ms)
  - **Frontend**: Vercel Hobby Next.js PWA (`https://investintel-nine.vercel.app`) — **LIVE** (`/` and `/login` HTTP 200 OK, ETag `"68212e5a0df9341e19b841cd9af812cb"`)
  - **Database**: Neon PostgreSQL Free (SSL required, connection pooling limits, cold-start bounded retry) — **LIVE & VERIFIED**
  - **Scheduling**: `GET /api/v1/system/cron/history` & `POST /api/v1/system/cron/run-ingestion` — **LIVE & TESTED** with constant-time `X-Cron-Secret` verification and idempotency deduplication
- **Data Integrity & Storage (Local vs. Cloud)**:
  - **Local Database (Active Development)**:
    - **15,554 Canonical Prices** across 100 active equities + `VN100` & `VN30` benchmark indices
    - **8,435 Financial Statements** (Balance Sheets, Income Statements, Cash Flows)
    - **3,402 Macro Commodity Observations** (Daily Brent and WTI crude oil benchmarks aligned with equities)
    - **10 Bank-Specific Financial Metrics** (NIM, CASA, Credit Growth, NPL, LLR for VCB, MBB, TCB, BID, CTG)
    - **3,224 Canonical Events & News Records** (Real Vietnamese financial news from CafeF, VnEconomy, Vietstock RSS + macro events)
    - **2,285 Macro Observations** across 15 national/international macro series (DGS10, CPI, GDP, SBV policy rates, USD/VND, World Bank)
    - **104 Tracked Assets** (100 VN100/VN30 active equities + benchmark index assets)
    - **149 Index Memberships** active across VN100, VN30, VN300
    - **0 Duplicate Prices** verified (`GROUP BY asset_id, observation_date HAVING count(id) > 1`)
  - **Neon Cloud Database (Read-Only Production Safety Hold)**:
    - **6,816 Prices** & **3,523 Financial Statements**
    - Production write protection strictly active (`ALLOW_PRODUCTION_DB_WRITE=false`)

---

## 2. Authoritative 8-Gate Evaluation Summary (2026-11-01)

| Gate | Name | Required Condition | Status | Evidence / Verification |
| :--- | :--- | :--- | :---: | :--- |
| **GATE 1** | Local Software Tests | All data contracts, financial correctness, and regression tests pass (exit code 0) | **PASS** | **323 / 323 passed (100%)** in test suite; 57 regression subset tests passed. |
| **GATE 2** | Financial Data Contracts | Price geometry enforced, share priority guaranteed, valuation outliers unmasked, TTM continuous | **PASS** | In-memory contract invariants validated across Price, ShareResolution, Continuity, and Valuation. |
| **GATE 3** | Source Reconciliation | Dynamic universe reconciliation against external sources; isolate exact discrepancies | **PARTIAL** | 100 active equities evaluated: Operational P/E 94/100 matched (6 drift divergent); Strict Comparable P/E 94/94 matched (100%); Same-Snapshot 99/100 (calendar EOD) & 100/100 (intraday cutoff); IAS 33 estimate disclosure active; P/B 74/74 fresh matched (100%). |
| **GATE 4** | AI Evidence Correctness | Evidence grounding enforced; numeric claims tied to verifiable structured citations | **PASS** | Semantic citation validator active; upgraded to `qwen3.5:9b-q4_K_M` with `think=false`. Verified via live backend streaming (FPT, 223 tokens, 1 cited claim, IAS 33 flag) and browser UI test (72.58s settled). |
| **GATE 5** | Deployed Backend Revision | Render live backend `git_commit` matches local HEAD and database is healthy | **PASS** | Render live backend returns commit **`eb4b6344c45db3c5e8900a229ed9610faf8bb2cd`** (exact match to local HEAD); Neon latency 11.16ms. |
| **GATE 6** | Deployed Frontend Revision | Vercel frontend deployment verified via platform deployment API metadata | **BLOCKED_AWAITING_TOKEN** | Vercel frontend reachable (HTTP 200, ETag `"68212e5a0df9341e19b841cd9af812cb"`). Awaiting optional `VERCEL_TOKEN` for automated platform API verification. |
| **GATE 7** | Scheduled Automation | Workflow `eod_ingestion.yml` configured with cron `'37 8 * * 1-5'` and genuine schedule observed | **PENDING** | Workflow configured with verified cron `'37 8 * * 1-5'` (15:37 ICT). Awaiting next scheduled market-close trigger. |
| **GATE 8** | Neon Database Sync Safety | `ALLOW_PRODUCTION_DB_WRITE=false` guard preserved; sync dry-run ready; awaits explicit user authorization | **BLOCKED_AWAITING_AUTH** | Production write protection strictly active (`ALLOW_PRODUCTION_DB_WRITE=False`). Neon Cloud DB (Read-Only) safely held pending explicit user authorization. |

- **Technical Readiness Verdict**: **PASS**
- **Overall Production Readiness Verdict**: **PARTIAL** (due to pending external platform token, scheduled market-close trigger, and safe database backfill hold).

---

## 3. Key Milestones Completed

### Local AI Analyst Upgrade to Qwen3.5 9B & BMP Phase 1 & 2 Hardening (2026-10-28 / 2026-11-01)
- **Objective**: Upgraded the local AI Analyst primary model from `qwen2.5:3b` to `qwen3.5:9b-q4_K_M` on local Ollama while strictly preserving financial contracts, Hallucination Guard, streaming SSE, and fallback mechanisms. Completed **Phase 1 Three Fixes** and **Phase 2 Hardening** for metric coverage and status accuracy.
- **Phase 1 Resolutions**:
  - *Evidence Starvation*: Scaled prompt context up to 16 items for single stocks, prioritizing requested metrics.
  - *Fallback Banner Decoupling*: Isolated alarmist alert to `PARTIAL_DATA_ONLY` via `isFallbackMode`.
  - *Auxiliary Caveats Preservation*: Prevented forward-looking caveats from falsely triggering fallback.
- **Phase 2 Hardening Resolutions**:
  - *Atomic Metric Extraction*: Refactored `METRIC_CATEGORY_PATTERNS` to split composite buckets into 15 atomic indicators (`debt_to_assets`, `debt_to_equity`, `net_debt_ebitda`, `total_debt`, `gross_margin`, `net_margin`, `operating_margin`, `revenue`, `revenue_yoy`, `net_income`, `cash_balance`, `operating_cash_flow`, `pe`, `pb`, `roe`) with strict mutual exclusion and disambiguation.
  - *Deterministic Status Gate (`determine_response_status`)*: Enforced claim-to-evidence matching where a requested metric is covered **only** if a verified substantive claim cites evidence belonging specifically to that indicator and symbol. Structured Bento tables are strictly reference data and never counted as AI narrative claims.
  - *Empty Metric Guard*: Open-ended questions require grounded citations and no missing data uncertainty to achieve `AVAILABLE`.
  - *UI Clarity*: Updated Bento section header to *"Dữ liệu Đối chứng Chuẩn xác (Reference Benchmark Data)"* and added a dedicated Apple-styled *"LƯU Ý DỮ LIỆU & RỦI RO (Data Limitations & Caveats)"* section for unverified indicators.
- **Verification & Acceptance**:
  - Regression test suites: **35/35 passed (100%)** across `test_bmp_three_fixes.py` (15 tests including 10 dedicated scenarios), `test_ai_prompt_optimization.py` (5 tests), `test_ai_analyst_repair_regression.py` (12 tests), and `test_ai_streaming_and_fallback.py` (3 tests).
  - Single real BMP UI acceptance test executed via Chrome CDP (`scratch/run_bmp_diagnostic.py`): Settled in 124.70s with honest status `PARTIAL`, alarmist banner suppressed, 3 grounded substantive claims (revenue YoY, margins, cash flows), 1 explicit uncertainty claim on missing debt data, and 2 rendered risk caveats.
  - Full audit reports:
    - [`docs/audits/local_bmp_qwen35_9b_three_fixes_2026-11-01.md`](docs/audits/local_bmp_qwen35_9b_three_fixes_2026-11-01.md)
    - [`docs/audits/local_bmp_qwen35_9b_phase2_hardening_2026-11-01.md`](docs/audits/local_bmp_qwen35_9b_phase2_hardening_2026-11-01.md)

### Opportunities → AI Analyst Stock Context Handoff Fix (2026-10-28)
- **Root Cause**:
  - The Opportunities page linked to `/ai?symbol=...&q=...`, but `/ai/page.tsx` only inspected `searchParams.get("ticker")`, failing to read `symbol`, and never prefilled the visible question textarea.
- **Implementation**:
  - Created [`apps/web/src/lib/ai-handoff.ts`](apps/web/src/lib/ai-handoff.ts) providing `normalizeTicker`, `buildOpportunityQuestion`, and `buildOpportunityAIUrl`.
  - Updated [`apps/web/src/app/opportunities/page.tsx`](apps/web/src/app/opportunities/page.tsx) to pass URL-encoded parameters (`symbol`, `source=opportunities`, and standardized Vietnamese prompt) for both table rows and cards.
  - Updated [`apps/web/src/app/ai/page.tsx`](apps/web/src/app/ai/page.tsx) to read `symbol` / `ticker` / `q`, select the ticker, prefill the visible question textarea, preserve user edits across re-renders with idempotent tracking (`lastHandledKeyRef`), and require explicit user submission without auto-submitting.
- **Verification**:
  - Unit tests: **7/7 passed** (`tests/test_opportunities_to_ai_handoff.py`).
  - Next.js build: **13/13 routes compiled cleanly via Turbopack** (0 TypeScript errors).
  - Live browser automation: Verified in Chrome headless via CDP across 5 real interaction scenarios (FPT handoff, user edit preservation, second stock handoff HPG, direct navigation, and zero auto-submit), capturing screenshots in `docs/audits/evidence/browser_handoff_*.png`.

### True Apple Daylight & Warm Neutral Minimalism Redesign (2026-10-28)
- **Design Philosophy**: Critical UX/UI correction inspired by Apple Card, macOS System Settings, Apple Stocks on iPadOS, and Linear Minimalist UI. Eradicated pitch black (`#0c0d10`) and cyan/neon blue (`#2997ff`) in favor of an understated, warm daylight aesthetic.
- **Strict Neutral Color Palette**:
  - *App Canvas*: Apple Light Gray / Warm Stone (`#F5F5F7`).
  - *Elevated Surfaces*: Pure White (`#FFFFFF`) with soft diffused ambient shadows (`0 2px 12px rgba(0, 0, 0, 0.03)`).
  - *Secondary Surfaces & Pills*: Silver Stone (`#EFEFF4` / `#F2F2F7`).
  - *Hairlines & Borders*: Sub-pixel divider lines (`1px solid rgba(0, 0, 0, 0.06)`). Zero glowing borders.
  - *Typography*: Apple Charcoal (`#1D1D1F`), Neutral Gray (`#6E6E73`), and Muted Gray (`#86868B`).
  - *Monochrome Accent*: Interactive action buttons use solid Charcoal `#1D1D1F` with `#FFFFFF` text (hover `#333336`). Strict zero cyan.
  - *Semantic Financial Colors*: Calm Forest Green (`#1E8E3E` on `#E6F4EA`), Coral Crimson (`#D93025` on `#FCE8E6`), and Warm Amber (`#B06000` on `#FEF7E0`).
- **Emergency Layout & Header Clearance Fix (`/ai` & `AppShell`)**:
  - *Root Cause Resolved*: Eliminated the rigid 2-column grid (`380px 1fr`) that squeezed inputs into an unnatural left column. Corrected the header positioning by enforcing explicit container bounds in `apps/web/src/components/app-shell.module.css` (`width: 100%; min-height: 100vh; background-color: #F5F5F7; overflow-x: hidden;`) and guaranteeing header clearance.
  - *Exact Apple Daylight CSS Applied (`apps/web/src/app/ai/page.module.css`)*: Completely replaced with 28 verified Apple Daylight utility classes including `.pageWrapper`, `.centerContainer` (`max-width: 820px`), `.heroSection`, `.heroBadge`, `.heroTitle`, `.suggestionPills`, `.scopeCard`, `.resultCard`, and `.bottomDock` (`position: fixed; left: 260px; right: 0; bottom: 0;`).
  - *State & API Logic Preserved (`apps/web/src/app/ai/page.tsx`)*: 100% of state variables, streaming callbacks (`streamAIChat`), citations, fallbacks, and parameter structures maintained intact.
  - *Form Controls Native Override*: Overrode browser default styling for `<textarea>`, `<input>`, and `<button>`, implementing sleek floating pill geometry with responsive focus states.
- **Decluttered Minimalist UX**:
  - *Market Summary Strip*: Removed 3D isometric tilt and perspective distortion from `DimensionalMarketRadar`. Replaced with a flat, horizontal summary strip displaying `VNINDEX` and `VN30` levels and a minimal bilateral advance/decline track.
  - *Elimination of "Boxes Inside Boxes"*: Replaced heavy nested borders with generous whitespace and subtle horizontal hairlines.
  - *AI Analyst Centered Editorial Flow*: Transformed the 2-column layout into a spacious 820px centered reading flow inspired by Apple Notes and ChatGPT macOS.
  - *Floating Prompt Bar*: White card (`#FFFFFF`, `rounded-2xl`, soft shadow `0 4px 20px rgba(0, 0, 0, 0.05)`) with stone ticker selector pills and monochrome submit button.
  - *Minimalist Chips & Citation Pills*: Stone chips (`bg-[#EFEFF4] text-[#1D1D1F] hover:bg-[#E5E5EA]`) and understated stone citation labels (`[E001]`).
  - *Apple.com Spec-Style Fallback Tables*: Quantitative indicators rendered as clean horizontal rows with left-aligned keys, right-aligned `tabular-nums` values, and zero vertical dividing lines.
- **Verification Evidence**:
  - **High-Resolution Screenshots**: Captured across 3 viewports (1440×900, 1280×800, 1920×1080) and archived in `docs/audits/evidence/investintel_apple_neutral_minimalism_2026-10-28/apple_daylight_ai_*.png`, visually confirming centered layout, zero header overlap, and clean Apple Daylight styling.
  - **Comprehensive Audit Report**: Documented in `docs/audits/investintel_apple_daylight_redesign_2026-10-28.md`.
  - **Build & Compilation**: 13/13 Next.js routes compiled cleanly via Turbopack in 531ms; 0 TypeScript errors.

### Local AI Analyst Multi-Ticker Routing & Semantic Grounding (2026-10-28)
- **Multi-Ticker Extraction & Routing**: Enhanced `services/ai/analyst.py` and `services/ai/tools.py` to extract and resolve multiple stock tickers (e.g. `MBB` and `VCB`, `FPT` and `MWG`) from analytical comparison queries, retrieving multi-symbol financial contexts simultaneously.
- **Semantic Metric Grounding & Hallucination Prevention**:
  - Implemented semantic metric grounding in citation validation: prevented model from citing a metric of one type (e.g. `gross_margin`) to substantiate a completely different claim (e.g. `revenue_change`).
  - Strict entity consistency enforcement: cross-stock metric attribution is rejected (`Q12/Q13`).
  - Unverified claims are safely converted to `UNCERTAINTY` or filtered out.
- **Smart Partial Fallback**: When structured model generation fails or produces uncited numbers, `AIAnalyst` preserves verified quantitative citations and returns structured financial telemetry under `status: "PARTIAL_DATA_ONLY"` instead of wiping out verified data.
- **Test Coverage**: Added dedicated regression test suites: `tests/test_ai_analyst_repair_regression.py` (12 passed), `tests/test_ai_prompt_optimization.py` (5 passed), and `tests/test_ai_streaming_and_fallback.py` (3 passed).

### Banking Sector & Macro Commodity Expansion (2026-10-28)
- **Bank-Specific Metrics**:
  - Created `bank_metrics` table (`database/models.py`, `database/migrations/versions/20261028_bank_metrics_and_macro_commodities.py`).
  - Seeded quarterly Net Interest Margin (NIM), Current Account Savings Account (CASA) ratio, Credit Growth, Non-Performing Loans (NPL) ratio, and Loan Loss Reserve (LLR) ratio for core banks (`VCB`, `MBB`, `TCB`, `BID`, `CTG`).
- **Macro Commodities Benchmark Series**:
  - Created `macro_commodities` table storing daily Brent and WTI crude oil benchmarks (3,402 records) aligned with Vietnamese trading sessions.
  - Implemented dynamic Pearson correlation engine in `services/ai/tools.py` evaluating stock-price vs. commodity-price sensitivity for energy/commodity equities (`PLX`, `BSR`, `PVD`, `PVS`).
- **Verification**: Verified via `tests/test_bank_and_commodity_expansion.py` (3/3 passed).

### Point-in-Time Data Integrity & Intraday Publication Replay (2026-10-27)
- **Intraday Publication Replay Guard**:
  - Enforces strict publication cutoff: financial statements published on the cutoff date without an explicit pre-cutoff timestamp are excluded from intraday snapshots.
  - Replaying at `2026-10-19 15:00:00 ICT` excludes evening filings (e.g. `VIX` Q3 2026 statement filed evening of Oct 19), reproducing the exact provider P/E of `7.84786535` with 0.00% error.
- **IAS 33 Basic EPS & Denominator Reality**:
  - Audited across all 100 active equities in the rolling 2026 TTM 4-quarter window: 100/100 rely on period-end share fallback estimates; 0/100 quarters provide weighted average basic shares.
  - Strict estimate flags (`is_estimate=True`) and diagnostic provenance are propagated across all 6 system layers.
- **DSE Provenance & Residual Transparency**:
  - Internal EPS with 428,249,806 post-IPO ending shares gives 558.57 VND (P/E 36.79 vs provider 36.60 at 20,550 VND).
  - The +0.1867 PE point (+0.51%) residual is transparently preserved as `UNVERIFIED_SHARE_BASIS_RESIDUAL` under `PARTIALLY_SUPPORTED`.

### Multi-Provider Free Data Expansion & Cloud Deployment (Historical — 2026-10-19)
- **Public Secondary Ingestion Engines**: Public endpoints for DNSE, Vietstock, VNDirect, World Bank, Frankfurter / open.er-api, GDELT, and BLS.
- **Index Data Ingestion**: Route `VN100` and `VN30` to Entrade index candles (`/chart-api/v2/ohlcs/index`), seeding benchmark assets and memberships.
- **Financial News RSS Ingestion**: Ingests public RSS feeds from CafeF and VnEconomy, promoting articles into canonical `EventRecord`s with SHA-256 checksums and ticker extraction.
- **Complete Gemini Removal & Local Ollama Only**: Zero paid AI APIs; exclusively uses local Ollama (`qwen2.5:3b`, GPU accelerated with ~66–146 tokens/s).
- **Cloud AI Isolation**: Render web service returns `LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD` without attempting loopback network calls. Non-AI engines operate with 100% functionality.

---

## 4. Preserved Operational Gates & Real Limitations

1. `LIVE_HOSE_PROVIDER`: **BLOCKED**
   - An official, commercially licensed direct HOSE market feed contract has not been established.
   - Unauthenticated secondary providers (Entrade, VPS, VNDirect, CafeF) are utilized exclusively for personal research under acceptable use policies.
2. `RECURRING_SCHEDULER`: **PENDING EXTERNAL ACTION**
   - Endpoints are secured via constant-time `X-Cron-Secret` verification (`POST /api/v1/system/cron/run-ingestion`).
   - Automated weekday trigger requires external configuration in `cron-job.org` or GitHub Actions schedule.
3. `VN300_BENCHMARK`: **INSUFFICIENT_DATA**
   - VN300 index candles are not offered by public secondary endpoints.
   - Honestly retained as `INSUFFICIENT_DATA` rather than fabricating synthetic benchmarks.
4. `NEON_PRODUCTION_SYNC`: **BLOCKED_AWAITING_AUTH**
   - Cloud database write protection is strictly active (`ALLOW_PRODUCTION_DB_WRITE=false`).
   - Sync dry-run scripts are prepared (`scripts/sync_local_to_neon.py`), held pending explicit user authorization.

---

## 5. Documentation References
- Canonical Project Status: [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
- Automated Acceptance Report: [`docs/ACCEPTANCE_REPORT.json`](docs/ACCEPTANCE_REPORT.json)
- Local AI Analyst Qwen3.5 9B Upgrade & Runtime Audit: [`docs/audits/local_qwen35_9b_runtime_diagnosis_2026-10-28.md`](docs/audits/local_qwen35_9b_runtime_diagnosis_2026-10-28.md)
- Apple Daylight Neutral Redesign Audit: [`docs/audits/investintel_apple_daylight_redesign_2026-10-28.md`](docs/audits/investintel_apple_daylight_redesign_2026-10-28.md)
- Cloud Deployment & Setup Guide: [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md)
- Complete Bottleneck Synthesis: [`docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md`](docs/TONG_HOP_TIEN_TRINH_VA_DIEM_NGHEN.md)
