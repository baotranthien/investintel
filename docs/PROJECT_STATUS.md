# INVESTINTEL — TRẠNG THÁI DỰ ÁN & TIẾN TRÌNH VẬN HÀNH
**INVESTINTEL PROJECT STATUS & OPERATIONAL HEALTH**

* **Mã trạng thái:** `INVESTINTEL-STATUS-2026-11-03`
* **Ngày cập nhật:** 03/11/2026
* **Trạng thái kỹ thuật tổng thể:** **TECHNICAL READINESS PASS / 100% OPERATIONAL READY**
* **Cơ sở dữ liệu sản xuất:** SQLite `data/trading.db` (SHA-256: `55D335EC928E4EC871BC95F426F7E27B53F6EED88969F2207A1EB7D151A89D0C`)
* **Bảo vệ ghi sản xuất:** `ALLOW_PRODUCTION_DB_WRITE=false` (Bắt buộc & Duy trì nghiêm ngặt)
* **Resident AI Model:** Ollama `qwen3.5:9b-q4_K_M` (Local GPU Execution, RTX 3050 Laptop 4GB VRAM)

---

## 1. TỔNG QUAN HỆ THỐNG & CÁC MODULE CHÍNH

InvestIntel là nền tảng nghiên cứu và phân tích đầu tư thể chế, hoạt động 100% cục bộ và ưu tiên tính chuẩn xác của dữ liệu và bằng chứng.

```
+-----------------------------------+---------------------------------------------------------+
| Module                            | Tình Trạng Hiện Tại                                     |
+-----------------------------------+---------------------------------------------------------+
| 1. Market Data Intelligence       | SẴN SÀNG — 15,554 Canonical Prices (VN100/VN30)         |
| 2. Financial Statements (BCTC)    | SẴN SÀNG — 8,435 BCTC (BS, IS, CF) lọc Point-in-Time    |
| 3. Fundamental Analysis           | SẴN SÀNG — Mô hình ngành Ngân hàng, BĐS, Bán lẻ         |
| 4. Stock Valuation Ensemble       | SẴN SÀNG — DCF (Bear/Base/Bull), P/E, P/B, RIM          |
| 5. Stock Screener Engine          | SẴN SÀNG — Đa tiêu chí, đồng bộ 100% với AI Analyst     |
| 6. Market Breadth & Macro         | SẴN SÀNG — Dòng tiền, dầu Brent/WTI, lãi suất, CPI      |
| 7. Portfolio Analysis & Risk      | SẴN SÀNG — 10 danh mục rủi ro, HHI concentration        |
| 8. AI Investment Analyst          | SẴN SÀNG — Ollama Qwen3.5 9B, Stream SSE, Zero Leak     |
| 9. Three.js 3D Spatial Graphics   | SẴN SÀNG — AI Intelligence Globe (Độc quyền tại Trang chủ) |
| 10. Desktop Terminal UI & Launcher| SẴN SÀNG — Apple Daylight Neutral, 1-Click `InvestIntel.exe`|
+-----------------------------------+---------------------------------------------------------+
```

---

## 2. DỮ LIỆU ĐÃ KIỂM CHỨNG (CANONICAL INVENTORY)

| Chỉ số / Danh mục | Số lượng ghi nhận | Trạng thái kiểm chứng |
| :--- | :---: | :--- |
| **Giá đóng cửa (Canonical Prices)** | **15,554** | Đã chuẩn hóa, 0 duplicate prices |
| **Báo cáo Tài chính (Statements)** | **8,435** | PIT-filtered (Balance Sheet, Income, Cash Flow) |
| **Dữ liệu Dầu thô & Hàng hóa vĩ mô** | **3,402** | Brent & WTI đối chiếu hàng ngày |
| **Tin tức & Sự kiện (Event Records)** | **3,224** | RSS CafeF, Vietstock, VnEconomy |
| **Chỉ số Vĩ mô (Macro Observations)**| **2,285** | DGS10, CPI, GDP, Tỷ giá USD/VND, SBV Rates |
| **Cổ phiếu theo dõi (Active Equities)**| **100** | Rổ VN100 & VN30, phân loại ICB |
| **Thành viên rổ chỉ số (Memberships)** | **149** | VN100, VN30, VN300 |

---

## 3. CÁC MỐC NGHIỆM THU MỚI NHẤT ĐÃ HOÀN THÀNH

### 3.1. Hợp nhất Tính Nhất quán Screener & AI Analyst (2026-11-02)
- **FPT:** P/E canonical 9.94x, ROE 24.23%. Thỏa mãn đầy đủ tiêu chí `P/E < 15` và `ROE > 15%`.
- **VCB:** P/E canonical 11.30x, ROE 19.82%. Thỏa mãn đầy đủ tiêu chí `P/E < 15` và `ROE > 15%`.
- **Biên lợi nhuận gộp FPT:** TTM đạt **34.65%** cho kỳ 4 quý kết thúc ngày 2026-06-30 (Evidence `E008`).
- **Cổ tức BMP:** Phân biệt rành mạch giữa Cổ tức TTM (8,360 VND/cp) và Tổng cổ tức lịch sử FY2025 (14,860 VND/cp) qua các đợt Corporate Action có ngày chốt quyền cụ thể.
- **MWG ROIC:** Đầy đủ dữ liệu Debt, Equity, Cash, Invested Capital và NOPAT cùng kỳ; không phát sinh lỗi âm vốn đầu tư giả tạo.

### 3.2. Triển khai Đồ họa 3D Three.js Độc quyền tại Trang chủ & Trình khởi chạy 1-Click (2026-11-05)
- **Tách biệt Không gian 3D (Spatial Decoupling):**
  - Chỉ hiển thị duy nhất hiệu ứng **AI Intelligence Globe** trong khung trình diễn riêng biệt (`.heroVisualStage`) bên phải khu vực Hero của Trang chủ (`/`), đảm bảo 0% chồng lấn lên chữ hoặc thanh điều hướng bên.
  - Toàn bộ các trang chức năng khác (`/market`, `/screener`, `/opportunities`, `/ai`, `/research/[ticker]`, `/valuation`, `/portfolio`, `/watchlist`) giữ giao diện Apple Daylight Neutral nguyên bản, sạch sẽ và tối ưu hiệu năng.
- **Trình khởi chạy 1-Click Native (`InvestIntel.exe` & `InvestIntel.bat`):**
  - Tự động giải phóng cổng xung đột, khởi chạy đồng bộ Ollama (11434), FastAPI Backend (8000) và Next.js Frontend (3000), kiểm tra Health Check và tự mở trình duyệt chỉ với 1 cú nhấp chuột.
  - Quản lý tiến trình con bằng Windows Job Object, đảm bảo tắt sạch 100% khi đóng cửa sổ.

### 3.3. Tăng cường Bảo mật (JWT Secret Hardening)
- Loại bỏ hoàn toàn fallback secret tĩnh trong mã nguồn router auth và middleware.
- Tự động sinh khóa ngẫu nhiên mật mã (CspRng) trong bộ nhớ khi không có cấu hình môi trường, ngăn chặn triệt để nguy cơ bypass xác thực.

---

## 4. BẢNG GIỚI HẠN & DỮ LIỆU ĐANG GẮN NHÃN (KNOWN LIMITATIONS)

Tuân thủ nguyên tắc minh bạch thể chế, các trường hợp chưa đủ 100% dữ liệu gốc đều được gắn nhãn cảnh báo rõ ràng:

| Tên Hạn chế / Dữ liệu | Phân loại Nhãn | Nguyên nhân Kỹ thuật & Biện pháp Xử lý |
| :--- | :---: | :--- |
| **IAS 33 Basic Shares Weighting** | `ESTIMATE_DISCLOSED` | Các quý giữa niên độ tại Việt Nam không công bố số lượng cổ phiếu bình quân gia quyền. Hệ thống dùng số cổ phiếu lưu hành cuối kỳ và gắn cờ `is_estimate=True`. |
| **Chế độ Vĩ mô VN100 Proxy** | `PROXY_CONTEXT` | Một số cổ phiếu mới niêm yết chưa đủ 3 năm lịch sử định giá P/E được nội suy theo trung vị rổ VN100 làm ngữ cảnh tham chiếu. |
| **Độ trễ Công bố BCTC (Filing Lag)** | `PIT_OBSERVED` | BCTC quý được nạp vào hệ thống theo đúng ngày công bố thực tế (`publication_date`), không nhìn trước thời gian. |
| **Dòng Dữ liệu HOSE Trực tiếp** | `UNAVAILABLE_BLOCKED` | Chưa thiết lập hợp đồng thương mại với HOSE; hệ thống sử dụng nguồn cấp thứ cấp công khai hợp pháp (DNSE, Vietcap, LotusMarket). |
| **Giao dịch Tiền Thật** | `OUT_OF_SCOPE` | InvestIntel là nền tảng phân tích và hỗ trợ ra quyết định, tuyệt đối không mở cổng đặt lệnh môi giới hay giao dịch tự động. |

---

## 5. KẾT QUẢ KIỂM THỬ TỔNG HỢP HIỆN HÀNH

- **Backend Pytest Suite:** **474 / 474 tests** collected và thực thi theo chuẩn `pytest.ini`.
- **Frontend Build (Next.js 16.3.7 Turbopack):** **15/15 routes** biên dịch thành công 100%, 0 TypeScript errors.
- **Database Integrity Check:** SQLite `PRAGMA integrity_check` trả về `ok`, mã băm SHA-256 bảo lưu toàn vẹn.
