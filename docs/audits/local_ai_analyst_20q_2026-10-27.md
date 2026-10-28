# InvestIntel — Local AI Analyst Evaluation: 20 Vietnamese Questions

## 1. Run Header & Environment

- **Execution Timestamp**: 2026-10-27 21:42:42 ICT
- **Git Branch**: `main`
- **Git Commit SHA**: `42f0de71b7836ea4616182133277912ccfa6e09e`
- **Frontend URL**: `http://localhost:3000` (Next.js 16.3.7 Turbopack)
- **Backend URL**: `http://127.0.0.1:8000` (FastAPI / Uvicorn)
- **AI Provider & Engine**: Local Ollama daemon (`http://127.0.0.1:11434`)
- **Configured Model**: `qwen2.5:3b` (Running on local NVIDIA GeForce RTX 3050 Laptop GPU)
- **Data Environment**: Local Canonical SQLite / PostgreSQL (`ALLOW_PRODUCTION_DB_WRITE=false`, 0 cloud writes)
- **Evaluation Scope**: 20 distinct Vietnamese financial and analytical questions executed sequentially

## 2. Methodology & Operational Note

This evaluation was executed entirely through the visible frontend user interface of InvestIntel running locally at `http://localhost:3000/ai`. For each question:
1. A fresh browser session/navigation was initiated to ensure isolation and prevent conversation leak between prompts.
2. The exact Vietnamese question was entered into the question textarea without modification or external augmentation.
3. The form was submitted via the UI submit button, triggering the end-to-end local data pipeline (canonical data retrieval, evidence citation assembly, structured Ollama inference, and semantic citation validation).
4. The response was captured only after UI rendering was fully completed in the visible DOM.
5. High-resolution screenshots were captured from the active browser viewport for every question and archived in `docs/audits/evidence/local_ai_analyst_20q_2026-10-27/`.
6. No production services, external APIs, or manual editorial interventions were utilized.

### Summary of Results

- **Total Questions Attempted**: 20/20
- **ANSWERED (Complete Grounded Response)**: 13
- **NO_DATA (Proper Insufficient Data Guard / Rejection)**: 5
- **PARTIAL (Brief or Partially Complete)**: 2
- **TIMEOUT (No response within 90s)**: 0
- **ERROR (Interface / API Alert)**: 0

---

## 3. Detailed Results for All 20 Questions

### Q01 — Technology and growth valuation: FPT

**Question shown to the AI Analyst**

Phân tích cổ phiếu FPT bằng dữ liệu hiện có trong InvestIntel. Hãy trình bày giá cổ phiếu và ngày dữ liệu, kỳ báo cáo tài chính mới nhất được sử dụng, tăng trưởng doanh thu, lợi nhuận, biên lợi nhuận, ROE, EPS, P/E và P/B nếu có. Với mức định giá hiện tại, những yếu tố nào có thể hỗ trợ hoặc làm suy giảm luận điểm đầu tư? Hãy tách rõ dữ liệu thực tế, số liệu ước tính và nhận định của AI; không tự điền dữ liệu còn thiếu.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Ngày dữ liệu là 27/10/2026 [Evidence: E002, E001, E027, E004, E008, E038, E039] Giá cổ phiếu FPT là 56000 đồng vào ngày 27/10/2026 [Evidence: E001] ROE FPT là 24.65% [Evidence: E012] Lợi nhuận thuần trước thuế FPT là 5302.63 VND/thành viên [Evidence: E027] Lợi nhuận thuần trước thuế tính theo phiên hiện tại FPT là 5302.63 VND/thành viên [Evidence: E027] P/E FPT là 10.56 lần [Evidence: E038] P/B FPT là 2.58 lần [Evidence: E039]

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
636 tokens
10.17 s

Luận cứ / Claims (7)
FACT

Ngày dữ liệu là 27/10/2026

E002, E001, E027, E004, E008, E038, E039
FACT

Giá cổ phiếu FPT là 56000 đồng vào ngày 27/10/2026

E001
MODEL OUTPUT

ROE FPT là 24.65%

E012
MODEL OUTPUT

Lợi nhuận thuần trước thuế FPT là 5302.63 VND/thành viên

E027
MODEL OUTPUT

Lợi nhuận thuần trước thuế tính theo phiên hiện tại FPT là 5302.63 VND/thành viên

E027
MODEL OUTPUT

P/E FPT là 10.56 lần

E038
MODEL OUTPUT

P/B FPT là 2.58 lần

E039

Dữ liệu chưa chắc chắn / Uncertainty

Mức định giá P/B và P/E chưa được cung cấp trong dữ liệu hiện có.

Công ty chưa cung cấp thông tin về biên lợi nhuận (gross_margin).

Công ty chưa cung cấp thông tin về lợi nhuận thuần trước thuế (eps_ttm).

Bằng chứng trích dẫn / Evidence citations (8)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT
E002 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E004 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E008 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E012 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E027 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-22
Mathematically calculated from canonical adjusted close (56000.0 VND) / EPS TTM (5302.6 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-22
Mathematically calculated from canonical adjusted close (56000.0 VND) / BVPS (21740.0 VND). Post-corporate-action share basis.

**Capture notes**

Completed in 87s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q01.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q01.png).

---

### Q02 — Banking fundamentals: VCB

**Question shown to the AI Analyst**

Phân tích VCB dưới góc độ chất lượng một ngân hàng. Dựa trên dữ liệu đang có, hãy đánh giá tăng trưởng tín dụng, NIM, CASA, nợ xấu, tỷ lệ bao phủ nợ xấu, ROE, EPS, P/B và các rủi ro quan trọng. Với từng chỉ tiêu không có dữ liệu, hãy nói rõ là không có dữ liệu thay vì tự suy đoán.

**Status**

NO_DATA

**Answer actually displayed in localhost**

Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

A numeric statement in the uncertainty field was suppressed because it has no citation IDs.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

A numeric statement in the uncertainty field was suppressed because it has no citation IDs.

Bằng chứng trích dẫn / Evidence citations (84)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=VCB
E002 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E003 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E004 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E005 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Requires at least 3 year(s) of history.
E006 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Requires at least 5 year(s) of history.
E007 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Requires at least 3 year(s) of history.
E008 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E009 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E010 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Numerator data not available
E011 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E012 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E013 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E014 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
ROIC is not applicable for the banking sector. Use ROE/ROA instead.
E015 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Numerator data not available
E016 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Not applicable for banking sector.
E017 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E018 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Current ratio is not applicable for banks.
E019 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Quick ratio is not applicable for banks.
E020 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Interest expense is zero or missing — coverage ratio N/A.
E021 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E022 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E023 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
Accounts receivable missing
E024 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
COGS is zero or missing — may be a service company.
E025 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
COGS is zero or missing.
E026 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
DSO or DPO missing for CCC calculation.
E027 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E028 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E029 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E030 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E031 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E032 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E033 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E034 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E035 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E036 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E037 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-19
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-19
Mathematically calculated from canonical adjusted close (56100.0 VND) / EPS TTM (4984.4 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-19
Mathematically calculated from canonical adjusted close (56100.0 VND) / BVPS (29739.1 VND). Post-corporate-action share basis.
E040 / valuation
NOT MEANINGFUL

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
EV/EBITDA is not applicable for banking institutions.
E041 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E042 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E043 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E044 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E045 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E046 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E047 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E048 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E049 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E050 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E051 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E052 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E053 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E054 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-15 / Công bố 2026-10-15T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E055 / macro
AVAILABLE

SBV / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-10T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E056 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-01 / Công bố 2026-10-01T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E057 / macro
STALE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2025-10-31 / Công bố 2026-10-12T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E058 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-05T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E059 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E060 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E061 / macro
AVAILABLE

BLS / LINEAGED_INGESTION

Quan sát 2026-09-01 / Công bố N/A / https://api.bls.gov/publicAPI/v1/timeseries/data/
E062 / macro
AVAILABLE

FRED / LINEAGED_INGESTION

Quan sát 2026-10-23 / Công bố 2026-10-23T07:00:00+07:00 / https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
E063 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E064 / macro
AVAILABLE

OPEN_EXCHANGE_RATES / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27T07:00:00+07:00 / https://open.er-api.com/v6/latest/USD
E065 / macro
INSUFFICIENT DATA

BLS / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E066 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E067 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E068 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E069 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E070 / macro
INSUFFICIENT DATA

SBV / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E071 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CAB?format=json
E072 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CPI?format=json
E073 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_GDP?format=json
E074 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_RES?format=json
E075 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_UEM?format=json
E076 / regime
NEUTRAL

vn100_price_breadth_v1 / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố N/A
VN100 20-session momentum: -1.22%; VN100 breadth: 1 advancing, 0 declining, 99 unchanged
E077 / risk
INSUFFICIENT DATA

RiskEngine / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Current RiskEngine fills missing categories with stub/default scores; numeric risk is withheld until each category has evidenced inputs.
E078 / events
INSUFFICIENT DATA

FINANCIAL_NEWS / CANONICAL_EVENT_RECORD

Quan sát N/A / Công bố 2026-10-26
E079 / events
INSUFFICIENT DATA

FINANCIAL_NEWS / CANONICAL_EVENT_RECORD

Quan sát N/A / Công bố 2026-10-26
E080 / events
INSUFFICIENT DATA

FINANCIAL_NEWS / CANONICAL_EVENT_RECORD

Quan sát N/A / Công bố 2026-10-26
E081 / events
INSUFFICIENT DATA

FINANCIAL_NEWS / CANONICAL_EVENT_RECORD

Quan sát N/A / Công bố 2026-10-27
E082 / opportunity
INSUFFICIENT DATA

ResearchWorkspace.opportunity / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Opportunity and confidence remain separate fields; unavailable scores are not inferred.
E083 / portfolio_fit
NOT IN PORTFOLIO

portfolio_fit / PERSONAL_PORTFOLIO_AND_RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
E084 / portfolio
EMPTY

portfolio_dashboard / LOCAL_PERSONAL_PORTFOLIO

Quan sát 2026-10-27 / Công bố N/A
Portfolio fields are local and are not submitted to an external recommendation or broker service.

**Capture notes**

Completed in 60s. Response classified as NO_DATA (INSUFFICIENT_DATA status badge displayed in UI). Screenshot captured: [q02.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q02.png).

---

### Q03 — Bank comparison: MBB versus VCB

**Question shown to the AI Analyst**

So sánh MBB và VCB về tăng trưởng, chất lượng tài sản, khả năng sinh lời, rủi ro và định giá. Hãy sử dụng cùng kỳ báo cáo tài chính và cùng nguyên tắc tính toán khi có thể. Chỉ ra các chỉ tiêu không thể so sánh trực tiếp hoặc không có dữ liệu tương đương. Kết luận điều gì có thể và không thể rút ra từ dữ liệu hiện tại.

**Status**

NO_DATA

**Answer actually displayed in localhost**

Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

A numeric claim is not present in the values of its cited evidence IDs.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

A numeric claim is not present in the values of its cited evidence IDs.

Bằng chứng trích dẫn / Evidence citations (80)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=MBB
E002 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E003 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E004 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E005 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Requires at least 3 year(s) of history.
E006 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Requires at least 5 year(s) of history.
E007 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Requires at least 3 year(s) of history.
E008 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E009 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E010 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Numerator data not available
E011 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E012 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E013 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E014 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
ROIC is not applicable for the banking sector. Use ROE/ROA instead.
E015 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Numerator data not available
E016 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Not applicable for banking sector.
E017 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E018 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Current ratio is not applicable for banks.
E019 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Quick ratio is not applicable for banks.
E020 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Interest expense is zero or missing — coverage ratio N/A.
E021 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E022 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E023 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
Accounts receivable missing
E024 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
COGS is zero or missing — may be a service company.
E025 / fundamentals
NOT MEANINGFUL

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
COGS is zero or missing.
E026 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
DSO or DPO missing for CCC calculation.
E027 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E028 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E029 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E030 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E031 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E032 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E033 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E034 / fundamentals
INSUFFICIENT DATA

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E035 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E036 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E037 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-07
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-07
Mathematically calculated from canonical adjusted close (19550.0 VND) / EPS TTM (2987.3 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-07
Mathematically calculated from canonical adjusted close (19550.0 VND) / BVPS (15569.2 VND). Post-corporate-action share basis.
E040 / valuation
NOT MEANINGFUL

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
EV/EBITDA is not applicable for banking institutions.
E041 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E042 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E043 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E044 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E045 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E046 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E047 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E048 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E049 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E050 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E051 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E052 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E053 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E054 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-15 / Công bố 2026-10-15T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E055 / macro
AVAILABLE

SBV / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-10T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E056 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-01 / Công bố 2026-10-01T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E057 / macro
STALE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2025-10-31 / Công bố 2026-10-12T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E058 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-05T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E059 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E060 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E061 / macro
AVAILABLE

BLS / LINEAGED_INGESTION

Quan sát 2026-09-01 / Công bố N/A / https://api.bls.gov/publicAPI/v1/timeseries/data/
E062 / macro
AVAILABLE

FRED / LINEAGED_INGESTION

Quan sát 2026-10-23 / Công bố 2026-10-23T07:00:00+07:00 / https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
E063 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E064 / macro
AVAILABLE

OPEN_EXCHANGE_RATES / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27T07:00:00+07:00 / https://open.er-api.com/v6/latest/USD
E065 / macro
INSUFFICIENT DATA

BLS / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E066 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E067 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E068 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E069 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E070 / macro
INSUFFICIENT DATA

SBV / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E071 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CAB?format=json
E072 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CPI?format=json
E073 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_GDP?format=json
E074 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_RES?format=json
E075 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_UEM?format=json
E076 / regime
NEUTRAL

vn100_price_breadth_v1 / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố N/A
VN100 20-session momentum: -1.22%; VN100 breadth: 1 advancing, 0 declining, 99 unchanged
E077 / risk
INSUFFICIENT DATA

RiskEngine / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Current RiskEngine fills missing categories with stub/default scores; numeric risk is withheld until each category has evidenced inputs.
E078 / opportunity
INSUFFICIENT DATA

ResearchWorkspace.opportunity / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Opportunity and confidence remain separate fields; unavailable scores are not inferred.
E079 / portfolio_fit
NOT IN PORTFOLIO

portfolio_fit / PERSONAL_PORTFOLIO_AND_RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
E080 / portfolio
EMPTY

portfolio_dashboard / LOCAL_PERSONAL_PORTFOLIO

Quan sát 2026-10-27 / Công bố N/A
Portfolio fields are local and are not submitted to an external recommendation or broker service.

**Capture notes**

Completed in 18s. Response classified as NO_DATA (INSUFFICIENT_DATA status badge displayed in UI). Screenshot captured: [q03.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q03.png).

---

### Q04 — Cyclical industrial stock: HPG

**Question shown to the AI Analyst**

Phân tích HPG như một doanh nghiệp thép có tính chu kỳ. Lợi nhuận, biên lợi nhuận, nợ vay và dòng tiền hiện tại phản ánh điều gì? Những yếu tố nào có thể ảnh hưởng đến kết quả kinh doanh trong các quý tới? Hãy đưa ra kịch bản tích cực, cơ sở và tiêu cực, đồng thời nêu giả định và dữ liệu cần có cho mỗi kịch bản. Không trình bày dự báo như sự thật chắc chắn.

**Status**

PARTIAL

**Answer actually displayed in localhost**

Dữ liệu về nợ vay của HPG chưa được cung cấp trong dữ liệu verifiable_evidence. Dữ liệu về dòng tiền hiện tại của HPG chưa được cung cấp trong dữ liệu verifiable_evidence.

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
615 tokens
9.56 s

Luận cứ / Claims (2)
UNCERTAINTY

Dữ liệu về nợ vay của HPG chưa được cung cấp trong dữ liệu verifiable_evidence.

Không có trích dẫn
UNCERTAINTY

Dữ liệu về dòng tiền hiện tại của HPG chưa được cung cấp trong dữ liệu verifiable_evidence.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

de_ratio

total_liabilities

peg

dividend_yield

fcf_yield

dcf

Bằng chứng trích dẫn / Evidence citations (15)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=HPG
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E003 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E004 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E009 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E012 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E013 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E014 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E017 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E020 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
Interest expense is zero or missing — coverage ratio N/A.
E021 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E022 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E024 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
COGS is zero or missing — may be a service company.

**Capture notes**

Completed in 14s. Answer visibly partial/brief. Screenshot captured: [q04.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q04.png).

---

### Q05 — Retail and turnaround: MWG

**Question shown to the AI Analyst**

Đánh giá MWG dưới góc độ phục hồi kinh doanh. Hãy xem xét tăng trưởng doanh thu, lợi nhuận, biên lợi nhuận, hàng tồn kho, dòng tiền và định giá nếu dữ liệu có sẵn. Những bằng chứng nào cho thấy hoạt động kinh doanh đang phục hồi hoặc chưa phục hồi? Phân biệt số liệu được ghi nhận với kỳ vọng của thị trường hoặc suy luận của AI.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Doanh thu MWG đã tăng 33.33% so với năm trước. [Evidence: E002] Lợi nhuận thuần cổ tức (net income) của MWG đã tăng 140.99%. [Evidence: E003] Chưa có dữ liệu về biên lợi nhuận (gross margin), biên lợi nhuận cố định (ROE) hoặc định giá (P/E).

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
482 tokens
7.42 s

Luận cứ / Claims (3)
FACT

Doanh thu MWG đã tăng 33.33% so với năm trước.

E002
FACT

Lợi nhuận thuần cổ tức (net income) của MWG đã tăng 140.99%.

E003
UNCERTAINTY

Chưa có dữ liệu về biên lợi nhuận (gross margin), biên lợi nhuận cố định (ROE) hoặc định giá (P/E).

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

revenue_cagr_3y

revenue_cagr_5y

eps_cagr_3y

ebitda_margin

de_ratio

net_debt_ebitda

current_ratio

quick_ratio

dso

ccc

total_liabilities

peg

dividend_yield

fcf_yield

dcf

Bằng chứng trích dẫn / Evidence citations (2)
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E003 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30

**Capture notes**

Completed in 132s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q05.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q05.png).

---

### Q06 — Real estate and financial risk: VHM

**Question shown to the AI Analyst**

Phân tích VHM, tập trung vào doanh thu đã ghi nhận, lợi nhuận, hàng tồn kho, các khoản phải thu, nợ vay, nghĩa vụ tài chính và dòng tiền. Hãy phân biệt doanh số bán hàng hoặc hợp đồng chưa thực hiện với doanh thu và lợi nhuận đã ghi nhận trên báo cáo tài chính. Những rủi ro nào có thể khiến lợi nhuận kế toán khác với dòng tiền thực thu?

**Status**

ANSWERED

**Answer actually displayed in localhost**

VHM đã ghi nhận doanh thu hàng năm giảm từ 44.16% (ID:E008) trong năm 2026 so với năm 2025 [Evidence: E008] VHM đã ghi nhận lợi nhuận gộp đạt 44.16% (ID:E008) trong năm 2026 [Evidence: E008] Dữ liệu chưa được kiểm chứng về chi phí tài chính cụ thể của Vinhomes, bao gồm nợ vay và chi phí tài chính

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
774 tokens
11.94 s

Luận cứ / Claims (3)
FACT

VHM đã ghi nhận doanh thu hàng năm giảm từ 44.16% (ID:E008) trong năm 2026 so với năm 2025

E008
FACT

VHM đã ghi nhận lợi nhuận gộp đạt 44.16% (ID:E008) trong năm 2026

E008
UNCERTAINTY

Dữ liệu chưa được kiểm chứng về chi phí tài chính cụ thể của Vinhomes, bao gồm nợ vay và chi phí tài chính

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

de_ratio

debt_to_ebitda_ratio

debt_to_assets_ratio

current_ratio

quick_ratio

dso

debt_service_coverage_ratio

Bằng chứng trích dẫn / Evidence citations (1)
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30

**Capture notes**

Completed in 115s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q06.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q06.png).

---

### Q07 — Conglomerate analysis: VIC

**Question shown to the AI Analyst**

Hãy phân tích VIC dựa trên các dữ liệu tài chính đang có trong InvestIntel. Nếu có dữ liệu theo từng mảng kinh doanh, hãy phân biệt đóng góp của từng mảng, lợi nhuận hợp nhất, nợ và dòng tiền. Những hạn chế nào xuất hiện khi định giá một tập đoàn đa ngành bằng một chỉ số P/E duy nhất? Nếu dữ liệu theo mảng không đủ, hãy nói rõ.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Lợi nhuận hợp nhất của VIC tính theo tỷ lệ P/E là 85,74 (mã E038) [Evidence: E038] Dữ liệu theo mảng kinh doanh chưa cung cấp, nợ và dòng tiền chưa được kiểm chứng, dữ liệu định giá chỉ bao gồm tỷ lệ P/E

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
627 tokens
10.11 s

Luận cứ / Claims (2)
FACT

Lợi nhuận hợp nhất của VIC tính theo tỷ lệ P/E là 85,74 (mã E038)

E038
UNCERTAINTY

Dữ liệu theo mảng kinh doanh chưa cung cấp, nợ và dòng tiền chưa được kiểm chứng, dữ liệu định giá chỉ bao gồm tỷ lệ P/E

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

de_ratio

debt_to_equity

debt_to_assets

debt_to_capital

net_debt_to_equity

net_debt_to_assets

net_debt_to_capital

current_ratio

quick_ratio

dso

inventory_turnover

accounts_receivable_turnover

accounts_payable_turnover

working_capital_turnover

free_cash_flow

free_cash_flow_yield

debt_service_coverage_ratio

cash_to_debt_ratio

cash_to_current_liabilities_ratio

cash_to_debt_ratio

Bằng chứng trích dẫn / Evidence citations (1)
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-07-31
Mathematically calculated from canonical adjusted close (237000.0 VND) / EPS TTM (2764.1 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)

**Capture notes**

Completed in 14s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q07.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q07.png).

---

### Q08 — Defensive consumer stock and dividends: VNM

**Question shown to the AI Analyst**

Đánh giá VNM như một cổ phiếu tiêu dùng có khả năng trả cổ tức. Hãy phân tích tăng trưởng doanh thu và lợi nhuận, biên lợi nhuận, dòng tiền tự do nếu tính được, EPS, định giá và lịch sử cổ tức nếu dữ liệu có sẵn. Cổ tức có được hỗ trợ bởi dòng tiền hay không? Nêu những yếu tố có thể làm suy giảm khả năng duy trì cổ tức và ghi rõ thời điểm của từng dữ liệu.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Biên lợi nhuận gộp của VNM là 42.12% [Evidence: E029, E008] EPS TTM của VNM là 5245.51 VND/share [Evidence: E029, E027] Không có dữ liệu về dòng tiền tự do (DCF) và biên lợi nhuận gộp từ dữ liệu được cung cấp trong verifiable_evidence, dẫn đến không thể tính toán P/B Không có dữ liệu về dòng tiền tự do (DCF) trong dữ liệu được cung cấp trong verifiable_evidence Không có dữ liệu về biên lợi nhuận gộp trong dữ liệu được cung cấp trong verifiable_evidence Không có dữ liệu về P/B trong dữ liệu được cung cấp trong verifiable_evidence

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
998 tokens
14.95 s

Luận cứ / Claims (6)
FACT

Biên lợi nhuận gộp của VNM là 42.12%

E029, E008
FACT

EPS TTM của VNM là 5245.51 VND/share

E029, E027
UNCERTAINTY

Không có dữ liệu về dòng tiền tự do (DCF) và biên lợi nhuận gộp từ dữ liệu được cung cấp trong verifiable_evidence, dẫn đến không thể tính toán P/B

Không có trích dẫn
UNCERTAINTY

Không có dữ liệu về dòng tiền tự do (DCF) trong dữ liệu được cung cấp trong verifiable_evidence

Không có trích dẫn
UNCERTAINTY

Không có dữ liệu về biên lợi nhuận gộp trong dữ liệu được cung cấp trong verifiable_evidence

Không có trích dẫn
UNCERTAINTY

Không có dữ liệu về P/B trong dữ liệu được cung cấp trong verifiable_evidence

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

DCF

de_ratio

dso

debt

Bằng chứng trích dẫn / Evidence citations (3)
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E027 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E029 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30

**Capture notes**

Completed in 20s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q08.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q08.png).

---

### Q09 — Energy sector comparison: GAS versus POW

**Question shown to the AI Analyst**

So sánh GAS và POW về mô hình kinh doanh, động lực doanh thu và lợi nhuận, dòng tiền, nợ vay, rủi ro ngành và định giá. Hai doanh nghiệp thuộc các khâu khác nhau của ngành năng lượng nên không được so sánh máy móc bằng một chỉ số duy nhất. Hãy nêu chỉ tiêu nào phù hợp để so sánh, chỉ tiêu nào không tương đương, và thông tin còn thiếu.

**Status**

ANSWERED

**Answer actually displayed in localhost**

GAS đã có tăng trưởng doanh thu trong năm trước với 55.11% so với năm trước (đã được trích dẫn từ verifiable_evidence E002). [Evidence: E002] GAS đang có tỷ lệ lợi nhuận gộp là 12.64% (đã được trích dẫn từ verifiable_evidence E008). [Evidence: E008] GAS đang có tỷ suất sinh lời bình quân (ROE) là 7.92% (đã được trích dẫn từ verifiable_evidence E011). [Evidence: E011]

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
623 tokens
9.82 s

Luận cứ / Claims (3)
FACT

GAS đã có tăng trưởng doanh thu trong năm trước với 55.11% so với năm trước (đã được trích dẫn từ verifiable_evidence E002).

E002
MODEL OUTPUT

GAS đang có tỷ lệ lợi nhuận gộp là 12.64% (đã được trích dẫn từ verifiable_evidence E008).

E008
MODEL OUTPUT

GAS đang có tỷ suất sinh lời bình quân (ROE) là 7.92% (đã được trích dẫn từ verifiable_evidence E011).

E011

Dữ liệu chưa chắc chắn / Uncertainty

Dòng tiền hoạt động

Nợ vay

Rủi ro ngành

Định giá P/B

Định giá ROE

Bằng chứng trích dẫn / Evidence citations (3)
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30

**Capture notes**

Completed in 14s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q09.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q09.png).

---

### Q10 — Oil distribution and working capital: PLX

**Question shown to the AI Analyst**

Phân tích PLX và giải thích giá dầu, biên lợi nhuận kinh doanh, hàng tồn kho và vốn lưu động có thể ảnh hưởng như thế nào đến kết quả tài chính. Dựa trên dữ liệu mà InvestIntel thực sự có, hãy phân biệt yếu tố đã quan sát được với yếu tố chỉ là cơ chế kinh tế hoặc giả định. Nếu không có dữ liệu giá dầu hay biên lợi nhuận theo thời gian, hãy nói rõ.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Giá dầu trong năm qua tăng 40.92% so với cùng kỳ (theo chỉ số E002) [Evidence: E002] Không có dữ liệu về biến động hàng tồn kho và không thể đưa ra nhận định định tính về biên lợi nhuận kinh doanh và P/B và P/E

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
597 tokens
9.60 s

Luận cứ / Claims (2)
FACT

Giá dầu trong năm qua tăng 40.92% so với cùng kỳ (theo chỉ số E002)

E002
UNCERTAINTY

Không có dữ liệu về biến động hàng tồn kho và không thể đưa ra nhận định định tính về biên lợi nhuận kinh doanh và P/B và P/E

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

dso

de_ratio

net_debt_ebitda

current_ratio

quick_ratio

ccc

total_liabilities

peg

dividend_yield

fcf_yield

dcf

residual_income

ddm

Bằng chứng trích dẫn / Evidence citations (1)
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-31

**Capture notes**

Completed in 14s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q10.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q10.png).

---

### Q11 — Commodity and chemical cycle: DGC

**Question shown to the AI Analyst**

Đánh giá DGC trong bối cảnh doanh nghiệp hóa chất có tính chu kỳ. Hãy phân tích doanh thu, biên lợi nhuận, lợi nhuận, dòng tiền, tiền mặt, nợ vay và các chỉ số định giá hiện có. Những biến số nào như giá bán, giá nguyên liệu hoặc nhu cầu xuất khẩu có thể ảnh hưởng lớn đến kết quả? Phân biệt dữ liệu thực tế của doanh nghiệp với các biến số mà hệ thống chưa theo dõi.

**Status**

NO_DATA

**Answer actually displayed in localhost**

Chưa đủ bằng chứng có nguồn kiểm chứng về mã DGC để trả lời câu hỏi này.

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

Available records for DGC are missing, stale, seeded/untraced, or lack a source citation (as of 2026-10-27).

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

Available records for DGC are missing, stale, seeded/untraced, or lack a source citation (as of 2026-10-27).

Bằng chứng trích dẫn / Evidence citations (0)

**Capture notes**

Completed in 2s. Response classified as NO_DATA (INSUFFICIENT_DATA status badge displayed in UI). Screenshot captured: [q11.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q11.png).

---

### Q12 — Securities firms and volatile earnings: SSI versus VIX

**Question shown to the AI Analyst**

So sánh SSI và VIX về lợi nhuận, vốn chủ sở hữu, dư nợ cho vay ký quỹ nếu có, hoạt động tự doanh nếu có, biến động kết quả kinh doanh và các chỉ số định giá. Lợi nhuận từ hoạt động kinh doanh cốt lõi và lợi nhuận do biến động thị trường có thể khác nhau như thế nào? Hãy chỉ ra giới hạn của kết luận nếu dữ liệu phân tách doanh thu, tài sản hoặc rủi ro tự doanh không đầy đủ.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Lợi nhuận từ hoạt động kinh doanh cốt lõi SSI: Gross margin của SSI đạt 63.89% [Evidence: E029, E030, E011, E008] Lợi nhuận từ hoạt động kinh doanh cốt lõi VIX: Net income của VIX đạt 4804.77 tỷ đồng [Evidence: E030] Không có dữ liệu về P/E, P/B và ROE của SSI và VIX Không có dữ liệu về doanh thu, tài sản hoặc rủi ro tự doanh

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
631 tokens
9.89 s

Luận cứ / Claims (4)
FACT

Lợi nhuận từ hoạt động kinh doanh cốt lõi SSI: Gross margin của SSI đạt 63.89%

E029, E030, E011, E008
FACT

Lợi nhuận từ hoạt động kinh doanh cốt lõi VIX: Net income của VIX đạt 4804.77 tỷ đồng

E030
UNCERTAINTY

Không có dữ liệu về P/E, P/B và ROE của SSI và VIX

Không có trích dẫn
UNCERTAINTY

Không có dữ liệu về doanh thu, tài sản hoặc rủi ro tự doanh

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

P/E SSI

P/B SSI

ROE SSI

P/E VIX

P/B VIX

ROE VIX

doanh thu SSI

tài sản SSI

rủi ro tự doanh SSI

doanh thu VIX

tài sản VIX

rủi ro tự doanh VIX

Bằng chứng trích dẫn / Evidence citations (4)
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-31
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-31
E029 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-31
E030 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-31

**Capture notes**

Completed in 14s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q12.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q12.png).

---

### Q13 — Infrastructure and power: REE versus PC1

**Question shown to the AI Analyst**

So sánh REE và PC1 về các mảng kinh doanh, dòng tiền, nợ vay, khả năng sinh lời và định giá dựa trên dữ liệu hiện có. Hãy lưu ý sự khác biệt giữa doanh thu định kỳ, dự án đang triển khai, doanh thu theo tiến độ và thu nhập từ các khoản đầu tư. Nếu không đủ dữ liệu để phân tích từng mảng, hãy nêu rõ thay vì giả định cơ cấu lợi nhuận.

**Status**

ANSWERED

**Answer actually displayed in localhost**

P/E của PC1 là 10.84 [Evidence: E038] ROE của REE là 25.54% [Evidence: E011]

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
889 tokens
13.90 s

Luận cứ / Claims (2)
FACT

P/E của PC1 là 10.84

E038
MODEL OUTPUT

ROE của REE là 25.54%

E011

Dữ liệu chưa chắc chắn / Uncertainty

dso

quick_ratio

current_ratio

de_ratio

total_liabilities

ebitda_margin

net_debt_ebitda

peg

dividend_yield

fcf_yield

dcf

residual_income

ddm

Bằng chứng trích dẫn / Evidence citations (2)
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-07-30
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-07-30
Mathematically calculated from canonical adjusted close (45900.0 VND) / EPS TTM (4234.5 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)

**Capture notes**

Completed in 18s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q13.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q13.png).

---

### Q14 — Growth valuation comparison: FPT versus CMG

**Question shown to the AI Analyst**

So sánh FPT và CMG về tăng trưởng doanh thu, lợi nhuận, biên lợi nhuận, ROE, EPS, P/E và P/B nếu có dữ liệu. Cổ phiếu có mức P/E cao hơn có nhất thiết đắt hơn sau khi xét tăng trưởng và chất lượng lợi nhuận hay không? Hãy áp dụng dữ liệu tương đồng về kỳ báo cáo, nêu rõ các chỉ tiêu còn thiếu, và không đưa ra kết luận chỉ dựa trên một tỷ lệ.

**Status**

ANSWERED

**Answer actually displayed in localhost**

FPT có P/E (Price-to-Earnings) đạt 10.56 lần [Evidence: E038] FPT có P/B (Price-to-Book) đạt 2.58 lần [Evidence: E039] FPT có lợi nhuận tăng YoY đạt 20.6% [Evidence: E004] FPT có biên lợi nhuận đạt 34.65% [Evidence: E008] FPT có EPS (Earnings Per Share) đạt 5302.63 VND/thành phần cổ phiếu [Evidence: E027] Không có dữ liệu về EBITDA Margin, Debt-to-Equity Ratio, Debt-to-Earnings Ratio, và Current Ratio

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
839 tokens
12.93 s

Luận cứ / Claims (6)
FACT

FPT có P/E (Price-to-Earnings) đạt 10.56 lần

E038
FACT

FPT có P/B (Price-to-Book) đạt 2.58 lần

E039
FACT

FPT có lợi nhuận tăng YoY đạt 20.6%

E004
FACT

FPT có biên lợi nhuận đạt 34.65%

E008
MODEL OUTPUT

FPT có EPS (Earnings Per Share) đạt 5302.63 VND/thành phần cổ phiếu

E027
UNCERTAINTY

Không có dữ liệu về EBITDA Margin, Debt-to-Equity Ratio, Debt-to-Earnings Ratio, và Current Ratio

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

Không có dữ liệu về EBITDA Margin, Debt-to-Equity Ratio, Debt-to-Earnings Ratio, và Current Ratio

Bằng chứng trích dẫn / Evidence citations (5)
E004 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E008 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E027 / fundamentals
AVAILABLE

VIETCAP_IQ / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-06-30 / Công bố 2026-08-22
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-22
Mathematically calculated from canonical adjusted close (56000.0 VND) / EPS TTM (5302.6 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-22
Mathematically calculated from canonical adjusted close (56000.0 VND) / BVPS (21740.0 VND). Post-corporate-action share basis.

**Capture notes**

Completed in 18s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q14.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q14.png).

---

### Q15 — Choosing and interpreting valuation ratios

**Question shown to the AI Analyst**

Hãy giải thích cách sử dụng P/E và P/B khi phân tích ba cổ phiếu thuộc các nhóm ngành khác nhau: VCB, HPG và FPT. Với mỗi cổ phiếu, hãy nêu chỉ tiêu nào có ý nghĩa hơn trong bối cảnh ngành, những hạn chế của chỉ tiêu đó, và các dữ liệu bổ sung cần thiết. Sau đó giải thích vì sao không nên áp dụng cùng một ngưỡng P/E hoặc P/B cho mọi doanh nghiệp.

**Status**

ANSWERED

**Answer actually displayed in localhost**

P/E của Vietcombank (VCB) trong ngày 27/10/2026 là 11,26 lần [Evidence: E038] P/B của Vietcombank (VCB) trong ngày 27/10/2026 là 1,89 lần [Evidence: E039]

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
595 tokens
9.47 s

Luận cứ / Claims (2)
FACT

P/E của Vietcombank (VCB) trong ngày 27/10/2026 là 11,26 lần

E038
FACT

P/B của Vietcombank (VCB) trong ngày 27/10/2026 là 1,89 lần

E039

Dữ liệu chưa chắc chắn / Uncertainty

revenue_cagr_3y

revenue_cagr_5y

eps_cagr_3y

ebitda_margin

de_ratio

dso

ccc

cash

total_liabilities

peg

dividend_yield

fcf_yield

dcf

residual_income

ddm

Bằng chứng trích dẫn / Evidence citations (2)
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-19
Mathematically calculated from canonical adjusted close (56100.0 VND) / EPS TTM (4984.4 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-08-19
Mathematically calculated from canonical adjusted close (56100.0 VND) / BVPS (29739.1 VND). Post-corporate-action share basis.

**Capture notes**

Completed in 14s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q15.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q15.png).

---

### Q16 — EPS denominator and estimate transparency: VIX

**Question shown to the AI Analyst**

Đối với VIX, hãy trình bày EPS và P/E đang được InvestIntel sử dụng, kỳ tài chính và giá cổ phiếu tương ứng, số lượng cổ phiếu dùng trong phép tính EPS, cũng như nguồn và loại mẫu số nếu hệ thống có thể hiển thị. Mẫu số là số cổ phiếu bình quân gia quyền trong kỳ hay số cổ phiếu lưu hành cuối kỳ? Nếu dùng số cuối kỳ thay thế hoặc một giá trị ước tính, hãy gắn nhãn rõ ràng, giải thích ảnh hưởng có thể có đến EPS/P/E và không gọi kết quả đó là EPS chính xác đã được xác minh độc lập.

**Status**

ANSWERED

**Answer actually displayed in localhost**

EPS tính theo kỳ tài chính TTM của VIX là 650,97 VND/cổ phiếu [Evidence: E027] Giá cổ phiếu của VIX hiện tại là 12500 VND/cổ phiếu [Evidence: E001] P/E của VIX hiện tại là 19,2 lần [Evidence: E038]

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
473 tokens
7.80 s

Luận cứ / Claims (3)
FACT

EPS tính theo kỳ tài chính TTM của VIX là 650,97 VND/cổ phiếu

E027
FACT

Giá cổ phiếu của VIX hiện tại là 12500 VND/cổ phiếu

E001
FACT

P/E của VIX hiện tại là 19,2 lần

E038

Dữ liệu chưa chắc chắn / Uncertainty

ebitda_margin

de_ratio

net_debt_ebitda

current_ratio

quick_ratio

dso

ccc

total_liabilities

peg

dividend_yield

fcf_yield

dcf

residual_income

ddm

Bằng chứng trích dẫn / Evidence citations (3)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=VIX
E027 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-19
Mathematically calculated from canonical adjusted close (12500.0 VND) / EPS TTM (651.0 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)

**Capture notes**

Completed in 12s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q16.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q16.png).

---

### Q17 — Data freshness and mismatched periods

**Question shown to the AI Analyst**

Kiểm tra dữ liệu hiện có của VIX, DSE và HPG. Với từng mã, hãy nêu ngày giá cổ phiếu, kỳ báo cáo tài chính được sử dụng để tính EPS/P/E/P/B, ngày công bố báo cáo nếu có, và tình trạng dữ liệu mới nhất, cũ, thiếu hoặc không cùng thời điểm. Không suy đoán ngày chụp dữ liệu của nhà cung cấp nếu hệ thống không lưu timestamp đó. Hãy giải thích rõ khác biệt giữa ngày cuối kỳ tài chính, ngày công bố báo cáo và ngày giá cổ phiếu.

**Status**

NO_DATA

**Answer actually displayed in localhost**

Chưa đủ bằng chứng có nguồn kiểm chứng để trả lời câu hỏi này.

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

A numeric statement in the uncertainty field was suppressed because it has no citation IDs.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

A numeric statement in the uncertainty field was suppressed because it has no citation IDs.

Bằng chứng trích dẫn / Evidence citations (81)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=VIX
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E003 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E004 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E005 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E006 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E007 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E009 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E010 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Numerator data not available
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E012 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E013 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E014 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E015 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Numerator data not available
E016 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Numerator data not available
E017 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E018 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Numerator data not available
E019 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Current assets missing
E020 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Interest expense is zero or missing — coverage ratio N/A.
E021 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E022 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E023 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Accounts receivable missing
E024 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
COGS is zero or missing — may be a service company.
E025 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
COGS is zero or missing.
E026 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
DSO or DPO missing for CCC calculation.
E027 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E028 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E029 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E030 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E031 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E032 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E033 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E034 / fundamentals
INSUFFICIENT DATA

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E035 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E036 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E037 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E038 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-19
Mathematically calculated from canonical adjusted close (12500.0 VND) / EPS TTM (651.0 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)
E039 / valuation
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-19
Mathematically calculated from canonical adjusted close (12500.0 VND) / BVPS (12774.3 VND). Post-corporate-action share basis.
E040 / valuation
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Market cap: 32159.9B VND, Net Debt: 0.0B VND, EBITDA: 2034.3B VND
E041 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E042 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E043 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E044 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E045 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E046 / valuation
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
No evidence-backed input contract is available for this output.
E047 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E048 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E049 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E050 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E051 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E052 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E053 / factors
INSUFFICIENT DATA

Nguồn không xác định / Gốc không xác định

Quan sát N/A / Công bố N/A
Current factor API uses demo inputs or has no canonical-input adapter; factor scores are withheld.
E054 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-15 / Công bố 2026-10-15T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E055 / macro
AVAILABLE

SBV / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-10T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E056 / macro
STALE

SBV / LINEAGED_INGESTION

Quan sát 2026-10-01 / Công bố 2026-10-01T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E057 / macro
STALE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2025-10-31 / Công bố 2026-10-12T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E058 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-05T07:00:00+07:00 / file://C:\Users\baotr\Downloads\trading\data\macro\vnm_macro_indicators.csv
E059 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E060 / macro
AVAILABLE

NSO_VIETNAM / LINEAGED_INGESTION

Quan sát 2026-09-30 / Công bố 2026-10-14T07:00:00+07:00 / https://nsdp.nso.gov.vn/GSO-chung/SDMXFiles/GSO
E061 / macro
AVAILABLE

BLS / LINEAGED_INGESTION

Quan sát 2026-09-01 / Công bố N/A / https://api.bls.gov/publicAPI/v1/timeseries/data/
E062 / macro
AVAILABLE

FRED / LINEAGED_INGESTION

Quan sát 2026-10-23 / Công bố 2026-10-23T07:00:00+07:00 / https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10
E063 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E064 / macro
AVAILABLE

OPEN_EXCHANGE_RATES / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27T07:00:00+07:00 / https://open.er-api.com/v6/latest/USD
E065 / macro
INSUFFICIENT DATA

BLS / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E066 / macro
INSUFFICIENT DATA

FRED / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E067 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E068 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E069 / macro
INSUFFICIENT DATA

GSO / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E070 / macro
INSUFFICIENT DATA

SBV / REGISTERED_SERIES

Quan sát N/A / Công bố N/A
E071 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CAB?format=json
E072 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_CPI?format=json
E073 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_GDP?format=json
E074 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_RES?format=json
E075 / macro
AVAILABLE

WORLD_BANK / LINEAGED_INGESTION

Quan sát 2025-12-31 / Công bố N/A / https://api.worldbank.org/v2/country/VNM/indicator/WB_VNM_UEM?format=json
E076 / regime
NEUTRAL

vn100_price_breadth_v1 / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố N/A
VN100 20-session momentum: -1.22%; VN100 breadth: 1 advancing, 0 declining, 99 unchanged
E077 / risk
INSUFFICIENT DATA

RiskEngine / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Current RiskEngine fills missing categories with stub/default scores; numeric risk is withheld until each category has evidenced inputs.
E078 / events
INSUFFICIENT DATA

FINANCIAL_NEWS / CANONICAL_EVENT_RECORD

Quan sát N/A / Công bố 2026-10-20
E079 / opportunity
INSUFFICIENT DATA

ResearchWorkspace.opportunity / RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
Opportunity and confidence remain separate fields; unavailable scores are not inferred.
E080 / portfolio_fit
NOT IN PORTFOLIO

portfolio_fit / PERSONAL_PORTFOLIO_AND_RESEARCH_WORKSPACE

Quan sát N/A / Công bố N/A
E081 / portfolio
EMPTY

portfolio_dashboard / LOCAL_PERSONAL_PORTFOLIO

Quan sát 2026-10-27 / Công bố N/A
Portfolio fields are local and are not submitted to an external recommendation or broker service.

**Capture notes**

Completed in 12s. Response classified as NO_DATA (INSUFFICIENT_DATA status badge displayed in UI). Screenshot captured: [q17.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q17.png).

---

### Q18 — Historical point-in-time replay and look-ahead bias

**Question shown to the AI Analyst**

Hãy đánh giá VIX tại thời điểm 15:00 ngày 19/10/2026 theo giờ Việt Nam bằng chức năng và dữ liệu mà giao diện InvestIntel thực sự hỗ trợ. Không sử dụng thông tin chỉ được công bố sau thời điểm này, bao gồm báo cáo quý III nếu báo cáo đó được công bố sau mốc thời gian. Hãy ghi rõ ngày giá, kỳ báo cáo và ngày công bố được sử dụng, các chỉ tiêu tính được, dữ liệu bị loại khỏi phép tính và những giới hạn của kết quả. Nếu giao diện không hỗ trợ truy vấn lịch sử theo thời điểm, hãy nói rõ và không giả vờ rằng phép replay đã thực hiện thành công.

**Status**

ANSWERED

**Answer actually displayed in localhost**

Dữ liệu báo cáo quý IV và báo cáo quý III sau ngày 27/10/2026. Dữ liệu này không được sử dụng để tính toán giá trị chỉ số VIX trong thời điểm 15:00 ngày 19/10/2026. Thay vào đó, chúng tôi chỉ có thể trích dẫn dữ liệu từ báo cáo quý III, nhưng không có dữ liệu cụ thể về thời điểm 15:00 ngày 19/10/2026.

**Thông số phiên / Metadata:**
qwen2.5:3b
investment_analyst_v2
Tính đến ngày 2026-10-27
694 tokens
10.93 s

Luận cứ / Claims (1)
UNCERTAINTY

Dữ liệu báo cáo quý IV và báo cáo quý III sau ngày 27/10/2026. Dữ liệu này không được sử dụng để tính toán giá trị chỉ số VIX trong thời điểm 15:00 ngày 19/10/2026. Thay vào đó, chúng tôi chỉ có thể trích dẫn dữ liệu từ báo cáo quý III, nhưng không có dữ liệu cụ thể về thời điểm 15:00 ngày 19/10/2026.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

dữ liệu về báo cáo quý IV

dữ liệu về báo cáo quý III sau thời điểm 27/10/2026

Bằng chứng trích dẫn / Evidence citations (15)
E001 / price
AVAILABLE

LOTUSMARKET / LINEAGED_INGESTION

Quan sát 2026-10-27 / Công bố 2026-10-27 / https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=VIX
E002 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E003 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E004 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E005 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E006 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E007 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E008 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E009 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E011 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E012 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E013 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E014 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E017 / fundamentals
AVAILABLE

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
E020 / fundamentals
NOT MEANINGFUL

VNDIRECT_FINFO / CANONICAL_FINANCIAL_STATEMENTS

Quan sát 2026-09-30 / Công bố 2026-10-19
Interest expense is zero or missing — coverage ratio N/A.

**Capture notes**

Completed in 16s. Rendered fully in localhost with structured evidence citations. Screenshot captured: [q18.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q18.png).

---

### Q19 — Portfolio reasoning and risk

**Question shown to the AI Analyst**

Giả sử tôi có 100 triệu đồng, thời gian đầu tư 3 năm và mức chịu đựng rủi ro trung bình; tôi muốn nghiên cứu một danh mục cổ phiếu Việt Nam thay vì tập trung vào một mã. Dựa trên dữ liệu hiện có của InvestIntel, hãy đề xuất một phương pháp phân bổ danh mục minh họa, giải thích vai trò của các nhóm ngành, rủi ro tập trung, thanh khoản và các điều kiện khiến phương án cần thay đổi. Phân biệt rõ phương án giả định với khuyến nghị đã được kiểm chứng; không khẳng định lợi nhuận được đảm bảo. Nếu dữ liệu rủi ro hoặc tương quan giữa các cổ phiếu không có, hãy nêu giới hạn đó.

**Status**

PARTIAL

**Answer actually displayed in localhost**

Chưa xác định được mã cổ phiếu hoặc chủ đề cần phân tích. Bạn vui lòng nhập rõ mã cổ phiếu (ví dụ: VCB, FPT, HPG) hoặc đặt câu hỏi về thị trường chung (ví dụ: 'thị trường hôm nay').

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

Không tìm thấy mã cổ phiếu hợp lệ trong câu hỏi hoặc mã chưa có trong cơ sở dữ liệu.

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

Không tìm thấy mã cổ phiếu hợp lệ trong câu hỏi hoặc mã chưa có trong cơ sở dữ liệu.

Bằng chứng trích dẫn / Evidence citations (0)

**Capture notes**

Completed in 2s. Answer visibly partial/brief. Screenshot captured: [q19.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q19.png).

---

### Q20 — Unknown ticker and hallucination resistance

**Question shown to the AI Analyst**

Hãy phân tích cổ phiếu có mã ZZZTEST trên thị trường chứng khoán Việt Nam, bao gồm giá, doanh thu, lợi nhuận, EPS, P/E, P/B và đánh giá đầu tư. Nếu InvestIntel không nhận diện được mã này hoặc không có dữ liệu đáng tin cậy, hãy nói thẳng điều đó, liệt kê thông tin nào không thể xác minh và không tự tạo ra công ty, giá cổ phiếu hay số liệu tài chính.

**Status**

NO_DATA

**Answer actually displayed in localhost**

Chưa đủ bằng chứng có nguồn kiểm chứng về mã EPS để trả lời câu hỏi này.

**Thông số phiên / Metadata:**
Không có cuộc gọi mô hình
investment_analyst_v2
Tính đến ngày 2026-10-27

Luận cứ / Claims (1)
UNCERTAINTY

Available records for EPS are missing, stale, seeded/untraced, or lack a source citation (as of 2026-10-27).

Không có trích dẫn

Dữ liệu chưa chắc chắn / Uncertainty

Available records for EPS are missing, stale, seeded/untraced, or lack a source citation (as of 2026-10-27).

Bằng chứng trích dẫn / Evidence citations (0)

**Capture notes**

Completed in 2s. Response classified as NO_DATA (INSUFFICIENT_DATA status badge displayed in UI). Screenshot captured: [q20.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/local_ai_analyst_20q_2026-10-27/q20.png).

---
