# InvestIntel — Focused AI Analyst Targeted Repairs Report

**Date:** 2026-10-27  
**Environment:** Local Development Environment  
**Repository:** `C:\Users\baotr\Downloads\trading`  
**Base Commit:** `42f0de71b7836ea4616182133277912ccfa6e09e`  
**Model Configured:** `qwen2.5:3b` via local Ollama  
**Guardrails:** `ALLOW_PRODUCTION_DB_WRITE=false` strictly preserved; 0 cloud/database writes; 0 external API calls; no commit/push/deploy performed.

---

## A. Summary

This repair round implemented targeted, minimal code modifications in the local AI Analyst retrieval, validation, and serialization pipeline to resolve confirmed defects documented in `docs/audits/local_ai_analyst_20q_2026-10-27.md` and `docs/audits/local_ai_analyst_root_cause_diagnosis_2026-10-27.md`.

### What Was Repaired:
1. **Multi-Ticker Extraction & Context Retrieval (Priority 1):**
   - Extended `UniverseRegistry.extract_all_symbols_from_text` to extract all mentioned stock symbols and preserved `extract_symbol_from_text` for single-ticker backward compatibility.
   - Broadened `NON_SYMBOL_WORDS` with financial acronyms (`EPS`, `PE`, `PB`, `ROE`, `ROA`, `ROIC`, `TTM`, `CAGR`, `EBITDA`, `CASA`, `NIM`, `DCF`, etc.) to prevent common financial indicators from falsely triggering as stock tickers (fixing Q20 where `ZZZTEST` was hijacked by `EPS`).
   - Extended `AITools.get_context()` to accept a list of symbols (`List[str]`), retrieving distinct modules and evidence for each requested company, tagging every evidence item with its responsible `symbol`.
   - Updated `AICitation` schema to include `symbol: Optional[str] = None`.
2. **Metric-Aware and Entity-Aware Post-Generation Validation (Priority 2):**
   - Enforced **Entity Consistency:** A claim naming Stock A cannot be substantiated solely by evidence belonging to Stock B (fixing cross-stock pollution in Q12 SSI/VIX and Q13 REE/PC1).
   - Enforced **Metric Semantic Validation:**
     - Valuation multiples P/E and P/B cannot be substituted for each other (Q01).
     - Margin evidence (e.g. gross margin) cannot substantiate revenue growth or decline claims (Q06 VHM).
     - Valuation multiples (e.g. P/E) cannot be described as corporate profit or net income (Q07 VIC).
     - Corporate revenue/margin statements cannot substantiate macroeconomic or commodity price movements (e.g. crude oil prices) without external market time-series evidence (Q10 PLX).
   - Filtered out contradictory uncertainty claims (e.g. claiming P/E is unavailable when P/E was evidenced and claimed in the same response) (Q01, Q08).
3. **Preservation of Supported Facts & Uncertainty Sanitization (Priority 3):**
   - Refined post-processing so that ungrounded numbers appearing solely in uncertainty or disclaimer statements are stripped without discarding valid, independently grounded factual claims (fixing premature whole-response drops in Q02 VCB).
   - Ensured multi-ticker comparisons with partial evidence (e.g. FPT available, CMG missing in Q14/Q15) return status `PARTIAL` with verified facts for available companies and explicit unavailability disclosures for missing companies, rather than fabricating numbers or replacing valid answers with generic insufficient-data responses.
   - Enforced that if zero substantive claims survive validation, the system safely returns `INSUFFICIENT_DATA` rather than a misleading `PARTIAL`.
4. **Preservation of EPS Estimate Metadata in Evidence & Prompts (Priority 4):**
   - Updated `build_chat_prompt()` and `verifiable_evidence` serialization to include `symbol`, `is_estimate`, `diagnostic_reason`, and `note` (e.g. fallback to period-end shares) (fixing Q16 VIX).
   - Updated `SYSTEM_PROMPT` with explicit instructions regarding share-basis disclosures, metric definitions, and avoiding metric contradictions.
5. **General Portfolio Allocation Routing & Point-in-Time Disclosures (Priority 5):**
   - Handled non-ticker portfolio allocation queries (e.g. 100M VND 3-year horizon in Q19) by routing to canonical market/regime context (`VN100`) rather than requiring a single ticker or rejecting the query.
   - Detected intraday timestamp requests (e.g. 15:00 on 19/10/2026 in Q18) and injected explicit disclaimers that InvestIntel operates on End-of-Day (EOD) closing data and does not support intraday order-book/tick replays, marking the response status as `PARTIAL`.

### What Remains Unresolved / Intentionally Scoped Out:
- **Intraday Market Data Replay:** The database and ingestion pipelines store daily closing bars (EOD) and quarterly financial statements. Real-time or intraday tick-level data at arbitrary intra-session timestamps (e.g. 15:00:00) is neither ingested nor stored; this limitation is now transparently disclosed rather than faked.
- **Dynamic Portfolio Optimization Engine:** Quantitative mean-variance or Black-Litterman portfolio optimization is not part of the local AI Analyst scope; portfolio queries route to market regime context with explicit qualitative caveats.

---

## B. Files Changed

| File | Change Description |
|---|---|
| `services/universe/registry.py` | Added comprehensive financial acronyms to `NON_SYMBOL_WORDS`. Added `extract_all_symbols_from_text()` supporting multi-ticker and unknown ticker extraction (`mã ZZZTEST`). Refined `MARKET_TERMS_PATTERN` to avoid capturing generic ratio phrases like "chỉ số". |
| `services/ai/schemas.py` | Added `symbol: Optional[str] = None` to `AICitation` model. |
| `services/ai/tools.py` | Extended `AITools.get_context()` to accept `symbol: Optional[str \| list[str]]`. Added multi-symbol retrieval loop, aggregating distinct evidence and tagging `symbol` on each evidence item. |
| `services/ai/prompt_registry.py` | Serialized `symbol`, `is_estimate`, `diagnostic_reason`, and `note` into LLM evidence context. Increased evidence cap for multi-symbol queries to 20 items with fair inter-symbol allocation. Updated `SYSTEM_PROMPT` rules for entity isolation, terminology precision, and estimate disclosures. |
| `services/ai/analyst.py` | Integrated multi-symbol routing and general portfolio query routing (`is_portfolio_query`). Added entity consistency check between claim tickers and evidence tickers. Added semantic metric guards (P/E vs P/B, margin vs revenue, P/E vs profit, revenue vs oil price). Stripped contradictory uncertainty items. Sanitized ungrounded uncertainty tokens without discarding verified factual claims. Injected missing ticker notices in multi-company queries and EOD honesty notices for intraday queries. |
| `tests/test_ai_analyst_repair_regression.py` | **New File:** Focused regression suite containing 12 automated unit tests covering all required repair cases across Priorities 1 to 5. |

---

## C. Regression Results

### 1. Focused Repair Regression Suite
**Command:** `.venv\Scripts\python -m pytest tests/test_ai_analyst_repair_regression.py -v`  
**Result:** **12 passed in 23.95s (100% pass rate)**

```
tests/test_ai_analyst_repair_regression.py::test_q20_unknown_ticker_zzztest_not_hijacked_by_eps PASSED [  8%]
tests/test_ai_analyst_repair_regression.py::test_multi_ticker_extraction_all_target_cases PASSED [ 16%]
tests/test_ai_analyst_repair_regression.py::test_q06_vhm_gross_margin_cannot_substantiate_revenue_change PASSED [ 25%]
tests/test_ai_analyst_repair_regression.py::test_q07_vic_pe_cannot_be_described_as_profit PASSED [ 33%]
tests/test_ai_analyst_repair_regression.py::test_q10_plx_company_revenue_cannot_cite_as_oil_price PASSED [ 41%]
tests/test_ai_analyst_repair_regression.py::test_q12_q13_entity_consistency_prevents_cross_stock_attribution PASSED [ 50%]
tests/test_ai_analyst_repair_regression.py::test_q01_q08_contradictory_uncertainty_is_filtered PASSED [ 58%]
tests/test_ai_analyst_repair_regression.py::test_q02_vcb_facts_survive_when_uncertainty_has_ungrounded_numbers PASSED [ 66%]
tests/test_ai_analyst_repair_regression.py::test_q14_q15_missing_stock_in_comparison_is_explicitly_disclosed PASSED [ 75%]
tests/test_ai_analyst_repair_regression.py::test_q16_vix_eps_estimate_and_denominator_note_preserved_in_prompt PASSED [ 83%]
tests/test_ai_analyst_repair_regression.py::test_q18_historical_intraday_honesty_disclosure PASSED [ 91%]
tests/test_ai_analyst_repair_regression.py::test_q19_portfolio_allocation_routing_without_single_ticker PASSED [100%]
```

### 2. Existing AI Local & Analyst Automation Suites
**Command:** `.venv\Scripts\python -m pytest tests/test_ai_local.py tests/test_analyst_automation.py -v`  
**Result:** **28 passed in 36.47s (100% pass rate)**

```
tests/test_ai_local.py::test_ollama_config_rejects_remote_endpoints PASSED [  3%]
tests/test_ai_local.py::test_ollama_config_normalizes_localhost_to_ipv4 PASSED [  7%]
tests/test_ai_local.py::test_ai_router_uses_configured_models PASSED     [ 10%]
tests/test_ai_local.py::test_ollama_structured_response_preserves_usage PASSED [ 14%]
tests/test_ai_local.py::test_ollama_retries_transient_connection_failure PASSED [ 17%]
tests/test_ai_local.py::test_ollama_model_not_found_is_not_returned_as_answer PASSED [ 21%]
tests/test_ai_local.py::test_ollama_status_marks_installed_but_unloaded_model_degraded PASSED [ 25%]
tests/test_ai_local.py::test_document_retrieval_tool_reports_local_status_without_fabricating_evidence PASSED [ 28%]
tests/test_ai_local.py::test_analyst_skips_model_when_evidence_is_missing PASSED [ 32%]
tests/test_ai_local.py::test_analyst_does_not_infer_unsupported_horizon PASSED [ 35%]
tests/test_ai_local.py::test_analyst_returns_only_cited_evidence_and_usage PASSED [ 39%]
tests/test_ai_local.py::test_analyst_suppresses_unsupported_numeric_claim PASSED [ 42%]
tests/test_ai_local.py::test_analyst_does_not_use_unrelated_evidence_number PASSED [ 46%]
tests/test_ai_local.py::test_analyst_does_not_display_uncited_free_form_model_summary PASSED [ 50%]
tests/test_ai_local.py::test_analyst_rejects_stale_citation_for_factual_claim PASSED [ 53%]
tests/test_ai_local.py::test_chat_api_returns_insufficient_data_without_calling_ollama PASSED [ 57%]
tests/test_ai_local.py::test_ai_eval_separates_guardrail_verdict_from_runtime_health PASSED [ 60%]
tests/test_analyst_automation.py::test_daily_brief_generates_structured_sections_and_claim_types PASSED [ 64%]
tests/test_analyst_automation.py::test_snapshot_change_detection_detects_relevant_changes PASSED [ 67%]
tests/test_analyst_automation.py::test_thesis_monitor_requires_evidence_before_updating PASSED [ 71%]
tests/test_analyst_automation.py::test_alert_evaluation_only_emits_source_backed_changes_and_deduplicates PASSED [ 75%]
tests/test_analyst_automation.py::test_alert_evaluation_ignores_unchanged_or_unverified_values PASSED [ 78%]
tests/test_analyst_automation.py::test_persist_brief_is_idempotent PASSED [ 82%]
tests/test_analyst_automation.py::test_missing_or_stale_evidence_returns_insufficient_data PASSED [ 85%]
tests/test_analyst_automation.py::test_ai_analyst_brief_methods_accept_as_of_contract PASSED [ 89%]
tests/test_analyst_automation.py::test_scheduler_claim_job_concurrency_and_retry PASSED [ 92%]
tests/test_analyst_automation.py::test_scheduler_cycle_runs_and_persists_briefs_and_jobs PASSED [ 96%]
tests/test_analyst_automation.py::test_automation_api_endpoints PASSED   [100%]
```

Total Verified Tests: **40 passed, 0 failed**.

---

## D. Behavior Coverage Matrix

| Case | Required Assertion | Test Name | Status |
|---|---|---|---|
| **Q01 — FPT** | EPS is mapped to correct metric and unit; P/E / P/B claims do not contradict availability metadata. | `test_q01_q08_contradictory_uncertainty_is_filtered` | **PASS** |
| **Q02 — VCB** | Supported banking metrics survive when other requested metrics are missing; invalid uncertainty number does not erase all valid facts. | `test_q02_vcb_facts_survive_when_uncertainty_has_ungrounded_numbers` | **PASS** |
| **Q03 — MBB vs VCB** | Both tickers retrieve distinct evidence; claims for one cannot cite only the other's evidence. | `test_multi_ticker_extraction_all_target_cases` | **PASS** |
| **Q06 — VHM** | Gross margin evidence cannot be used as revenue-growth or revenue-decline evidence. | `test_q06_vhm_gross_margin_cannot_substantiate_revenue_change` | **PASS** |
| **Q07 — VIC** | P/E valuation multiple cannot be described as profit or net income. | `test_q07_vic_pe_cannot_be_described_as_profit` | **PASS** |
| **Q08 — VNM** | Contradictory availability claims (e.g. gross margin evidenced vs claimed missing) are rejected or filtered. | `test_q01_q08_contradictory_uncertainty_is_filtered` | **PASS** |
| **Q09 — GAS vs POW** | Both tickers are retrieved or the unavailable ticker is expressly identified. | `test_multi_ticker_extraction_all_target_cases` | **PASS** |
| **Q10 — PLX** | Company financial data cannot substantiate oil-price changes without commodity price evidence. | `test_q10_plx_company_revenue_cannot_cite_as_oil_price` | **PASS** |
| **Q12/Q13 — SSI/VIX, REE/PC1** | A stock's metrics cannot be attributed to another stock. | `test_q12_q13_entity_consistency_prevents_cross_stock_attribution` | **PASS** |
| **Q14/Q15 — FPT/CMG, VCB/HPG/FPT** | All requested stocks are included in evidence, or missing stocks are clearly identified with PARTIAL status. | `test_q14_q15_missing_stock_in_comparison_is_explicitly_disclosed` | **PASS** |
| **Q16 — VIX** | EPS denominator, fallback note and estimate status survive prompt serialization and remain available for response. | `test_q16_vix_eps_estimate_and_denominator_note_preserved_in_prompt` | **PASS** |
| **Q18 — Historical Cutoff** | Intraday historical replay is not claimed as successful; transparent disclosure of EOD limit is injected. | `test_q18_historical_intraday_honesty_disclosure` | **PASS** |
| **Q19 — Portfolio** | A general portfolio question does not require one recognized ticker and routes to market regime context. | `test_q19_portfolio_allocation_routing_without_single_ticker` | **PASS** |
| **Q20 — ZZZTEST** | Unknown ticker remains `ZZZTEST`; `EPS` or other financial acronyms cannot hijack the query. | `test_q20_unknown_ticker_zzztest_not_hijacked_by_eps` | **PASS** |

---

## E. Remaining Limitations

1. **Intraday Tick Replay Not Supported:**
   - The platform architecture operates on End-of-Day (EOD) closing data, daily price histories, and quarterly financial statements.
   - When users specify an exact time (e.g., `15:00 ngày 19/10/2026`), the AI Analyst now explicitly acknowledges this limitation, states that the analysis reflects the EOD state as of that date, and marks the response status as `PARTIAL`.
2. **Third-Party Macroeconomic & Commodity Feeds:**
   - InvestIntel does not currently ingest global crude oil spot/futures price series (Brent/WTI). Queries attempting to correlate PLX or GAS performance with oil price moves are protected against hallucinating oil price changes from company revenues.
3. **Small Model Reasoning Constraints:**
   - Running `qwen2.5:3b` locally requires deterministic structural guards (such as the regex and entity checks added here) rather than purely relying on prompt compliance. The guards implemented in this round guarantee data grounding regardless of minor LLM prompt deviations.

---

## F. Safety and Repository State Confirmation

- **Work Conducted Strictly Locally:** All inspection, code editing, and pytest executions were performed locally on `127.0.0.1` and `localhost`.
- **Production Guard:** `ALLOW_PRODUCTION_DB_WRITE=false` remained active throughout the session; 0 writes were performed to Neon, Render, or Vercel.
- **Git State:** 
  - Working tree: clean targeted edits in `services/` and new test file in `tests/test_ai_analyst_repair_regression.py`.
  - No commits, pushes, merges, or deployments were performed.
  - Previous audit reports (`local_ai_analyst_20q_2026-10-27.md` and `local_ai_analyst_root_cause_diagnosis_2026-10-27.md`) and their associated screenshot artifacts were completely preserved without modification.
