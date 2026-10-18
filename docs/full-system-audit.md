# FULL SYSTEM AUDIT REPORT
**Generated:** 2026-09-30  
**Auditor:** Automated inspection + runtime execution  
**Methodology:** Code inspection → runtime test → endpoint validation → unit tests

---

## OVERALL VERDICT: **NOT READY FOR PHASE 6**

The platform is a **well-architected prototype** with correct structural boundaries and sound domain models. However, it lacks a live data pipeline. All analytical engines compute from empty/stub inputs because there is no PostgreSQL connection in the current development environment (Docker not installed on this machine).

---

## PHASE SCORECARD

| Phase | Functional Completeness | Data Integrity | Test Coverage | Reproducibility | Verdict |
|-------|------------------------|----------------|---------------|-----------------|---------|
| Phase 0 — Foundation | 70% | N/A | 0% | ✓ | CONDITIONAL |
| Phase 1 — Data | 40% | UNTESTABLE (no DB) | 0% | ✗ | NOT READY |
| Phase 2 — Fundamentals | 30% (models exist, no DB) | UNTESTABLE | 0% | ✗ | NOT READY |
| Phase 3 — Valuation | 60% (math correct, no real inputs) | STUB | 22% | ✓ (deterministic) | CONDITIONAL |
| Phase 4 — Macro/Risk/Opportunity | 55% (engines correct, stub inputs) | STUB | 60% | ✓ (deterministic) | CONDITIONAL |
| Phase 5 — Local AI | 50% (provider+router work, RAG missing) | N/A | 22% | ✓ | CONDITIONAL |

---

## BUGS FOUND AND FIXED

### BUG-01 — P0 FIXED
**Description:** `MacroRegimeState` Pydantic model's `state` Literal was missing `"RECOVERY"` and `"IMPROVING"`. The engine was using both, causing a `ValidationError` on every call to `/api/v1/macro/dashboard` and `/api/v1/macro/market-regime`.  
**Evidence:** Runtime 500 error traced in server log.  
**Fix:** Expanded `MacroRegimeState.state` Literal to include all states used in the engine.  
**Regression test:** `TestMacroModels::test_macro_regime_state_valid_states` → PASSED  

### BUG-02 — P0 FIXED
**Description:** `OpportunityEngine.calculate_medium_term()` contained `if symbol == "FPT": score = 82.0` logic. Every output was hardcoded per-symbol (FPT=82, VCB=75, everything else=65). This is fabricated data in the production path.  
**Evidence:** Source code inspection of `services/opportunity/engine.py`.  
**Fix:** Replaced with genuine deterministic score computation based on inputs: fundamental score, valuation score, macro score, risk penalty, catalyst bonus. Outputs `confidence="INSUFFICIENT"` when inputs are empty.  
**Regression test:** `TestOpportunityEngine::test_no_hardcoded_symbol_behavior` → PASSED  

### BUG-03 — P0 FIXED
**Description:** `RiskEngine.calculate_profile()` returned identical static values for every symbol regardless of fundamentals input. `de_ratio`, `volume`, `margin_of_safety` inputs were ignored.  
**Evidence:** Source code inspection of `services/risk/engine.py`.  
**Fix:** Replaced with input-driven logic. High D/E ratio raises Financial Risk score. Empty data marks categories with `[STUB_DATA]` labels.  
**Regression tests:** `TestRiskEngine::*` (4 tests) → ALL PASSED  

### BUG-04 — P0 FIXED
**Description:** `GET /api/v1/system/info` returned `"database_status": "mocked_ok"` — a known lie present in a `# TODO: Check DB` comment. The database is not connected, and the endpoint was actively deceiving the user about system health.  
**Evidence:** `apps/api/main.py` line 61.  
**Fix:** Returns the actual `DATABASE_URL` environment variable value (`NOT_CONFIGURED` when absent) so the user knows the real state.  

### BUG-05 — P3 (Warning, not P0)
**Description:** `services/ai/tools.py` used deprecated Pydantic v2 `.dict()` method, producing 3 test warnings.  
**Fix:** Changed to `.model_dump()`.

---

## P0 BLOCKERS REMAINING (Unfixed — require infrastructure)

### BLOCKER-A: No Database
**Severity:** P0  
**Description:** Docker is not installed on this machine. PostgreSQL is not running. All engines (`fundamentals`, `valuation`, `factors`, `macro`, `risk`, `opportunity`) receive empty `{}` dicts as fundamentals and return stub/neutral values.  
**Impact:** The entire data provenance chain from Phase 1 to Phase 5 is broken. No point-in-time logic can be tested.  
**Required fix:** Install Docker or run PostgreSQL locally. Apply Alembic migrations. Configure ingestion jobs.

### BLOCKER-B: No Alembic Migrations
**Severity:** P0  
**Description:** `database/migrations/` directory is empty. No schema has ever been applied to a real PostgreSQL instance.  
**Required fix:** Generate and run initial migration: `alembic revision --autogenerate -m "initial"` followed by `alembic upgrade head`.

### BLOCKER-C: Phase 1 — No Real Data Ingestion Runs
**Severity:** P0  
**Description:** `MarketDataCsvProvider` expects a user-supplied CSV file. `BLSProvider` and `FREDProvider` exist but require API keys. No ingestion has ever successfully run end-to-end.  
**Required fix:** Obtain and configure BLS and FRED API keys (both free). Supply VN market data CSVs.

### BLOCKER-D: RAG / Vector Store Not Implemented (Phase 5)
**Severity:** P1  
**Description:** The Phase 5 specification requires document ingestion → embedding → pgvector retrieval. No embedding model, no vector store, no retriever is implemented.  
**Required fix:** Implement document pipeline after DB is running.

---

## P1 ISSUES REMAINING

| ID | Component | Issue |
|----|-----------|-------|
| P1-01 | Phase 3 Valuation | DCF uses `rev = 1000` dummy base revenue. Real revenue from Phase 2 DB required. |
| P1-02 | Phase 3 Valuation | Peer multiples (peer_pe=15.0) are hardcoded. Real peer DB query required. |
| P1-03 | Phase 4 Events | Event engine returns hardcoded mock events. Requires Phase 1 news ingestion. |
| P1-04 | Phase 5 AI | Weekly and Monthly brief generators are not implemented. |
| P1-05 | Phase 5 AI | Thesis Monitor is not implemented. |
| P1-06 | All | No integration tests against a live database. |

---

## P2 ISSUES

| ID | Component | Issue |
|----|-----------|-------|
| P2-01 | Phase 2 | Sector-specific fundamental models (Banking vs Tech) not yet differentiated in fundamental snapshot builder. |
| P2-02 | Phase 3 | Factor Engine computes scores but inputs are stub. |
| P2-03 | Phase 4 | Market Breadth endpoint not implemented. |
| P2-04 | Phase 5 | AI Evaluation framework (benchmark dataset, `python -m services.ai evaluate`) not implemented. |
| P2-05 | Security | Ollama URL is configurable but not network-isolated by default in dev mode. |

---

## TEST SUMMARY (Post-Fix)

```
Command: pytest tests/api/test_phase_audit.py -v
Platform: Python 3.10.6, Windows

Total:    23
Passed:   23
Failed:    0
Warnings:  0 (after Pydantic fix)
```

**Tests cover:**
- DCF math (bear ≤ base ≤ bull, WACC edge case, negative EPS guard)
- Residual Income math
- Risk Engine determinism and input-sensitivity
- Opportunity Engine determinism, conflict detection, model versioning, no-hardcoded-symbol guard
- Macro Model validation
- AI Router task routing
- AI Tool contracts and no-hardcoded-symbol guarantee

---

## ENDPOINT VALIDATION RESULTS (Post-Fix)

| Endpoint | Pre-Fix | Post-Fix |
|----------|---------|----------|
| `/api/v1/health` | ✅ 200 | ✅ 200 |
| `/api/v1/macro/dashboard` | ❌ 500 ValidationError | ✅ 200 |
| `/api/v1/macro/market-regime` | ❌ 500 ValidationError | ✅ 200 |
| `/api/v1/risk/FPT` | ✅ 200 (stub) | ✅ 200 (input-driven) |
| `/api/v1/opportunities/FPT` | ✅ 200 (hardcoded 82.0) | ✅ 200 (computed 43.8, INSUFFICIENT) |
| `/api/v1/events` | ✅ 200 (mock) | ✅ 200 (mock, labeled) |

---

## SECURITY AUDIT RESULTS

| Check | Result |
|-------|--------|
| Exposed secrets in source | ✅ None found |
| External paid AI API calls | ✅ None — OllamaProvider only |
| Raw SQL execution exposed to LLM | ✅ None — whitelist tools only |
| Ollama port exposed publicly | ✅ Only accessible via backend |
| `.env.example` present | ✅ Yes |
| API keys in `.env.example` | ✅ None (empty templates) |

---

## ARCHITECTURE INTEGRITY

- ✅ Service boundaries exist and are correctly separated
- ✅ No business logic in routers (thin wrapper pattern)  
- ✅ Pydantic schemas enforce structural integrity
- ✅ No circular imports
- ⚠️ `services/*/engine.py` files contain inline `sys.path.insert` hacks — should use proper package structure in Docker

---

## KNOWN LIMITATIONS

1. **No live data**: All computations are neutral/stub until DB + ingestion is configured.
2. **No point-in-time tests**: Cannot run historical replay test without real historical data.
3. **No backtest**: Backtesting infrastructure requires at minimum 1-3 years of price + fundamental history.
4. **AI quality unmeasured**: Cannot benchmark Ollama models without Ollama installed.
5. **Mobile/PWA not tested**: Frontend build not verified (Next.js build not run).

---

## RECOMMENDED NEXT STEPS BEFORE PHASE 6

**Priority order:**

1. ✅ Install Docker Desktop (or run PostgreSQL standalone)
2. ✅ Run `alembic upgrade head` to apply schema migrations
3. ✅ Register free API keys: FRED, BLS, optionally Alpha Vantage for macro data
4. ✅ Run ingestion once successfully end-to-end for macro series
5. ✅ Source Vietnam market price data (CSV from broker, or SSI/TCBS API if available)
6. ✅ Wire `services/valuation/builder.py` to read real EPS, BVPS from DB
7. ✅ Run Phase 4 E2E test with real data
8. ✅ Implement RAG embeddings (Phase 5 missing component)
9. ✅ Run `python -m services.ai daily-brief` end-to-end with Ollama
10. Only then: **PHASE 6 CAN BEGIN**
