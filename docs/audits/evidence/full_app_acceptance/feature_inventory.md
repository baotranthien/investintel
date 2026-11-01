# INVESTINTEL — COMPLETE APPLICATION FEATURE INVENTORY
**Generated:** 2026-11-02 01:34 ICT | **Branch:** `phase6-local-stability` | **Environment:** Local Workstation (Windows 11)

---

## 1. Application Routes & Page Inventory

| # | Route | File Path | Scope & Purpose | Status |
|---|-------|-----------|-----------------|:------:|
| 1 | `/` | `apps/web/src/app/page.tsx` | Dashboard overview, data provider statuses, canonical universe breakdown, navigation hubs | ACTIVE |
| 2 | `/market` | `apps/web/src/app/market/page.tsx` | Market overview, VN-Index/VN30 indices, Market Regime Engine, Dimensional Radar, Macro metrics | ACTIVE |
| 3 | `/screener` | `apps/web/src/app/screener/page.tsx` | Quantitative Stock Screener (P/E, P/B, ROE, margins, D/E, market cap, universe filters) | ACTIVE |
| 4 | `/opportunities` | `apps/web/src/app/opportunities/page.tsx` | Multi-factor Opportunity Scanner, Why Now / Why Not Now evidence cards, AI handoff | ACTIVE |
| 5 | `/research` | `apps/web/src/app/research/page.tsx` | Research Analyst hub, Stock Analysis, Daily Market Brief, Quantitative Backtester | ACTIVE |
| 6 | `/research/[ticker]` | `apps/web/src/app/research/[ticker]/page.tsx` | Deep Company Analysis, 7 institutional sections, 5Y/12Q longitudinal history, Peer comparison | ACTIVE |
| 7 | `/valuation` | `apps/web/src/app/valuation/page.tsx` | Composite Valuation Model (DCF, Relative multiples), Margin of Safety, Factor Radar | ACTIVE |
| 8 | `/portfolio` | `apps/web/src/app/portfolio/page.tsx` | Portfolio Dashboard, holdings, allocation, Core/Satellite fit, DCA plans, manual transactions | ACTIVE |
| 9 | `/watchlist` | `apps/web/src/app/watchlist/page.tsx` | Watchlist tracker, investment thesis note capture, revision history, decision brief | ACTIVE |
| 10| `/ai` | `apps/web/src/app/ai/page.tsx` | Local AI Analyst (Qwen3.5 9B), SSE streaming, tool toggles, Apple Citation Pills, evidence drawer | ACTIVE |
| 11| `/data-center` | `apps/web/src/app/data-center/page.tsx` | Data Center provenance, source freshness, pipeline execution history | ACTIVE |
| 12| `/system` | `apps/web/src/app/system/page.tsx` | System Observability Dashboard, RTX 3050 GPU/VRAM telemetry, scheduler controls, one-click trigger | ACTIVE |
| 13| `/login` | `apps/web/src/app/login/page.tsx` | Authentication handler (auto-redirects to `/` in local single-user mode) | ACTIVE |
| 14| `/[section]` | `apps/web/src/app/[section]/page.tsx` | Dynamic section router for future milestones (e.g. `/settings`) | ACTIVE |

---

## 2. Interactive Controls & UI Actions Inventory

| Module | Control / Action | Type | Target Endpoint / Action | State Handling |
|--------|------------------|------|--------------------------|----------------|
| **Dashboard** | Reload Providers & Assets | Button | `GET /api/v1/data/providers`, `GET /api/v1/data/assets` | Loading indicator, error alert |
| **Market** | Evidence Details Toggle | HTML Details | In-memory claim inspection | Open/close expansion |
| **Market** | Radar Chart Hover | SVG Radar | Recharts dimensional view | Interactive tooltip |
| **Screener** | Universe Filter | Select | `GET /api/v1/screener?universe=...` | Param update, reload table |
| **Screener** | Financial Metrics Inputs | Number Inputs | `pe_min`, `pe_max`, `roe_min`, `de_ratio_max`, etc. | Form state binding |
| **Screener** | Apply Filter | Submit Button | Form submission -> `fetchResults()` | Loading table overlay |
| **Screener** | Reset Filters | Reset Button | Clears inputs -> default query | Restores defaults |
| **Opportunities** | Search Ticker/Name | Text Input | Filters displayed results client-side | Real-time filter |
| **Opportunities** | Filter Chips | Button Chips | All, High Score, Banking, Tech | Active chip highlight |
| **Opportunities** | View Mode Toggle | Toggle Button | Cards vs Table view | Layout switch |
| **Opportunities** | Sort Dropdown | Select | `score_desc`, `score_asc`, `symbol_asc`, `roe_desc` | Client sort reorder |
| **Opportunities** | AI Handoff Link | Router Link | `/ai?ticker=...&question=...` | Context preservation |
| **Research** | Symbol Selector | Text / Link | Navigates to `/research/{ticker}` | Workspace load |
| **Research** | Backtest Runner | Form & Submit | `POST /api/v1/factors/backtest` | Performance chart render |
| **Company Research**| Section Navigation | Sidebar / Tabs | 7 sections + Historical + Peers | Tab switching |
| **Company Research**| Evidence Accordion | HTML Details | Source, date, origin, URL | Evidence modal/details |
| **Valuation** | Ticker Dropdown | Select | `GET /api/v1/valuation/{symbol}` | Panel reload |
| **Portfolio** | Add Holding | Form / Modal | `POST /api/v1/portfolio/holdings` | Optimistic reload |
| **Portfolio** | Edit / Delete Holding | Button | `PATCH` / `DELETE /api/v1/portfolio/holdings/{id}`| Table re-render |
| **Portfolio** | Apply Template | Button | `POST /api/v1/portfolio/templates/{id}/apply` | Portfolio rebalancing |
| **Portfolio** | Snapshot Portfolio | Button | `POST /api/v1/portfolio/snapshot` | Notification toast |
| **Watchlist** | Add Item | Form | `POST /api/v1/watchlist/items` | List addition |
| **Watchlist** | Edit Thesis & Conviction| Form / Inputs | `PATCH /api/v1/watchlist/items/{id}` | Revision history update |
| **Watchlist** | Decision Brief Toggle | Button | `GET /api/v1/decision/{symbol}/context` | Accordion expansion |
| **Watchlist** | Capture Decision Snapshot| Button | `POST /api/v1/decision/{symbol}/snapshot`| Receipt confirmation |
| **AI Analyst** | Question Input | Textarea | `POST /api/v1/ai/chat/stream` | Auto-focus, char count |
| **AI Analyst** | Suggestion Chips | Buttons | Prefills query prompt | One-click query fill |
| **AI Analyst** | Tool Toggles | Checkboxes | Customizes tool subset passed to agent | Tool config state |
| **AI Analyst** | Citation Pill Hover | Modal / Tooltip | Inspects fact provenance | Citation popover |
| **AI Analyst** | Clear Conversation | Button | Clears history and resets context | Clean thread state |
| **System** | Manual Refresh | Button | `GET /api/v1/system/diagnostics` | Live telemetry fetch |
| **System** | Trigger Pipeline | Button | `POST /api/v1/automation/scheduler/trigger` | Pipeline execution run |

---

## 3. Backend Endpoints Inventory (102 Endpoints across 20 Modules)

| Router / Tag | Prefix | Count | Key Endpoints |
|---|---|---|---|
| **AI** | `/api/v1/ai` | 8 | `/chat/stream`, `/stock-analysis`, `/daily-brief`, `/status`, `/query`, `/feedback` |
| **Alerts** | `/api/v1/alerts` | 4 | `/` (GET feed), `/evaluate` (POST), `/rules` (GET), `/{id}/read` (PATCH) |
| **Auth** | `/api/v1/auth` | 4 | `/login`, `/logout`, `/session`, `/me` |
| **Automation** | `/api/v1/automation`| 7 | `/cycle`, `/briefs`, `/alerts`, `/scheduler/status`, `/scheduler/pause`, `/scheduler/resume`, `/scheduler/trigger` |
| **Cron** | `/api/v1/cron` | 3 | `/daily-ingestion`, `/daily-brief`, `/health` |
| **Data** | `/api/v1/data` | 9 | `/providers`, `/assets`, `/runs`, `/lineage`, `/quality`, `/prices/{symbol}` |
| **Decision** | `/api/v1/decision` | 3 | `/{symbol}/context`, `/{symbol}/snapshot`, `/{symbol}/history` |
| **Events** | `/api/v1/events` | 1 | `/{symbol}` |
| **Factors** | `/api/v1/factors` | 4 | `/{symbol}`, `/rankings`, `/backtest`, `/summary` |
| **Fundamentals**| `/api/v1/fundamentals`| 11| `/{symbol}/statements`, `/{symbol}/snapshot`, `/{symbol}/ratios`, `/{symbol}/line-items` |
| **Macro** | `/api/v1/macro` | 3 | `/latest`, `/series`, `/observations` |
| **Market** | `/api/v1/market` | 2 | `/dashboard`, `/movers` |
| **Opportunity** | `/api/v1/opportunity`| 2 | `/scanner`, `/{symbol}` |
| **Portfolio** | `/api/v1/portfolio` | 14| `/`, `/holdings`, `/settings`, `/targets`, `/dca`, `/fit`, `/templates`, `/snapshot` |
| **Research** | `/api/v1/research` | 5 | `/{symbol}`, `/{symbol}/history`, `/{symbol}/report`, `/{symbol}/deep` |
| **Risk** | `/api/v1/risk` | 1 | `/{symbol}` |
| **Screener** | `/api/v1/screener` | 1 | `/` (multi-metric query) |
| **Valuation** | `/api/v1/valuation` | 9 | `/{symbol}`, `/{symbol}/dcf`, `/{symbol}/relative`, `/{symbol}/historical`, `/{symbol}/peers` |
| **Watchlist** | `/api/v1/watchlist` | 5 | `/`, `/items`, `/items/{id}`, `/snapshot`, `/revisions` |
| **System/Health**| `/api/v1/system`, `/`| 6 | `/health`, `/ready`, `/api/v1/system/info`, `/api/v1/system/diagnostics` |

---

## 4. Database Models Inventory (40 Models)

| Domain | Models |
|---|---|
| **Market & Asset Foundation** | `Asset`, `Price`, `CorporateAction`, `IndexMembership`, `MacroCommodity`, `MacroSeries`, `MacroObservation`, `EventRecord` |
| **Financial Statements** | `FinancialStatement`, `FinancialLineItem`, `LineItemMapping`, `FormulaRegistry`, `NormalizedBalanceSheet`, `NormalizedIncome`, `NormalizedCashFlow` |
| **Metrics & Snapshots** | `FundamentalMetric`, `FundamentalSnapshot`, `BankMetric`, `PeerGroup`, `AssetDecisionSnapshot` |
| **Data Lineage & Quality** | `DataSource`, `DataRun`, `DataLineage`, `DataQualityReportRecord`, `QualityFlag`, `StagingRecord` |
| **Portfolio & DCA** | `PersonalPortfolio`, `PersonalPortfolioSnapshot`, `PortfolioHolding`, `PortfolioTarget`, `ManualPortfolioTransaction`, `DcaPlan` |
| **Watchlist & Decision** | `WatchlistItem`, `WatchlistSnapshot`, `WatchlistThesisRevision` |
| **AI Analyst & Automation** | `AnalystAlert`, `AnalystAutomationJob`, `AnalystBrief`, `Document`, `DocumentChunk` |

---

## 5. Scheduled Automation & Background Workers

1. **Scheduled Ingestion Worker** (`services/ingestion/scheduler.py`): Daily market and statement delta ingestion.
2. **Opportunities Scanning Worker** (`services/scheduler/engine.py`): Evaluates universe factors and generates ranked opportunity scores.
3. **Alerts Rule Engine Worker** (`services/alerts/engine.py`): Evaluates 5 institutional trigger conditions with deterministic deduplication.
4. **SQLite Hot Backup Job** (`services/db/backup.py`): Online WAL backup and SHA-256 verification.
5. **AI Analyst Daily Brief Worker** (`services/ai/scheduler.py`): Morning market intelligence summary synthesis.

