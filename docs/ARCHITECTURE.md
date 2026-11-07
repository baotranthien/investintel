# INVESTINTEL — HỆ THỐNG KIẾN TRÚC TOÀN DIỆN
**SYSTEM ARCHITECTURE & DESIGN SPECIFICATION**

* **Phiên bản:** v2.5 (Local-First Deterministic Engine)
* **Cập nhật gần nhất:** 03/11/2026
* **Triết lý kiến trúc:** *“Quant engine calculates. AI explains with verifiable evidence.”*

---

## 1. TỔNG QUAN KIẾN TRÚC (HIGH-LEVEL OVERVIEW)

InvestIntel là nền tảng nghiên cứu và phân tích đầu tư vốn cổ phần thể chế, vận hành theo mô hình **Local-First / Zero External Leak**. Hệ thống gồm 3 tầng kiến trúc chính:

```
+---------------------------------------------------------------------------------------+
|                                    TRÌNH DUYỆT WEB                                    |
|                                                                                       |
|   Next.js 16 (App Router) + React 19 + Apple Minimalist Daylight Theme                |
|   + Three.js 3D Spatial Telemetry (Single Canvas Host: Globe / Landscape / Neural / Reactor)|
+-------------------------------------------+-------------------------------------------+
                                            |
                         HTTP / REST API & SSE Event Stream
                                            |
+-------------------------------------------v-------------------------------------------+
|                               FASTAPI BACKEND GATEWAY                                 |
|                                                                                       |
|   - Point-in-Time Financial Repository (PIT Filtering)                                |
|   - Deterministic Valuation Ensemble (DCF, Relative P/E, P/B, Residual Income)        |
|   - Stock Screener Engine & Factor Scoring                                            |
|   - Risk & Horizon Engine (10 Categories, Macro Sensitivity)                          |
|   - Local AI Analyst Agent (Prompt Registry, Structured Tool Grounding, SSE Stream)   |
+---------------------+-----------------------------------+-----------------------------+
                      |                                   |
                      v                                   v
+---------------------+-------------+   +-----------------+-----------------------------+
|    CANONICAL SQLITE DATABASE      |   |        LOCAL AI REASONING CORE                |
|                                   |   |                                               |
|   data/trading.db                 |   |   Ollama Runtime (`http://127.0.0.1:11434`)   |
|   - 104 Assets (VN100/VN30)       |   |   Model: `qwen3.5:9b-q4_K_M`                  |
|   - 15,554 Canonical Prices       |   |   Config: `temperature: 0.1`, `think: false`  |
|   - 8,435 Financial Statements    |   |   100% Cục bộ — Không gửi dữ liệu ra ngoài    |
|   ALLOW_PRODUCTION_DB_WRITE=false |   +-----------------------------------------------+
+-----------------------------------+
```

---

## 2. LUỒNG DỮ LIỆU & QUY TẮC POINT-IN-TIME (DATA FLOW & PIT INTEGRITY)

1. **Chuẩn hóa Dữ liệu Gốc:**
   - Dữ liệu thô từ các nhà cung cấp (DNSE, Vietcap, LotusMarket, CafeF RSS, Macro Series) được chuẩn hóa và lưu trữ có cấu trúc.
   - Mỗi bản ghi tài chính đều gắn liền 2 mốc thời gian:
     - `observation_date`: Kỳ báo cáo kế toán (ví dụ: `2025-12-31`).
     - `publication_date`: Thời điểm báo cáo thực tế được công bố ra công chúng.
2. **Quy tắc Lọc Point-in-Time (PIT Filtering):**
   - Mọi truy vấn phân tích, định giá và kiểm tra của AI Analyst đều phải truyền tham số `as_of_date`.
   - Hệ thống nghiêm cấm sử dụng các BCTC có `publication_date > as_of_date` để triệt tiêu hoàn toàn rủi ro nhìn trước tương lai (Look-ahead bias).
3. **Chuẩn hóa Trailing Twelve Months (TTM):**
   - Giá trị TTM bắt buộc tính toán trên 4 quý liên tục khả dụng gần nhất.
   - Tuyệt đối không dùng số liệu cả năm cũ để thay thế cho TTM nếu chưa đủ bằng chứng.

---

## 3. CÁC SERVICE QUAN TRỌNG TRONG BACKEND

### 3.1. FundamentalSnapshotBuilder & FinancialRepository
- Truy vấn BCTC dạng chuẩn hóa (Bảng Cân đối Kế toán, Báo cáo KQKD, Báo cáo LCTT).
- Tính toán các chỉ số tài chính TTM: EPS TTM, Doanh thu TTM, Gross Margin, Net Margin, ROE, ROA, ROIC.
- Áp dụng các mô hình ngành chuyên biệt (Ngân hàng: NIM, CASA, NPL; Bất động sản: Tồn kho dự án; Sản xuất/Thép: Vòng quay hàng tồn kho, Chu kỳ tiền mặt CCC).

### 3.2. ValuationSnapshotBuilder & Valuation Ensemble
- **DCF (Discounted Cash Flow):** Dự báo dòng tiền tự do FCF nhiều năm, tính WACC và giá trị cuối kỳ theo mô hình Gordon Growth. Xác định 3 dải giá trị: Thận trọng (Bear), Cơ sở (Base), và Lạc quan (Bull).
- **Định giá Tương đối P/E & P/B:** So sánh bội số thị trường với trung vị nhóm ngành (Peer Median) và lịch sử định giá của doanh nghiệp.
- **Thu nhập Thặng dư (Residual Income Model - RIM):** Áp dụng chi phí vốn chủ sở hữu $K_e$ và giá trị sổ sách BVPS để định giá các ngành tài chính/ngân hàng.

### 3.3. StockScreenerEngine & OpportunityEngine
- Thực thi các bộ lọc đa tiêu chí (ví dụ: `P/E < 15` và `ROE > 15%`).
- Kết quả lọc đồng bộ 100% với AI Analyst, trả về mã bằng chứng `evidence_id` truy nguyên cụ thể cho từng cổ phiếu đạt chuẩn.

### 3.4. Local AI Analyst Engine
- Hoạt động qua router `apps/api/routers/ai.py` và service `services/ai/analyst.py`.
- Tiếp nhận câu hỏi, tự động xây dựng kế hoạch truy vấn (Query Planning), gọi các công cụ tài chính nội bộ (`services/ai/tools.py`), thu thập số liệu có bằng chứng và truyền luồng suy luận SSE về giao diện người dùng.

---

## 4. KIẾN TRÚC ĐỒ HỌA 3D THREE.JS TOÀN DIỆN (SINGLE CANVAS HOST)

InvestIntel áp dụng kiến trúc đồ họa 3D không gian thể chế dựa trên **Three.js v0.187.0**:

1. **Host Component Tập trung (`investintel-scene-host.tsx`):**
   - Chỉ duy trì **1 WebGL Canvas** duy nhất gắn tại root layout `AppShell`.
   - Vị trí: `position: fixed`, `inset: 0`, `z-index: 0`, `pointer-events: none`.
   - Chuyển đổi scene khi đổi trang mà **không tạo lại WebGL context**, dọn dẹp bộ nhớ VRAM triệt để thông qua hàm `dispose()`.
2. **4 Concept Không Gian:**
   - **AI Intelligence Globe** (`/`): Quả cầu viễn thám, vành quỹ đạo nghiêng và các cung truyền dữ liệu toàn cầu.
   - **3D Market Landscape** (`/market`, `/screener`, `/opportunities`): Địa hình lưới thể chế, cụm trụ ngành kết hợp `InstancedMesh` (1 Draw Call duy nhất cho toàn bộ thị trường).
   - **Neural Intelligence** (`/ai`): Mạng nơ-ron 3D đa tầng phản ứng trực tiếp với từng pha của luồng SSE (`fetching_data`, `llm_reasoning`, `validating`, `completed`).
   - **Valuation Reactor** (`/research/[ticker]`, `/valuation`): Lõi định giá hạt nhân, 4 vòng quỹ đạo mô hình (DCF/PE/PB/RIM) và vectơ biên an toàn.
3. **Cơ chế Điều tiết Hiệu năng & Thắt nút Khung hình Thông minh (Performance Controller):**
   - Mặc định 30 FPS trên GPU RTX 3050 Laptop.
   - Tự động hạ xung nhịp đồ họa xuống **15 FPS** khi AI Analyst đang suy luận cục bộ để bảo vệ VRAM và tránh tranh chấp tài nguyên GPU với Ollama.

---

## 5. CÁC QUY TẮC AN TOÀN & BẢO VỆ DỰ ÁN BẮT BUỘC

1. **Bảo vệ Cơ sở Dữ liệu Sản xuất:**
   - Biến môi trường `ALLOW_PRODUCTION_DB_WRITE=false` luôn luôn kích hoạt.
   - Mọi bài kiểm thử tự động ghi dữ liệu chỉ được phép thực thi trên cơ sở dữ liệu tạm thời (in-memory SQLite hoặc temporary file), tuyệt đối không chạm vào `data/trading.db`.
2. **Không Khởi tạo Luồng Giao dịch:**
   - InvestIntel là hệ thống nghiên cứu và phân tích (Decision Support System), không phải Brokerage Bot. Tuyệt đối không tích hợp API đặt lệnh thật hoặc giao dịch tự động.
3. **Toàn vẹn Bảo mật (JWT Hardening):**
   - Không sử dụng secret key tĩnh trong mã nguồn. Khi không có biến môi trường cấu hình, hệ thống tự động sinh khóa ngẫu nhiên mật mã trong bộ nhớ.

