# INVESTINTEL — TỔNG HỢP LỊCH SỬ KIỂM TOÁN VÀ NGHIỆM THU
**HISTORICAL AUDIT & ACCEPTANCE CHRONOLOGY**

* **Mục đích:** Lưu trữ cô đọng các mốc kiểm toán, chẩn đoán và nghiệm thu qua các giai đoạn phát triển của InvestIntel (Phase 3 – Phase 6, AI Analyst Hardening, Security Sign-Off).
* **Tài liệu nghiệm thu chính thức hiện hành:** [`INVESTINTEL_FINAL_ACCEPTANCE_2026-11-02.md`](file:///c:/Users/baotr/Downloads/trading/docs/audits/INVESTINTEL_FINAL_ACCEPTANCE_2026-11-02.md)
* **Tài liệu triển khai Three.js 3D:** [`INVESTINTEL_THREEJS_IMPLEMENTATION.md`](file:///c:/Users/baotr/Downloads/trading/docs/implementation/INVESTINTEL_THREEJS_IMPLEMENTATION.md)

---

## 1. GIAI ĐOẠN 1–2: NỀN TẢNG DỮ LIỆU & BCTC CHUẨN HÓA

### 1.1. Các mục tiêu hoàn thành:
- Thiết lập Schema Canonical Database (PostgreSQL / SQLite) cho tài sản niêm yết, chuỗi giá lịch sử (OHLCV) và bộ 3 BCTC (Bảng Cân đối Kế toán, Báo cáo Kết quả Kinh doanh, Báo cáo Lưu chuyển Tiền tệ).
- Xây dựng kho lưu trữ tài chính hỗ trợ lọc Point-in-Time (PIT): Mọi truy vấn BCTC đều áp dụng điều kiện quan sát thời điểm `observation_date` và `publication_date`, loại bỏ hoàn toàn rủi ro nhìn trước tương lai (look-ahead bias).

### 1.2. Vấn đề đã xử lý & bài học kinh nghiệm:
- **Xử lý số liệu âm:** Phân biệt rõ ràng giữa giá trị 0 (zero) và giá trị thiếu/không khả dụng (None / N/A).
- **Chuẩn hóa TTM (Trailing Twelve Months):** Yêu cầu bắt buộc phải đủ 4 quý liên tục để tính TTM; nếu thiếu quý thì chuyển sang cơ chế suy diễn có gắn nhãn cảnh báo rõ ràng, không tự ý chèn số liệu kỳ năm cũ làm TTM.

---

## 2. GIAI ĐOẠN 3: ĐỘNG CƠ ĐỊNH GIÁ & MULTI-MODEL VALUATION

### 2.1. Các mô hình cốt lõi:
- **DCF (Discounted Cash Flow):** Dự báo dòng tiền tự do FCF nhiều năm, tính WACC và giá trị cuối kỳ theo mô hình Gordon Growth. Xác định 3 dải giá trị: Thận trọng (Bear), Cơ sở (Base), và Lạc quan (Bull).
- **Định giá Tương đối P/E & P/B:** So sánh bội số thị trường với trung vị nhóm ngành (Peer Median) và lịch sử định giá của doanh nghiệp.
- **Thu nhập Thặng dư (Residual Income Model - RIM):** Áp dụng chi phí vốn chủ sở hữu $K_e$ và giá trị sổ sách BVPS để định giá các ngành tài chính/ngân hàng.

### 2.2. Điểm kiểm toán chính:
- Không hardcode EPS hay doanh thu.
- Tự động phát hiện trường hợp $WACC \le g$ hoặc $K_e \le g$ để cảnh báo mô hình không khả thi về mặt toán học thay vì trả về kết quả âm vô lý.

---

## 3. GIAI ĐOẠN 4: TRÍ TUỆ ĐẦU TƯ NÂNG CAO & BỘ LỌC CỔ PHIẾU

### 3.1. Các động cơ triển khai:
- **StockScreenerEngine:** Cho phép lọc linh hoạt theo các tiêu chí kết hợp: P/E, ROE, P/B, vốn hóa, ngành.
- **OpportunityEngine:** Chấm điểm cơ hội đầu tư trên thang 0–100, tích hợp ma trận xung đột tín hiệu và độ tin cậy dữ liệu.
- **RiskEngine:** Phân tích rủi ro đa chiều (Đòn bẩy D/E, Khả năng trả nợ, Rủi ro biên lợi nhuận, Nhạy cảm vĩ mô).

### 3.2. Chỉnh sửa tính nhất quán (Remediation 2026-11-02):
- **Screener & AI Analyst Consistency:** Điều chỉnh đồng bộ giá trị P/E và ROE của các cổ phiếu bluechip (FPT P/E canonical 9.94x, VCB P/E canonical 11.30x) giữa động cơ định lượng và AI Analyst. Cả 2 mã đều thỏa mãn chính xác bộ lọc `P/E < 15` và `ROE > 15%`.
- **Cổ tức BMP:** Đối chiếu và xác nhận lịch sử cổ tức phân tách rõ ràng giữa TTM (8,360 VND/cp) và tổng lịch sử các đợt Corporate Actions.

---

## 4. GIAI ĐOẠN 5: PHÂN TÍCH DANH MỤC & PHÒNG HỘ RỦI RO

### 4.1. Chức năng danh mục:
- Tải trọng danh mục (Portfolio Holdings), phân bổ tài sản theo ngành, mức độ tập trung vốn (HHI - Herfindahl-Hirschman Index).
- Phân tích rủi ro Beta, độ nhạy lãi suất và căng thẳng thanh khoản đối với danh mục cá nhân.

### 4.2. Bằng chứng kiểm toán:
- Xác nhận cơ chế `ALLOW_PRODUCTION_DB_WRITE=false` bảo vệ an toàn toàn bộ dữ liệu danh mục người dùng.

---

## 5. GIAI ĐOẠN 6: ỔN ĐỊNH CỤC BỘ & NÂNG CẤP AI ANALYST CỤC BỘ

### 5.1. Nâng cấp mô hình AI cục bộ:
- Thay thế hoàn toàn các API đám mây bên ngoài bằng mô hình chạy cục bộ **Ollama `qwen3.5:9b-q4_K_M`** trên GPU máy trạm (NVIDIA RTX 3050 Laptop 4GB VRAM).
- Cấu hình suy luận: Nhiệt độ 0.1, `num_ctx: 8192`, `think: false` đối với các câu hỏi tài chính trực tiếp, tắt suy luận lang thang để tập trung trích dẫn bằng chứng thực tế.

### 5.2. Bảo mật Token & JWT Hardening:
- Loại bỏ hoàn toàn fallback secret tĩnh trong `apps/api/routers/auth.py` và `services/auth/middleware.py`.
- Tự động sinh khóa ngẫu nhiên mật mã (CspRng) trong bộ nhớ khi không có cấu hình môi trường, ngăn chặn triệt để nguy cơ bypass xác thực.

### 5.3. Trực quan hóa 3D Three.js:
- Tích hợp 4 Concept đồ họa 3D thể chế (AI Intelligence Globe, 3D Market Landscape, Neural Intelligence, Valuation Reactor) với kiến trúc Single Canvas Host và điều tiết khung hình thông minh (30 FPS mặc định, 15 FPS khi AI streaming).

---

## 6. DANH MỤC BẰNG CHỨNG KIỂM TOÁN LƯU TRỮ

Toàn bộ artifacts bằng chứng số liệu và ảnh chụp màn hình kiểm toán được bảo lưu tại:
- `docs/audits/evidence/full_app_acceptance/`
- `docs/audits/evidence/ai_analyst_final_reacceptance_2026-11-02/`

