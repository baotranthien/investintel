# INVESTINTEL — 20 ORIGINAL INDEPENDENT AI ANALYST QUESTIONS REPORT
**Execution Timestamp:** 2026-11-02 | **Model:** `qwen3.5:9b-q4_K_M` (Local Ollama on NVIDIA RTX 3050 Laptop GPU)
**Strict Isolation:** Zero mutation of portfolio or watchlist data. All queries run sequentially.

## 1. Summary Statistics
- Total Questions Evaluated: 20
- Successful Responses: 20/20 (100%)
- Total Citations Grounded: 74
- Average Response Time: 64.88s

## 2. Question-by-Question Evaluation & Full Responses

### Question 1 — [FPT] `Phân tích cơ cấu tăng trưởng doanh thu và lợi nhuận của FPT dựa trên số liệu báo cáo tài chính mới nhất?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 117.216s
- **Citations (3):**
  - `[E002]`  *(Source: VNDIRECT_FINFO)*
  - `[E003]`  *(Source: VNDIRECT_FINFO)*
  - `[E008]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Doanh thu FPT năm nay tăng 1,45%, dựa trên bằng chứng E002. [Evidence: E002] Lợi nhuận ròng của FPT tăng trưởng mạnh đến 27,27% tương ứng bằng chứng E003. [Evidence: E003] Biên lợi nhuận gộp đạt mức 34,65% như số liệu ghi nhận E008. [Evidence: E008] Dữ liệu về hệ số định giá PEG vẫn còn thiếu trong báo cáo hiện tại.
```

---

### Question 2 — [VCB] `Chất lượng tài sản và tỷ lệ bao phủ nợ xấu của Ngân hàng Vietcombank (VCB) hiện nay ra sao?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 54.397s
- **Citations (2):**
  - `[E093]`  *(Source: BCTC_SOAT_XET_Q2_2026)*
  - `[E094]`  *(Source: BCTC_SOAT_XET_Q2_2026)*

**Full Model Answer:**
```text
Tỷ lệ bao phủ nợ xấu VCB đạt 212,0% (ID: E094). [Evidence: E094] Tỷ lệ nợ xấu NPL của VCB ở mức 1,14% (ID: E093). [Evidence: E093]
```

---

### Question 3 — [MBB] `Đánh giá biên lãi thuần (NIM) và tỷ lệ tiền gửi không kỳ hạn (CASA) của MBB?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 58.959s
- **Citations (2):**
  - `[E090]`  *(Source: BCTC_SOAT_XET_Q2_2026)*
  - `[E091]`  *(Source: BCTC_SOAT_XET_Q2_2026)*

**Full Model Answer:**
```text
Biên lãi ròng MBB quý II/2026 là 4,62%. [Evidence: E090] Tỷ lệ CASA của MBB tại cùng kỳ là 39,5%. [Evidence: E091]
```

---

### Question 4 — [MWG] `Tình hình tài chính, biên lợi nhuận gộp và sức khỏe dòng tiền của Thế Giới Di Động (MWG)?`
- **Result:** PASS | **Answer Status:** `PARTIAL` | **Duration:** 95.623s
- **Citations (1):**
  - `[E008]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Biên lợi nhuận gộp của Thế Giới Di Động là 20,66% (E008). [Evidence: E008]
```

---

### Question 5 — [HPG] `Chi phí vốn, hệ số đòn bẩy tài chính D/E và tiến độ mở rộng của Tập đoàn Hòa Phát (HPG)?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 56.732s
- **Citations (2):**
  - `[E002]`  *(Source: VNDIRECT_FINFO)*
  - `[E015]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Hệ số đòn bẩy D/E của HPG là 0,7. [Evidence: E015] Doanh thu HPG tăng 35,9% so với cùng kỳ. [Evidence: E002] Tiến độ mở rộng và chi phí vốn cụ thể chưa được công bố trong dữ liệu hiện có.
```

---

### Question 6 — [BMP] `Định giá P/E và tỷ suất sinh lời ROE của Nhựa Bình Minh (BMP) so với trung vị ngành vật liệu?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 85.457s
- **Citations (2):**
  - `[E012]`  *(Source: VNDIRECT_FINFO)*
  - `[E046]`  *(Source: LOTUSMARKET)*

**Full Model Answer:**
```text
Hệ số định giá P/E của Nhựa Bình Minh (BMP) là khoảng 8,99 lần. [Evidence: E046] Tỷ suất sinh lời ROE của công ty này đạt mức 41,57%. [Evidence: E012] Không có dữ liệu trung vị ngành vật liệu để so sánh trực tiếp.
```

---

### Question 7 — [PLX] `Mối tương quan giữa doanh thu PLX và biến động giá dầu thế giới (Brent/WTI)?`
- **Result:** PASS | **Answer Status:** `PARTIAL` | **Duration:** 92.405s
- **Citations (1):**
  - `[E090]`  *(Source: INVESTINTEL_PYTHON_CALCULATOR)*

**Full Model Answer:**
```text
Hệ số tương quan Pearson giữa giá PLX và hàng hóa (bao gồm dầu) được tính là -0.36. [Evidence: E090]
```

---

### Question 8 — [VNINDEX] `Đánh giá trạng thái chế độ thị trường (Market Regime) và độ rộng thị trường chứng khoán Việt Nam?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 93.402s
- **Citations (1):**
  - `[E001]`  *(Source: LOTUSMARKET)*

**Full Model Answer:**
```text
Chỉ số VN100 đang giao dịch tại mức 1761,77 điểm. [Evidence: E001] Dữ liệu về EPS và lợi nhuận ròng hiện chưa được xác minh.
```

---

### Question 9 — [FPT] `Biên lợi nhuận ròng và hiệu quả sử dụng vốn ROIC của FPT trong các kỳ gần nhất?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 62.391s
- **Citations (1):**
  - `[E011]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Biên lợi nhuận ròng của FPT là 15,68%. [Evidence: E011] Chưa có dữ liệu ROIC trong bằng chứng hiện tại.
```

---

### Question 10 — [VCB] `Quy mô vốn chủ sở hữu và định giá P/B của Vietcombank (VCB) hiện tại?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 69.053s
- **Citations (1):**
  - `[E047]`  *(Source: LOTUSMARKET)*

**Full Model Answer:**
```text
Biên độ P/B của VCB hiện tại đạt 1,89 lần. [Evidence: E047] Vốn chủ sở hữu thực tế chưa được cung cấp trong bằng chứng.
```

---

### Question 11 — [BMP] `Mô hình định giá DCF và kịch bản cơ sở (Base Case) đối với cổ phiếu BMP đưa ra kết quả gì?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 62.89s
- **Citations (2):**
  - `[E046]`  *(Source: LOTUSMARKET)*
  - `[E047]`  *(Source: LOTUSMARKET)*

**Full Model Answer:**
```text
Hệ số P/E ước tính của BMP là 8.99 lần. [Evidence: E046] Biên P/B hiện tại ghi nhận ở mức 3.55 lần. [Evidence: E047] Kết quả DCF chưa khả dụng trong danh sách bằng chứng.
```

---

### Question 12 — [VN100] `Những cổ phiếu nào trong rổ VN100 đang có điểm cơ hội (Opportunity Score) cao nhất hiện nay?`
- **Result:** PASS | **Answer Status:** `PARTIAL_DATA_ONLY` | **Duration:** 49.302s
- **Citations (14):**
  - `[E001]`  *(Source: LOTUSMARKET)*
  - `[E038]`  *(Source: SBV)*
  - `[E041]`  *(Source: NSO_VIETNAM)*
  - `[E042]`  *(Source: NSO_VIETNAM)*
  - `[E043]`  *(Source: NSO_VIETNAM)*
  - `[E044]`  *(Source: BLS)*
  - `[E045]`  *(Source: FRED)*
  - `[E047]`  *(Source: OPEN_EXCHANGE_RATES)*
  - `[E054]`  *(Source: WORLD_BANK)*
  - `[E055]`  *(Source: WORLD_BANK)*
  - `[E056]`  *(Source: WORLD_BANK)*
  - `[E057]`  *(Source: WORLD_BANK)*
  - `[E058]`  *(Source: WORLD_BANK)*
  - `[E059]`  *(Source: vn100_price_breadth_v1)*

**Full Model Answer:**
```text
Mô hình AI chưa trích xuất được kết luận văn bản đủ độ tin cậy để vượt qua lớp kiểm định chống sai lệch (Hallucination Guard). Hệ thống cung cấp bảng số liệu tài chính thực tế đã được đối chiếu từ cơ sở dữ liệu kiểm chứng cùng các chỉ số được tính toán trực tiếp:
```

---

### Question 13 — [BRENT] `Biến động của giá dầu Brent và chỉ số hàng hóa vĩ mô ảnh hưởng thế nào đến các doanh nghiệp năng lượng?`
- **Result:** PASS | **Answer Status:** `PARTIAL_DATA_ONLY` | **Duration:** 62.05s
- **Citations (15):**
  - `[E001]`  *(Source: LOTUSMARKET)*
  - `[E038]`  *(Source: SBV)*
  - `[E041]`  *(Source: NSO_VIETNAM)*
  - `[E042]`  *(Source: NSO_VIETNAM)*
  - `[E043]`  *(Source: NSO_VIETNAM)*
  - `[E044]`  *(Source: BLS)*
  - `[E045]`  *(Source: FRED)*
  - `[E047]`  *(Source: OPEN_EXCHANGE_RATES)*
  - `[E054]`  *(Source: WORLD_BANK)*
  - `[E055]`  *(Source: WORLD_BANK)*
  - `[E056]`  *(Source: WORLD_BANK)*
  - `[E057]`  *(Source: WORLD_BANK)*
  - `[E058]`  *(Source: WORLD_BANK)*
  - `[E059]`  *(Source: vn100_price_breadth_v1)*
  - `[E064]`  *(Source: PUBLIC_COMMODITY_FEED)*

**Full Model Answer:**
```text
Mô hình AI chưa trích xuất được kết luận văn bản đủ độ tin cậy để vượt qua lớp kiểm định chống sai lệch (Hallucination Guard). Hệ thống cung cấp bảng số liệu tài chính thực tế đã được đối chiếu từ cơ sở dữ liệu kiểm chứng cùng các chỉ số được tính toán trực tiếp:
```

---

### Question 14 — [MWG] `Chất lượng dòng tiền hoạt động kinh doanh (CFO) so với lợi nhuận ròng của MWG?`
- **Result:** PASS | **Answer Status:** `PARTIAL` | **Duration:** 70.278s
- **Citations (1):**
  - `[E021]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Tỷ lệ CFO trên lợi nhuận ròng (CFO to Net Income) của MWG là 0,24 lần. [Evidence: E021]
```

---

### Question 15 — [BMP] `Chính sách chi trả cổ tức và tỷ suất cổ tức tiền mặt (Dividend Yield) của BMP?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 58.992s
- **Citations (1):**
  - `[E032]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Không có thông tin về chính sách phân红的 hiện hữu của BMP. Chưa xác định được tỷ suất cổ tức tiền mặt (dividend yield). Mã chứng khoán BMP đang trong trạng thái đăng ký hoạt động. [Evidence: E032]
```

---

### Question 16 — [HPG] `Tỷ lệ nợ ròng trên EBITDA và khả năng chi trả lãi vay của HPG?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 37.866s
- **Citations (1):**
  - `[E016]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Tỷ lệ này được trích từ nguồn VNDIRECT_FINFO (E016). [Evidence: E016]
```

---

### Question 17 — [BMP] `Định giá P/E và P/B trung vị của nhóm cổ phiếu ngành vật liệu (Materials Peers) tại Việt Nam?`
- **Result:** PASS | **Answer Status:** `AVAILABLE` | **Duration:** 43.414s
- **Citations (2):**
  - `[E046]`  *(Source: LOTUSMARKET)*
  - `[E047]`  *(Source: LOTUSMARKET)*

**Full Model Answer:**
```text
Mã BMP ghi nhận P/E là 8,99 lần dựa trên dữ liệu ước tính. [Evidence: E046] P/B của mã này đạt mức 3,55 lần tính toán chính xác. [Evidence: E047]
```

---

### Question 18 — [MWG] `Chu kỳ chuyển đổi tiền mặt (CCC) và hiệu quả quản lý hàng tồn kho của MWG?`
- **Result:** PASS | **Answer Status:** `PARTIAL_DATA_ONLY` | **Duration:** 57.36s
- **Citations (20):**
  - `[E001]`  *(Source: LOTUSMARKET)*
  - `[E002]`  *(Source: VNDIRECT_FINFO)*
  - `[E003]`  *(Source: VNDIRECT_FINFO)*
  - `[E004]`  *(Source: VNDIRECT_FINFO)*
  - `[E008]`  *(Source: VNDIRECT_FINFO)*
  - `[E009]`  *(Source: VNDIRECT_FINFO)*
  - `[E010]`  *(Source: VNDIRECT_FINFO)*
  - `[E011]`  *(Source: VNDIRECT_FINFO)*
  - `[E012]`  *(Source: VNDIRECT_FINFO)*
  - `[E013]`  *(Source: VNDIRECT_FINFO)*
  - `[E014]`  *(Source: VNDIRECT_FINFO)*
  - `[E015]`  *(Source: VNDIRECT_FINFO)*
  - `[E016]`  *(Source: VNDIRECT_FINFO)*
  - `[E017]`  *(Source: VNDIRECT_FINFO)*
  - `[E018]`  *(Source: VNDIRECT_FINFO)*
  - `[E019]`  *(Source: VNDIRECT_FINFO)*
  - `[E020]`  *(Source: VNDIRECT_FINFO)*
  - `[E021]`  *(Source: VNDIRECT_FINFO)*
  - `[E022]`  *(Source: VNDIRECT_FINFO)*
  - `[E023]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Mô hình AI chưa trích xuất được kết luận văn bản đủ độ tin cậy để vượt qua lớp kiểm định chống sai lệch (Hallucination Guard). Hệ thống cung cấp bảng số liệu tài chính thực tế đã được đối chiếu từ cơ sở dữ liệu kiểm chứng cùng các chỉ số được tính toán trực tiếp:
```

---

### Question 19 — [ALL] `Các cổ phiếu thỏa mãn tiêu chí định giá rẻ P/E dưới 15 và sinh lời ROE trên 15%?`
- **Result:** PASS | **Answer Status:** `INSUFFICIENT_DATA` | **Duration:** 2.292s
- **Citations (0):**

**Full Model Answer:**
```text
Chưa xác định được mã cổ phiếu hoặc chủ đề cần phân tích. Bạn vui lòng nhập rõ mã cổ phiếu (ví dụ: VCB, FPT, HPG) hoặc đặt câu hỏi về thị trường chung (ví dụ: 'thị trường hôm nay').
```

---

### Question 20 — [FPT] `Tóm tắt luận điểm đầu tư cốt lõi và các rủi ro chính đối với cổ phiếu FPT?`
- **Result:** PASS | **Answer Status:** `PARTIAL` | **Duration:** 67.552s
- **Citations (2):**
  - `[E003]`  *(Source: VNDIRECT_FINFO)*
  - `[E005]`  *(Source: VNDIRECT_FINFO)*

**Full Model Answer:**
```text
Lợi nhuận ròng của FPT đã tăng 27,27% so với cùng kỳ trước đây. [Evidence: E003] Doanh thu công ty này duy trì mức tăng trưởng hợp lý 3 năm qua đạt 13,15%. (Mức tăng trưởng doanh thu của FPT) [Evidence: E005] Dữ liệu về chỉ số PEG và dòng tiền tự do hiện chưa được xác minh.
```

---
