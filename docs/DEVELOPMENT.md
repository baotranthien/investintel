# INVESTINTEL — HƯỚNG DẪN MÔI TRƯỜNG PHÁT TRIỂN & VẬN HÀNH CỤC BỘ
**DEVELOPMENT ENVIRONMENT & LOCAL OPERATIONS GUIDE**

* **Cập nhật gần nhất:** 03/11/2026
* **Hệ điều hành khuyến nghị:** Windows 11 (hoặc macOS / Linux)
* **Phần cứng khuyến nghị:** CPU 6+ Cores, RAM 16GB+, GPU NVIDIA (RTX 3050 Laptop 4GB VRAM trở lên)

---

## 1. YÊU CẦU PHẦN MỀM CƠ BẢN

1. **Python 3.10+**:
   - Sử dụng môi trường ảo: `.venv`
   - Cài đặt thư viện: `.venv\Scripts\pip install -r requirements.txt`
2. **Node.js v20+ & npm** (Hiện hành: Node v24.14.0):
   - Quản lý gói thư mục web: `apps/web`
3. **Ollama (Cục bộ)**:
   - Tải về từ: [ollama.com](https://ollama.com)
   - Kéo mô hình phục vụ AI Analyst:
     ```bash
     ollama pull qwen3.5:9b-q4_K_M
     ```

---

## 2. KHỞI ĐỘNG NHANH TOÀN BỘ HỆ THỐNG (ONE-CLICK STARTUP)

Trên Windows, bạn có thể khởi động toàn bộ hệ thống bằng các tệp script hợp nhất sẵn có:

### Cách 1: Sử dụng Batch Script ở thư mục gốc
- **Khởi động toàn bộ:** Nhấp đúp vào `Start-InvestIntel.bat`
- **Kiểm tra trạng thái:** Nhấp đúp vào `Status-InvestIntel.bat`
- **Chẩn đoán sức khỏe:** Nhấp đúp vào `Doctor-InvestIntel.bat`
- **Dừng toàn bộ:** Nhấp đúp vào `Stop-InvestIntel.bat`

### Cách 2: Sử dụng PowerShell Orchestrator
```powershell
powershell -ExecutionPolicy Bypass -File scripts/local/start-investintel.ps1
```

Script này tự động:
1. Kiểm tra và khởi động tiến trình Ollama cục bộ.
2. Khởi động FastAPI Backend tại `http://127.0.0.1:8000`.
3. Khởi động Next.js Web Frontend tại `http://localhost:3000`.
4. Ghi nhận nhật ký tại `logs/supervisor/supervisor.log`.

---

## 3. KHỞI ĐỘNG THỦ CÔNG TỪNG THÀNH PHẦN

Nếu cần debug từng service độc lập:

### Bước 1: Khởi động Ollama AI Core
```bash
ollama serve
```
Kiểm tra API Ollama hoạt động: `curl http://127.0.0.1:11434/api/tags`

### Bước 2: Khởi động FastAPI Backend
```bash
.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

### Bước 3: Khởi động Next.js Web Frontend
```bash
npm --prefix apps/web run dev
```
- Truy cập trình duyệt: `http://localhost:3000`

---

## 4. QUY TRÌNH KIỂM THỬ, LINT, TYPECHECK & BUILD

Mọi thay đổi mã nguồn phải vượt qua đầy đủ các bài kiểm tra chất lượng trước khi bàn giao:

### 4.1. Chạy Backend Test Suite
Nhờ có tệp cấu hình `pytest.ini` tại thư mục gốc, bạn có thể chạy toàn bộ test suite tiêu chuẩn một cách nhanh chóng:
```bash
# Chạy toàn bộ 474 bài kiểm thử của repository
.venv\Scripts\python.exe -m pytest

# Chạy kiểm thử hồi quy tính nhất quán tài chính và bảo mật
.venv\Scripts\python.exe -m pytest tests/test_one_pass_final_hardening.py tests/test_screener_ai_consistency.py tests/test_jwt_auth_hardening.py -v
```

### 4.2. Kiểm tra TypeScript & Typecheck Frontend
```powershell
powershell -Command "Set-Location apps/web; .\node_modules\.bin\tsc.cmd --noEmit"
```

### 4.3. Kiểm thử Production Build Frontend
```bash
npm --prefix apps/web run build
```
Đảm bảo tất cả 15 route được biên dịch thành công qua Turbopack mà không có lỗi SSR / Hydration mismatch.

---

## 5. CẤU HÌNH BIẾN MÔI TRƯỜNG (.ENV)

Tệp `.env` tại thư mục gốc điều khiển các chế độ vận hành:

```ini
# BẢO VỆ DATABASE SẢN XUẤT (BẮT BUỘC GIỮ FALSE)
ALLOW_PRODUCTION_DB_WRITE=false

# CẤU HÌNH ĐƯỜNG DẪN DATABASE CANONICAL
DATABASE_URL=sqlite:///data/trading.db

# CẤU HÌNH AI ANALYST CỤC BỘ
OLLAMA_BASE_URL=http://127.0.0.1:11434
AI_PRIMARY_MODEL=qwen3.5:9b-q4_K_M
AI_FAST_MODEL=qwen3.5:9b-q4_K_M

# CẤU HÌNH MÃ HÓA BẢO MẬT (Tùy chọn, hệ thống tự sinh ngẫu nhiên nếu để trống)
JWT_SECRET_KEY=
```

---

## 6. LƯU Ý VỀ TỐI ƯU HÓA PHẦN CỨNG & VRAM

- Khi máy tính chỉ có 4GB VRAM (như RTX 3050 Laptop), mô hình `qwen3.5:9b-q4_K_M` chiếm khoảng 5.5GB bộ nhớ (một phần offload vào RAM hệ thống).
- Hệ thống đồ họa Three.js 3D đã được lập trình sẵn cơ chế **AI Throttling tự động**: khi có truy vấn phân tích AI đang diễn ra, tốc độ render 3D sẽ tự động giảm xuống **15 FPS** để giải phóng năng lực GPU cho tác vụ AI. Người dùng cũng có thể chủ động chuyển chế độ sang **Tiết kiệm (15 FPS)** hoặc **Tĩnh (Tắt 3D)** tại nút chọn góc trên bên phải thanh Topbar.

