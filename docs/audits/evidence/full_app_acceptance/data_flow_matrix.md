# INVESTINTEL — FRONTEND–BACKEND–DATABASE DATA FLOW MATRIX
**Generated:** 2026-11-02 | **Branch:** `phase6-local-stability` | **Target Environment:** Local Workstation (Windows 11)

---

## 1. End-to-End Data Flow Mapping

The table below traces user-facing features from the Next.js UI layer through the client HTTP calls, FastAPI routers, underlying analytical services, database models, and final rendered views.

| # | Frontend Page | UI Feature / Action | Frontend API Client Method | FastAPI Router & Route | Analytical Service Layer | SQLAlchemy Model | Returned Data | UI Result & State | Verification |
|---|---|---|---|---|---|---|---|---|:---:|
| 1 | `/` (Dashboard) | View Data Sources & Freshness | `getDataProviders()` | `GET /api/v1/data/providers` | `services/data/providers.py` | `DataSource`, `DataRun` | Provider statuses, last run timestamp, records count | Rendered provider cards with freshness badges | **PASS** |
| 2 | `/` (Dashboard) | View Universe Distribution | `getAssets()` | `GET /api/v1/data/assets` | `services/data/repository.py` | `Asset`, `IndexMembership` | List of assets with symbols, exchange, asset type | Hero counter & asset type breakdown cards | **PASS** |
| 3 | `/market` | Market Overview & Indices | `getMarketDashboard()` | `GET /api/v1/market/dashboard` | `services/market/engine.py` | `Price`, `Asset`, `MacroSeries` | VNINDEX, VN30, advancing/declining counts | Market metric cards with evidence citations | **PASS** |
| 4 | `/market` | Macro Commodity Radar | `getLatestMacro()` | `GET /api/v1/macro/latest` | `services/macro/service.py` | `MacroObservation`, `MacroCommodity` | BRENT, WTI, interest rates, inflation | Dimensional Market Radar visualization | **PASS** |
| 5 | `/screener` | Multi-Filter Stock Screening | `getStockScreener()` | `GET /api/v1/screener` | `services/screener/engine.py` | `FundamentalSnapshot`, `Asset`, `Price` | Filtered stock rows, valuation multiples, ROE | Paginated screener results table | **PASS** |
| 6 | `/opportunities`| Multi-Factor Opportunity Scan | `getOpportunityScanner()` | `GET /api/v1/opportunity/scanner` | `services/opportunity/scanner.py` | `FundamentalSnapshot`, `Asset`, `Price` | Ranked opportunities with composite scores | Opportunity cards with Why Now / Why Not Now | **PASS** |
| 7 | `/research/[ticker]` | Deep Financial Research | `getResearchWorkspace()` | `GET /api/v1/research/{symbol}` | `services/research/workspace.py` | `FinancialStatement`, `FundamentalMetric` | 7 institutional modules + balance sheet metrics | Modular research workspace with evidence accordions | **PASS** |
| 8 | `/research/[ticker]` | Longitudinal History (5Y/12Q)| `getFinancialHistory()` | `GET /api/v1/research/{symbol}/history` | `services/research/history.py` | `FinancialStatement`, `FinancialLineItem` | Annual (5Y) & quarterly (12Q) financial periods | Historical longitudinal tables & trends | **PASS** |
| 9 | `/valuation` | Composite Valuation & Scenarios| `getValuationSnapshot()` | `GET /api/v1/valuation/{symbol}` | `services/valuation/builder.py` | `FundamentalSnapshot`, `Price` | Composite fair value (Bear/Base/Bull), DCF | Fair value range, methods table, Margin of Safety | **PASS** |
| 10| `/valuation` | Cross-Sectional Peer Comparison| `getPeerComparison()` | `GET /api/v1/valuation/{symbol}/peers` | `services/valuation/peers.py` | `PeerGroup`, `FundamentalSnapshot`, `Asset` | Peer table, sector medians (P/E, P/B, ROE) | Cross-sectional peer table & premium/discount | **PASS** |
| 11| `/portfolio` | Portfolio Holdings & Analytics | `getPortfolio()` | `GET /api/v1/portfolio` | `services/portfolio/engine.py` | `PersonalPortfolio`, `PortfolioHolding` | Positions, market values, asset class weights | Holdings table, sector allocation chart | **PASS** |
| 12| `/portfolio` | Target Allocation & Fit | `getPortfolioFit()` | `GET /api/v1/portfolio/fit` | `services/portfolio/fit.py` | `PortfolioTarget`, `PortfolioHolding` | Drift %, Core vs Satellite allocation | Risk warnings, rebalancing recommendations | **PASS** |
| 13| `/watchlist` | Watchlist Items & Thesis Notes| `getWatchlist()` | `GET /api/v1/watchlist` | `services/watchlist/service.py` | `WatchlistItem`, `WatchlistThesisRevision`| Tickers, conviction levels, thesis history | Watchlist cards with revision timeline | **PASS** |
| 14| `/watchlist` | Decision Brief & Snapshot | `getDecisionContext()` | `GET /api/v1/decision/{symbol}/context` | `services/decision/context.py` | `AssetDecisionSnapshot`, `Price` | Consolidated decision factors & evidence | Expandable decision brief accordion | **PASS** |
| 15| `/ai` | Local Streaming AI Analyst | `streamAIChat()` | `POST /api/v1/ai/chat/stream` | `services/ai/gateway.py` | `Asset`, `FundamentalSnapshot`, Ollama LLM | SSE tokens, citations (`[E001]`), evidence | Real-time markdown with Apple Citation Pills | **PASS** |
| 16| `/data-center`| Data Ingestion Lineage & QA | `getDataProviders()` | `GET /api/v1/data/providers` | `services/data/providers.py` | `DataRun`, `DataSource`, `DataLineage` | Ingestion run summaries, record counts | Lineage table and data provenance log | **PASS** |
| 17| `/system` | System Observability & Telemetry| `getSystemDiagnostics()` | `GET /api/v1/system/diagnostics` | `services/ai/telemetry.py` | N/A (`nvidia-smi`, SQLite PRAGMA) | RTX 3050 VRAM/temp, TTFT, scheduler status | Hardware telemetry cards & health matrix | **PASS** |
| 18| `/system` | Autonomous Pipeline Trigger | `triggerAutomationPipeline()`| `POST /api/v1/automation/scheduler/trigger`| `services/scheduler/engine.py` | `DataRun`, `FundamentalSnapshot`, `Price` | Pipeline execution status & stage receipts | Status toast & updated execution log | **PASS** |

---

## 2. Unused Endpoints, Mock Data & Contract Audit

1. **Working API Connections**: 18 major user-facing features mapped to 24 core API routes; all 18 tested and verified healthy.
2. **Mock Data Audit**: Zero mock data used in active user workflows. All metrics originate from SQLite canonical tables (`Price`, `FinancialStatement`, `FundamentalMetric`, `FundamentalSnapshot`, `Asset`).
3. **Internal / Automation Endpoints**:
   - `/api/v1/cron/*` routes are standalone scheduled trigger endpoints designed for internal task runners.
   - `/api/v1/automation/cycle` and `/api/v1/automation/briefs` support autonomous background workers.
4. **Contract Uniformity**:
   - All responses return standard ISO dates (`YYYY-MM-DD`).
   - Currency units in VND, multiples as dimensionless floating point.
   - Pydantic models validate all inputs with zero unhandled type conversions.

