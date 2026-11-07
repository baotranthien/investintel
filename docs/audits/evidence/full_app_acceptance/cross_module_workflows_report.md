# INVESTINTEL — CROSS-MODULE DATA FLOW ACCEPTANCE REPORT
**Execution Timestamp:** 2026-11-02 | **Branch:** `phase6-local-stability` | **Target:** Local Workstation

## 1. Summary of 6 Connected Workflows
- Total Workflows Tested: 6
- Passing Workflows: 6/6 (100%)

## 2. Step-by-Step Execution Evidence

### Workflow 1 — Stock Discovery — **PASS** (77.902s)
- **1. Market Overview** (`GET /api/v1/market/dashboard`) -> `200 OK`: Index: VN30 status: PARTIAL
- **2. Screener Filter** (`GET /api/v1/screener`) -> `200 OK`: Discovered candidate: VCB with ROE 17.26%
- **3. Deep Analysis** (`GET /api/v1/research/VCB`) -> `200 OK`: Retrieved 7 sections, Research status: AVAILABLE
- **4. AI Analyst Handoff** (`POST /api/v1/ai/chat`) -> `200 OK`: AI answer status: AVAILABLE, citations: 2

---

### Workflow 2 — Investment Opportunity — **PASS** (4.194s)
- **1. Opportunity Scanner** (`GET /api/v1/opportunities`) -> `200 OK`: Top opportunity: ACB (Score: 50.0)
- **2. Peer Comparison** (`GET /api/v1/valuation/ACB/peers`) -> `200 OK`: Peer Group: BANK_VN, Median PE: 6.28
- **3. Valuation Model** (`GET /api/v1/valuation/ACB`) -> `200 OK`: Fair Value status: LOW

---

### Workflow 3 — Fundamental Research — **PASS** (0.403s)
- **1. Balance Sheet** (`GET /api/v1/fundamentals/BMP/balance-sheet`) -> `200 OK`: Total Assets available, currency: VND
- **2. Fundamental Snapshot** (`GET /api/v1/fundamentals/BMP/snapshot`) -> `200 OK`: Snapshot sector: MATERIALS, P/E: None
- **3. Historical Analysis** (`GET /api/v1/research/BMP/history`) -> `200 OK`: Annual periods: 5, Quarterly: 12
- **4. Deep Research** (`GET /api/v1/research/BMP`) -> `200 OK`: All 7 institutional modules grounded

---

### Workflow 4 — Portfolio Management — **PASS** (0.4s)
- **1. Watchlist Fetch** (`GET /api/v1/watchlist`) -> `200 OK`: Current watchlist items: 1
- **2. Portfolio Dashboard** (`GET /api/v1/portfolio`) -> `200 OK`: Holdings count: 0
- **3. Portfolio Fit** (`GET /api/v1/portfolio/fit`) -> `200 OK`: Portfolio Status: EMPTY
- **4. Investment Alerts** (`GET /api/v1/alerts`) -> `200 OK`: Active alerts: 3

---

### Workflow 5 — Automated Daily Intelligence — **PASS** (54.061s)
- **1. Scheduler Trigger** (`POST /api/v1/automation/scheduler/trigger`) -> `200 OK`: Pipeline Status: SUCCESS
- **2. System Diagnostics** (`GET /api/v1/system/diagnostics`) -> `200 OK`: Scheduler paused: False, GPU: NVIDIA GeForce RTX 3050 Laptop GPU

---

### Workflow 6 — AI Research Journey — **PASS** (85.443s)
- **1. AI Research Query** (`POST /api/v1/ai/chat`) -> `200 OK`: Model: qwen3.5:9b-q4_K_M | Citations: 3 | Answer Status: AVAILABLE
- **2. Grounded Citation** (`Citation Grounding Verification`) -> `VERIFIED`: [E012] Metric: roe = 41.5664 (Source: VNDIRECT_FINFO)
- **2. Grounded Citation** (`Citation Grounding Verification`) -> `VERIFIED`: [E046] Metric: pe = 8.91 (Source: LOTUSMARKET)
- **2. Grounded Citation** (`Citation Grounding Verification`) -> `VERIFIED`: [E047] Metric: pb = 3.52 (Source: LOTUSMARKET)

---
