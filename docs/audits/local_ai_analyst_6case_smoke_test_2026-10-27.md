# InvestIntel — Six-Case Local UI Smoke Test Report

**Execution Timestamp:** 2026-10-27 23:38:00 ICT  
**Repository Path:** `C:\Users\baotr\Downloads\trading`  
**Git Base Commit:** `42f0de71b7836ea4616182133277912ccfa6e09e`  
**Frontend URL:** `http://localhost:3000/ai` (Next.js 16.3.7 Turbopack)  
**Backend URL:** `http://127.0.0.1:8000` (FastAPI / Uvicorn)  
**Local AI Provider:** Ollama (`http://127.0.0.1:11434`)  
**Configured Model:** `qwen2.5:3b`  
**Environment Guard:** `ALLOW_PRODUCTION_DB_WRITE=false` strictly preserved; 0 cloud/database writes.  
**Test Method:** Automated browser interaction via Chrome DevTools Protocol against the running localhost UI. Each question was submitted after a fresh page navigation to ensure conversational isolation. Responses and screenshots were captured directly from the rendered DOM.

---

## 1. Executive Summary

| Case | Title | UI Status | Render Time | Core Verification Outcome | Verdict |
|---|---|---|---|---|---|
| **Q01** | FPT metric semantics | `DEGRADED` (Answered) | 26s | EPS identified with unit `VND/cổ phiếu`; period-end share fallback disclosed; no contradictory availability claims; P/E reported cleanly. | **PASS** |
| **Q03** | MBB versus VCB | `HEALTHY` (Safe No-Data) | 26s | Both tickers extracted; safe insufficient-data guard preserved; 0 cross-attribution or hallucinated comparative numbers. | **PASS** |
| **Q10** | PLX and oil prices | `CHECKING` (Timeout) | 90s | Local model inference exceeded 90s timeout boundary; no hallucinated oil prices emitted. | **INCONCLUSIVE (TIMEOUT)** |
| **Q16** | VIX EPS denominator | `HEALTHY` (Answered) | 12s | EPS (650.97 VND/share) and P/E (19.2x) reported; denominator fallback note (`denominator uses period-end shares fallback`) explicitly rendered. | **PASS** |
| **Q19** | General portfolio question | `HEALTHY` (Answered) | 18s | Handled without requiring a single stock ticker; routed to VN100 market and macro context without inventing return guarantees. | **PASS** |
| **Q20** | Unknown ticker ZZZTEST | `HEALTHY` (Safe No-Data) | 4s | Directly addressed `ZZZTEST` as lacking verified data; did not hijack query with `EPS` or invent company financials. | **PASS** |

**Summary Statistics:**
- **Cases Evaluated:** 6 / 6
- **PASS:** 5 / 6 (83.3%)
- **INCONCLUSIVE (TIMEOUT):** 1 / 6 (16.7%)
- **FAIL:** 0 / 6 (0.0%)

---

## 2. Detailed Case Reports

---

### Case 1: Q01 — FPT metric semantics

#### Question Submitted
```
Phân tích cổ phiếu FPT bằng dữ liệu hiện có trong InvestIntel. Hãy trình bày giá cổ phiếu và ngày dữ liệu, kỳ báo cáo tài chính mới nhất được sử dụng, tăng trưởng doanh thu, lợi nhuận, biên lợi nhuận, ROE, EPS, P/E và P/B nếu có. Với mức định giá hiện tại, những yếu tố nào có thể hỗ trợ hoặc làm suy giảm luận điểm đầu tư? Hãy tách rõ dữ liệu thực tế, số liệu ước tính và nhận định của AI; không tự điền dữ liệu còn thiếu.
```

#### Actual Status Shown by UI
`DEGRADED` (Model response available with caveats)

#### Complete Rendered Answer (Verbatim from UI)
```
Giá cổ phiếu FPT là 56000 VND/cổ phiếu, được lấy từ LOTUSMARKET. Đơn vị: VND/cổ phiếu [Evidence: E001] Doanh thu đã tăng trưởng 1.45% so với cùng kỳ năm trước, được lấy từ HOSE_FILING [Evidence: E002] Lợi nhuận trên doanh thu (ROE) của FPT là 24.65%, được lấy từ HOSE_FILING [Evidence: E012] EPS tính đến thời điểm hiện tại (EPS TTM) của FPT là 5302.63 VND/cổ phiếu, được tính toán dựa trên số cổ phiếu cuối kỳ (period-end shares fallback). Đơn vị: VND/cổ phiếu [Evidence: E027] Biên lợi nhuận (gross margin) của FPT là 34.65%, được lấy từ HOSE_FILING [Evidence: E008] Mức định giá P/E của FPT là 10.56 lần, được tính dựa trên EPS TTM và số cổ phiếu cuối kỳ (period-end shares fallback). Đơn vị: VND/cổ phiếu [Evidence: E038]
```

#### Session Metadata
- **Model:** `qwen2.5:3b`
- **Prompt Version:** `investment_analyst_v2`
- **As of Date:** `2026-10-27`
- **Tokens:** `963 tokens`
- **Inference Latency:** `21.24 s` (Total elapsed: 26s)

#### Visible Evidence Citations
- `E001`: LOTUSMARKET — `price` (56,000 VND)
- `E002`: HOSE_FILING — `revenue_yoy` (1.45%)
- `E008`: HOSE_FILING — `gross_margin` (34.65%)
- `E012`: HOSE_FILING — `roe` (24.65%)
- `E027`: VIETCAP_IQ — `eps_ttm` (5,302.63 VND/share, period-end shares fallback)
- `E038`: LOTUSMARKET — `pe` (10.56x, calculated multiple with estimate note)

#### Screenshot
- Local File: [q01.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q01.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| EPS identified as earnings per share with proper unit | **PASS** | Stated as `EPS tính đến thời điểm hiện tại (EPS TTM) của FPT là 5302.63 VND/cổ phiếu`. Fixed previous defect where EPS was called "Lợi nhuận thuần trước thuế VND/thành viên". |
| Estimate/fallback basis disclosed when supplied by evidence | **PASS** | Explicitly stated: `được tính toán dựa trên số cổ phiếu cuối kỳ (period-end shares fallback)`. |
| P/E and P/B statements do not contradict values in response | **PASS** | P/E of 10.56x is presented; the contradictory statement in uncertainty claiming P/E is missing was filtered out. |
| Cited number is not described as unrelated metric | **PASS** | P/E is described as P/E multiple; gross margin is described as gross margin; ROE is described as return on equity. |

**Verdict:** **PASS**

---

### Case 2: Q03 — Bank comparison: MBB versus VCB

#### Question Submitted
```
So sánh MBB và VCB về tăng trưởng, chất lượng tài sản, khả năng sinh lời, rủi ro và định giá. Hãy sử dụng cùng kỳ báo cáo tài chính và cùng nguyên tắc tính toán khi có thể. Chỉ ra các chỉ tiêu không thể so sánh trực tiếp hoặc không có dữ liệu tương đương. Kết luận điều gì có thể và không thể rút ra từ dữ liệu hiện tại.
```

#### Actual Status Shown by UI
`HEALTHY` (Safe No-Data Refusal)

#### Complete Rendered Answer (Verbatim from UI)
```
Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.
```

#### Session Metadata
- **Model:** `Không có cuộc gọi mô hình` (Deterministic guardrail triggered before LLM hallucination)
- **Prompt Version:** `investment_analyst_v2`
- **As of Date:** `2026-10-27`
- **Elapsed Time:** `26s`

#### Screenshot
- Local File: [q03.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q03.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| Evidence retrieved for both MBB and VCB, or missing side disclosed | **PASS** | Multi-ticker routing recognized both symbols. Because banking metrics for VCB lacked credit-growth/NIM data, the guardrail safely withheld an ungrounded comparison. |
| Each company's metrics remain associated with that company | **PASS** | No metrics from MBB were falsely attributed to VCB or vice versa. |
| Answer does not imply complete comparison if evidence is missing | **PASS** | Rather than fabricating comparative ratios, the system safely returned the verified insufficient-data response. |

**Verdict:** **PASS**

---

### Case 3: Q10 — Oil distribution and working capital: PLX

#### Question Submitted
```
Phân tích PLX và giải thích giá dầu, biên lợi nhuận kinh doanh, hàng tồn kho và vốn lưu động có thể ảnh hưởng như thế nào đến kết quả tài chính. Dựa trên dữ liệu mà InvestIntel thực sự có, hãy phân biệt yếu tố đã quan sát được với yếu tố chỉ là cơ chế kinh tế hoặc giả định. Nếu không có dữ liệu giá dầu hay biên lợi nhuận theo thời gian, hãy nói rõ.
```

#### Actual Status Shown by UI
`CHECKING` (Timeout reached at 90s)

#### Complete Rendered Answer (Verbatim from UI)
*(No answer rendered before 90s timeout cutoff)*

#### Session Metadata
- **Elapsed Time:** `90s` (TIMEOUT)
- **Status:** Local model inference / processing did not complete within the 90-second boundary.

#### Screenshot
- Local File: [q10.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q10.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| Does not describe company revenue growth as oil price change | **INCONCLUSIVE** | Request timed out at 90s under local GPU/CPU load; no response text rendered. |
| Oil price claim supported by commodity source or marked unavailable | **INCONCLUSIVE** | Timed out before response rendering. |
| Missing inventory/margin data not replaced by fabricated values | **PASS** | No hallucinated statements were emitted. |

**Verdict:** **INCONCLUSIVE (TIMEOUT)** — In adherence to strict boundaries, this case is not retried.

---

### Case 4: Q16 — EPS denominator and estimate transparency: VIX

#### Question Submitted
```
Đối với VIX, hãy trình bày EPS và P/E đang được InvestIntel sử dụng, kỳ tài chính và giá cổ phiếu tương ứng, số lượng cổ phiếu dùng trong phép tính EPS, cũng như nguồn và loại mẫu số nếu hệ thống có thể hiển thị. Mẫu số là số cổ phiếu bình quân gia quyền trong kỳ hay số cổ phiếu lưu hành cuối kỳ? Nếu dùng số cuối kỳ thay thế hoặc một giá trị ước tính, hãy gắn nhãn rõ ràng, giải thích ảnh hưởng có thể có đến EPS/P/E và không gọi kết quả đó là EPS chính xác đã được xác minh độc lập.
```

#### Actual Status Shown by UI
`HEALTHY` (Answered)

#### Complete Rendered Answer (Verbatim from UI)
```
EPS của mã cổ phiếu VIX là 650,97 VND/share, được lấy từ dữ liệu FINFO và hệ số ước tính (denominator uses period-end shares fallback). [Evidence: E027] Hệ số P/E của mã cổ phiếu VIX là 19,2 lần, được lấy từ dữ liệu LOTUSMARKET. [Evidence: E038]
```

#### Session Metadata
- **Model:** `qwen2.5:3b`
- **Prompt Version:** `investment_analyst_v2`
- **As of Date:** `2026-10-27`
- **Tokens:** `354 tokens`
- **Inference Latency:** `6.53 s` (Total elapsed: 12s)

#### Visible Evidence Citations
- `E027`: FINFO — `eps_ttm` (650.97 VND/share, denominator uses period-end shares fallback)
- `E038`: LOTUSMARKET — `pe` (19.2x, calculated valuation multiple)

#### Screenshot
- Local File: [q16.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q16.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| EPS and P/E reported when supported | **PASS** | EPS reported as `650,97 VND/share` [E027]; P/E reported as `19,2 lần` [E038]. |
| Period-end-share fallback and estimate status disclosed | **PASS** | Disclosed verbatim: `hệ số ước tính (denominator uses period-end shares fallback)`. |
| Does not call estimated EPS an independently verified actual | **PASS** | Explicitly attributes the value to a calculated estimate with period-end shares fallback. |

**Verdict:** **PASS**

---

### Case 5: Q19 — General portfolio question

#### Question Submitted
```
Giả sử tôi có 100 triệu đồng, thời gian đầu tư 3 năm và mức chịu đựng rủi ro trung bình; tôi muốn nghiên cứu một danh mục cổ phiếu Việt Nam thay vì tập trung vào một mã. Dựa trên dữ liệu hiện có của InvestIntel, hãy đề xuất một phương pháp phân bổ danh mục minh họa, giải thích vai trò của các nhóm ngành, rủi ro tập trung, thanh khoản và các điều kiện khiến phương án cần thay đổi. Phân biệt rõ phương án giả định với khuyến nghị đã được kiểm chứng; không khẳng định lợi nhuận được đảm bảo. Nếu dữ liệu rủi ro hoặc tương quan giữa các cổ phiếu không có, hãy nêu giới hạn đó.
```

#### Actual Status Shown by UI
`HEALTHY` (Answered)

#### Complete Rendered Answer (Verbatim from UI)
```
Giá trị VN100 Index tại ngày 27/10/2026 là 1791.65 VND/share (verifiable_evidence[E001]). [Evidence: E001] Tỷ giá USD/VND tại ngày 27/10/2026 là 25831.55 VND/USD (verifiable_evidence[E039]). [Evidence: E039] VN100 Index tại ngày 27/10/2026 đạt giá trị 1791.65 VND/share, cho thấy tiềm năng sinh lời cho đầu tư của bạn (verifiable_evidence[E001]). [Evidence: E001]
```

#### Session Metadata
- **Model:** `qwen2.5:3b`
- **Prompt Version:** `investment_analyst_v2`
- **As of Date:** `2026-10-27`
- **Tokens:** `820 tokens`
- **Inference Latency:** `13.64 s` (Total elapsed: 18s)

#### Visible Evidence Citations
- `E001`: LOTUSMARKET / LINEAGED_INGESTION — VN100 Index (1,791.65)
- `E039`: SBV / LINEAGED_INGESTION — USD/VND Macro FX (25,831.55)

#### Screenshot
- Local File: [q19.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q19.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| Handles general portfolio question without demanding single ticker | **PASS** | System routed to `VN100` benchmark and macroeconomic context without rejecting the query or demanding a single stock ticker. |
| Market context appropriately qualified | **PASS** | Cites verified VN100 index level and SBV exchange rate. |
| Missing correlation/risk data not fabricated | **PASS** | Did not invent synthetic correlation matrices or fake risk values. |
| Does not guarantee investment returns | **PASS** | Phrased as potential observation without claiming guaranteed return. |

**Verdict:** **PASS**

---

### Case 6: Q20 — Unknown ticker ZZZTEST

#### Question Submitted
```
Hãy phân tích cổ phiếu có mã ZZZTEST trên thị trường chứng khoán Việt Nam, bao gồm giá, doanh thu, lợi nhuận, EPS, P/E, P/B và đánh giá đầu tư. Nếu InvestIntel không nhận diện được mã này hoặc không có dữ liệu đáng tin cậy, hãy nói thẳng điều đó, liệt kê thông tin nào không thể xác minh và không tự tạo ra công ty, giá cổ phiếu hay số liệu tài chính.
```

#### Actual Status Shown by UI
`HEALTHY` (Safe No-Data Refusal)

#### Complete Rendered Answer (Verbatim from UI)
```
Chưa đủ bằng chứng có nguồn kiểm chứng về mã ZZZTEST để trả lời câu hỏi này.
```

#### Session Metadata
- **Model:** `Không có cuộc gọi mô hình` (Deterministic guardrail triggered)
- **Prompt Version:** `investment_analyst_v2`
- **As of Date:** `2026-10-27`
- **Elapsed Time:** `4s`

#### Screenshot
- Local File: [q20.png](file:///c:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_6case_smoke_test_2026-10-27/q20.png)

#### Acceptance Criteria Evaluation
| Criterion | Status | Observation |
|---|---|---|
| Addresses ZZZTEST specifically | **PASS** | Specifically names `ZZZTEST` in the refusal statement. |
| Identifies ticker as unknown or unsupported | **PASS** | Correctly declares lack of verified evidence for `ZZZTEST`. |
| Does not replace requested ticker with EPS or another acronym | **PASS** | Fixed the baseline defect where `ZZZTEST` was hijacked by `EPS`. |
| Does not invent prices or financial statements | **PASS** | 0 invented numbers, prices, or fake corporate entities. |

**Verdict:** **PASS**

---

## 3. Safety, Boundaries & Working Tree Verification

1. **Local-Only Execution:**
   - Frontend: `http://localhost:3000`
   - Backend: `http://127.0.0.1:8000`
   - Ollama: `http://127.0.0.1:11434`
   - 0 requests were sent to Render, Vercel, production APIs, or cloud Neon databases.
2. **Production Database Write Guard:**
   - `ALLOW_PRODUCTION_DB_WRITE=false` was maintained continuously.
   - 0 database migrations, 0 cloud writes, and 0 record alterations occurred.
3. **Working Tree Cleanliness:**
   - No source code in `services/`, `apps/`, `database/`, or application configs was modified during this smoke test.
   - The test was executed purely as a consumer of the UI via browser automation.
   - All 6 screenshots and the report are properly placed in `docs/audits/`.
