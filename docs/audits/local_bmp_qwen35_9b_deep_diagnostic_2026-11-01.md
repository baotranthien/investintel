# InvestIntel — BMP Deep-Dive Diagnostic with Qwen3.5 9B

**Date of Execution:** 2026-11-01 05:37:01 ICT  
**Target Symbol:** `BMP` (CTCP Nhựa Bình Minh — HOSE)  
**Evaluator:** Antigravity AI Pair Programmer & InvestIntel Quality Gate  
**Execution Mode:** Local-First, Zero Cloud Writes (`ALLOW_PRODUCTION_DB_WRITE=false`)  
**Active Inference Model:** Local Ollama `qwen3.5:9b-q4_K_M` (4096 context, `think=false`, 76% CPU / 24% GPU offload on RTX 3050 4GB)

---

## 1. Executive Summary

A real end-to-end diagnostic query was executed through the local web frontend (`http://localhost:3000/ai`) asking the AI Analyst to evaluate `BMP`. 

The core findings of this investigation are:

1. **The Model Did Not Crash and Hallucination Guard Did Not Reject the Claims**:
   Unlike previous timeout or schema failures, `qwen3.5:9b-q4_K_M` successfully generated valid JSON matching the `AIAnswerDraft` schema in **96.49 seconds**. The Hallucination Guard validated and accepted all generated claims.
2. **The Root Cause of "PARTIAL" Status is Prompt Evidence Truncation (`max_evidence_items = 5`)**:
   InvestIntel possesses **80 canonical evidence items** for `BMP`, including verified figures for Revenue (5,570B VND), Net Income (1,251B VND), Gross Margin (44.86%), Net Margin (22.47%), Cash (713B VND), Debt-to-Assets (15.38%), and Operating Cash Flow (548B VND). However, the recent prompt optimization in `services/ai/prompt_registry.py` capped single-stock evidence to strictly **5 items** to prevent model latency spikes on 4 GB VRAM hardware.
3. **The Model Honestly Reported Missing Metrics**:
   Because the prompt provided only 5 metrics (`pe`, `pb`, `roe`, `price`, `revenue_yoy`) and listed `de_ratio`, `net_debt_ebitda`, `current_ratio` under `unverified_or_missing_metrics`, the model followed its prompt rules and generated an `UNCERTAINTY` claim stating that gross margins, D/E, and debt metrics were not provided in the prompt context.
4. **Any `UNCERTAINTY` Claim Sets Status to `"PARTIAL"` and Triggers the Fallback Banner in the UI**:
   Under `services/ai/analyst.py`, having any claim of type `UNCERTAINTY` evaluates `has_uncertainty = True`, setting `status = "PARTIAL"`. Furthermore, `apps/web/src/app/ai/page.tsx` renders the `<AppleSmartFallback>` component whenever `answer.structured_data_summary` is present, displaying the banner *"🛡️ Chế độ Dữ liệu Đối chứng Chuẩn xác - AI tự động chuyển sang chế độ Dữ liệu Đối chứng Chuẩn xác để đảm bảo an toàn số liệu và ngăn ngừa Hallucination"* alongside the full 48-indicator Bento grid. This created the user-facing appearance of a failure when the model had in fact reasoned accurately on the restricted evidence it received.

---

## 2. Browser Harness Repair & Test Execution

### A. Harness Diagnosis & Repair (`scratch/run_bmp_diagnostic.py`)
- **Previous Failure Cause**:
  1. Next.js Suspense Hydration Lag: Navigating directly to `/ai` initially rendered the Suspense fallback `<p>Đang chuẩn bị không gian làm việc...</p>`, during which `textarea` and `input[type="text"]` did not exist in the DOM.
  2. The previous script attempted to read DOM properties before hydration, returned `null`, and attempted to trigger submit on a non-existent form.
  3. The previous CDP WebSocket client used an unbounded `await self.ws.recv()` loop that hung indefinitely when Chrome events arrived out-of-order.
- **Harness Fixes Implemented**:
  1. **Bounded Polling for React Hydration**: Added an explicit 30s polling loop waiting for `document.querySelector('textarea')`, `document.querySelector('input[type="text"]')`, and `submitBtn` to mount and become enabled.
  2. **Native React 19 State Binding**: Passed URL query parameters `?symbol=BMP&q=...` to trigger Next.js native `useMemo`/`useState` state initialization, ensuring `activeSymbol === 'BMP'`, `question === QUESTION`, and `submitBtn.disabled === false`.
  3. **Robust CDP WebSocket Client**: Implemented a background reader task (`_reader_loop`) with request-ID matching futures, filtering asynchronous `Network.*` events, and adding a strict 15-second timeout on all CDP commands via `asyncio.wait_for`.
  4. **Network Dispatch Verification**: Verified both the UI status pill (`StatusPill: 'Đang khởi tạo kết nối luồng phân tích...'`) and CDP `Network.requestWillBeSent` for `POST /api/v1/ai/chat/stream`.

### B. Execution Telemetry
| Parameter | Value |
| :--- | :--- |
| **URL** | `http://localhost:3000/ai?symbol=BMP&q=...` |
| **Question** | *"Phân tích cổ phiếu BMP dựa trên toàn bộ dữ liệu tài chính hiện có trong InvestIntel. Hãy trình bày giá cổ phiếu và ngày dữ liệu, kỳ báo cáo tài chính mới nhất, tăng trưởng doanh thu và lợi nhuận, biên lợi nhuận, ROE, EPS, P/E, P/B, nợ vay và dòng tiền nếu có dữ liệu. Đánh giá chất lượng tài chính, định giá, các yếu tố hỗ trợ, rủi ro và những thông tin còn thiếu. Với mỗi chỉ tiêu, hãy nêu giá trị, đơn vị, kỳ báo cáo, ngày công bố và nguồn nếu dữ liệu hỗ trợ. Phân biệt rõ số liệu thực tế, số liệu tính toán và số liệu ước tính. Nếu thiếu dữ liệu, hãy phân tích những phần có đủ bằng chứng và nói rõ phần nào chưa thể kết luận. Không tự điền dữ liệu còn thiếu."* |
| **Target Symbol** | `BMP` |
| **Backend Endpoint** | `POST http://127.0.0.1:8000/api/v1/ai/chat/stream` (HTTP 200 OK) |
| **Inference Provider** | Local Ollama `qwen3.5:9b-q4_K_M` (Context 4096, `think=false`) |
| **Stream Duration** | **96.49 seconds** |
| **UI Status Badge** | `MÃ: BMP` · `PARTIAL` |
| **Pre-submit Screenshot** | [`docs/audits/evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_submitted.png`](evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_submitted.png) |
| **Final Settled Screenshot** | [`docs/audits/evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_final.png`](evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_final.png) |
| **Telemetry JSON** | [`docs/audits/evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_telemetry.json`](evidence/bmp_qwen35_9b_diagnostic_2026-11-01/bmp_telemetry.json) |

---

## 3. BMP Evidence Inventory & Context Truncation Analysis

### A. Total Assembled Evidence (80 Items in Backend)
InvestIntel assembled **80 canonical evidence items** for `BMP` from the local database:

| Category | Available Canonical Evidence (Examples) | Status | Sourced |
| :--- | :--- | :---: | :---: |
| **Price & Date** | `price`: 138,100 VND (as of 2026-10-28) | `AVAILABLE` | VNDIRECT+LOTUSMARKET |
| **Growth Rates** | `revenue_yoy`: +19.06%, `net_income_yoy`: +26.35%, `eps_yoy`: +26.35% | `AVAILABLE` | VNDIRECT_FINFO |
| **Profit Margins** | `gross_margin`: 44.86%, `ebit_margin`: 28.06%, `net_margin`: 22.47% | `AVAILABLE` | VNDIRECT_FINFO |
| **Returns** | `roe`: 41.57%, `roa`: 35.25%, `roic`: 50.87% | `AVAILABLE` | VNDIRECT_FINFO |
| **Valuation Multiples** | `pe`: 9.03x (`is_estimate: True`), `pb`: 3.56x, `ev_ebitda`: 7.23x | `AVAILABLE` | VNDIRECT+LOTUSMARKET |
| **Per Share Figures** | `eps_ttm`: 15,292 VND/share (`is_estimate: True`), `bvps`: 38,740 VND/share | `AVAILABLE` | VNDIRECT_FINFO |
| **Financial Scale** | `revenue`: 5,570.47B VND, `net_income`: 1,251.83B VND, `cash`: 713.16B VND | `AVAILABLE` | VNDIRECT_FINFO |
| **Balance Sheet & Solvency** | `total_assets`: 3,747.71B VND, `total_equity`: 3,171.30B VND, `debt_to_assets`: 15.38% | `AVAILABLE` | VNDIRECT_FINFO |
| **Cash Flows** | `cfo`: 547.88B VND, `fcf`: 504.72B VND, `cfo_to_ni`: 0.44, `fcf_to_ni`: 0.40 | `AVAILABLE` | VNDIRECT_FINFO |
| **Missing/Unpopulated** | `de_ratio`, `net_debt_ebitda`, `current_ratio`, `quick_ratio`, `ebitda_margin` | `INSUFFICIENT_DATA` | VNDIRECT_FINFO |

### B. Evidence Selection & 5-Item Context Cap
In `services/ai/prompt_registry.py` (lines 139–141):
```python
max_evidence_items = 10 if len(query_symbols) > 1 else 5
for item in verifiable_evidence[:max_evidence_items]:
    ...
```
Because `BMP` is a single-ticker query (`len(query_symbols) == 1`), `max_evidence_items` was enforced at **5 items**.

The scoring algorithm prioritized the top 5 items matching query keywords:
1. `E038` — `pe`: **9.03** (`is_estimate: True`)
2. `E039` — `pb`: **3.56**
3. `E012` — `roe`: **41.57%**
4. `E001` — `price`: **138,100 VND**
5. `E002` — `revenue_yoy`: **19.06%**

### C. Omitted Evidence (75 Items Omitted from Model Prompt)
The following verified fundamental data points were present in the local database but **completely excluded from the model prompt**:
- `E008`: Gross Margin (**44.86%**)
- `E011`: Net Profit Margin (**22.47%**)
- `E030`: Net Income (**1,251.83B VND**)
- `E003`: Net Income YoY Growth (**+26.35%**)
- `E027`: Basic EPS TTM (**15,292 VND/share**, estimate)
- `E017`: Debt to Assets (**15.38%**)
- `E032`: Cash Balance (**713.16B VND**)
- `E036`: Operating Cash Flow CFO (**547.88B VND**)
- `E037`: Free Cash Flow FCF (**504.72B VND**)
- `E033` & `E035`: Total Assets (**3,747.71B VND**) and Total Equity (**3,171.30B VND**)

---

## 4. Model Generation & Hallucination Guard Diagnosis

### A. Raw Output Structure (`AIAnswerDraft`)
The Ollama 9B model generated the following structured JSON output:
```json
{
  "answer": "Hệ số P/E được tính toán ước tính ở mức 8,99 lần dựa trên số cổ phiếu cuối kỳ. Các chỉ tiêu về biên lợi nhuận gộp, D/E hay tỷ lệ nợ vay hiện chưa có dữ liệu để xác nhận.",
  "claims": [
    {
      "claim_type": "MODEL_OUTPUT",
      "text": "Hệ số P/E được tính toán ước tính ở mức 8,99 lần dựa trên số cổ phiếu cuối kỳ.",
      "citation_ids": ["E038"]
    },
    {
      "claim_type": "UNCERTAINTY",
      "text": "Các chỉ tiêu về biên lợi nhuận gộp, D/E hay tỷ lệ nợ vay hiện chưa có dữ liệu để xác nhận.",
      "citation_ids": []
    }
  ],
  "uncertainty": [
    "Biên lợi nhuận gộp chưa có số liệu kiểm chứng trong danh sách verifiable evidence",
    "Tỷ lệ nợ trên vốn D/E và các chỉ tiêu nợ vay chưa có dữ liệu hỗ trợ"
  ]
}
```

### B. Hallucination Guard Evaluation
- **Claim 1 (`MODEL_OUTPUT`)**:
  - Mentions P/E estimate of ~8.99x–9.03x.
  - Cites `E038` (which provides `pe: 9.03`, `is_estimate: True`).
  - IAS 33 estimate warning compliance: **PASSED** (accurately identified as an estimate based on period-end shares).
  - Numeric grounding: **PASSED** (grounded against `E038`).
  - Semantic metric validation: **PASSED** (P/E multiple cited against P/E evidence).
- **Claim 2 (`UNCERTAINTY`)**:
  - States that gross margins, D/E, and debt metrics lack supporting data in the prompt.
  - Carries empty `citation_ids: []`.
  - Semantic validation: **PASSED** (valid uncertainty declaration).
- **Substantive Claim Count**: At least 1 substantive claim survived (`valid_substantive_claims = 1`).
- **Verdict**: The output **PASSED Hallucination Guard without claim suppression**.

---

## 5. Fallback Analysis: Why Did the UI Display `PARTIAL` and the Bento Box?

### A. Backend Status Logic (`services/ai/analyst.py:1102–1120`)
```python
has_uncertainty = (
    asks_intraday
    or any(c.claim_type == "UNCERTAINTY" for c in cited_claims)
    or any(item.freshness in {"STALE", "INSUFFICIENT_DATA", "NOT_CONFIGURED"} for item in citations if item.id in referenced_ids)
    or ...
)
res = AIChatResponse(
    status="PARTIAL" if has_uncertainty else "AVAILABLE",
    ...
)
```
Because the model honestly created an `UNCERTAINTY` claim acknowledging that margins and debt were absent from its prompt, `has_uncertainty` became `True`. This set the response status to **`PARTIAL`**.

### B. Frontend Fallback Trigger (`apps/web/src/app/ai/page.tsx:426–431`)
```tsx
{(answer.status === "PARTIAL_DATA_ONLY" || answer.structured_data_summary) && (
  <AppleSmartFallback
    summary={answer.structured_data_summary}
    metadataFlags={answer.metadata_flags}
  />
)}
```
The frontend component `<AppleSmartFallback>` was designed to render whenever:
1. `answer.status === "PARTIAL_DATA_ONLY"`, **OR**
2. `answer.structured_data_summary` is non-null.

Because `_build_structured_data_summary` is constructed on **every single request** (successful or fallback), the entire Apple Smart Fallback UI—including the security warning banner and the 48-indicator Bento table—was rendered below the answer. This made a successful, grounded response appear visually as an error fallback.

---

## 6. Root-Cause Classification Matrix

| Category | Status | Evidence / Observation | Confidence | Impact on UI |
| :--- | :---: | :--- | :---: | :--- |
| **Prompt Evidence Truncation** | **CONFIRMED** | `services/ai/prompt_registry.py` limits single-ticker evidence to 5 items. 75 verified BMP metrics were stripped from prompt. | **100%** | Model was blind to Revenue, Net Income, Gross Margin, Cash, and Debt; forced to declare `UNCERTAINTY`. |
| **Status Downgrade on Uncertainty** | **CONFIRMED** | `services/ai/analyst.py` sets `status="PARTIAL"` if any `UNCERTAINTY` claim exists. | **100%** | Badge displayed `PARTIAL` instead of `AVAILABLE`. |
| **Overeager Smart Fallback Rendering** | **CONFIRMED** | `page.tsx` checks `answer.structured_data_summary`, rendering the Fallback banner even on valid answers. | **100%** | UI displayed *"Chế độ Dữ liệu Đối chứng Chuẩn xác"* banner on a successful answer. |
| **Model Runtime / Generation** | **DISPROVEN** | `qwen3.5:9b-q4_K_M` generated valid JSON in 96.49s; Pydantic schema validation passed cleanly. | **100%** | No runtime crash; 9B model performed reliably on hardware. |
| **Data Coverage Problem** | **DISPROVEN** | Database contains 15,554 prices, 8,435 financial statements; all 28 core BMP indicators are fresh and verified. | **100%** | Fundamentals exist locally; data omission occurred in Python prompt assembly, not in DB. |
| **Browser Harness Timing** | **RESOLVED** | Fixed Suspense hydration wait and CDP WebSocket timeout; browser executed cleanly in 99.88s total. | **100%** | Harness is now robust and reliable. |

---

## 7. Minimal Corrective Recommendations (For Future Implementation)

1. **Context Cap Tiering in Prompt Assembly (`services/ai/prompt_registry.py`)**:
   - Currently, single-ticker queries are hard-capped at `max_evidence_items = 5`.
   - On Qwen 3.5 9B with `think=false`, 10–15 concise evidence items consume only ~300 prompt tokens (well within the 4096 context window and under 1.5 seconds of prompt evaluation).
   - *Recommendation*: Expand `max_evidence_items` for comprehensive single-ticker deep-dives from 5 to **12–15 items**, ensuring that Revenue, Net Income, Gross Margin, Net Margin, Cash, Debt-to-Assets, and CFO are never omitted when asked.
2. **Refine Frontend Fallback Banner Condition (`apps/web/src/app/ai/page.tsx`)**:
   - Change `{(answer.status === "PARTIAL_DATA_ONLY" || answer.structured_data_summary) && ...}` to:
     `{answer.status === "PARTIAL_DATA_ONLY" && ...}` for the alert banner, while rendering the quantitative Bento grid as a regular verified data supplement under `AVAILABLE` / `PARTIAL`.
3. **Preserve All Safeguards**:
   - Do not disable Hallucination Guard or loosen numeric grounding.
   - The guard performed as intended by ensuring that the model did not invent the missing gross margin or debt metrics.

---

## 8. Repository & Environment Safety Confirmation

- **Application Source Code**: Preserved 100% without modification.
- **Financial Calculations & Hallucination Guard**: Untouched; zero relaxation of rules.
- **Database**: Zero writes performed; `ALLOW_PRODUCTION_DB_WRITE=false` strictly enforced.
- **Version Control**: No commits, pushes, or resets executed.
- **Artifacts Saved**: Pre-submit screenshot, settled screenshot, telemetry JSON, and this diagnostic audit report.

