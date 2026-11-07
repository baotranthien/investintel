# INVESTINTEL — NỀN TẢNG NGHIÊN CỨU & PHÂN TÍCH ĐẦU TƯ THỂ CHẾ
**INSTITUTIONAL AI EQUITY RESEARCH & INVESTMENT ANALYST PLATFORM**

> *“Quant engine calculates. AI explains with verifiable evidence.”*

InvestIntel là nền tảng nghiên cứu và phân tích đầu tư vốn cổ phần cá nhân theo chuẩn mực thể chế, tích hợp mô hình định lượng xác định (Deterministic Quant Engines), đối soát BCTC theo thời điểm (Point-in-Time), trí tuệ nhân tạo cục bộ (Local Ollama AI Analyst) và hệ thống đồ họa 3D viễn thám không gian (Three.js 3D).

---

## 1. CÔNG NGHỆ & KIẾN TRÚC TỔNG QUAN

- **Frontend:** Next.js 16 (App Router) + React 19 + Turbopack + Apple Warm Neutral Daylight Minimalist Design System.
- **Đồ họa 3D Không gian:** Three.js v0.187.0 với kiến trúc **Single Canvas Host** duy nhất:
  - Concept 1: **AI Intelligence Globe** (`/`) — Quả cầu viễn thám và luồng dữ liệu toàn cầu.
  - Concept 2: **3D Market Landscape** (`/market`, `/screener`, `/opportunities`) — Địa hình thanh khoản và trụ ngành InstancedMesh.
  - Concept 3: **Neural Intelligence** (`/ai`) — Mạng nơ-ron đa tầng đồng bộ thời gian thực với luồng SSE.
  - Concept 4: **Valuation Reactor** (`/research/[ticker]`, `/valuation`) — Lõi định giá tổng hợp, 4 quỹ đạo mô hình (DCF/PE/PB/RIM) và biên an toàn.
- **Backend:** FastAPI + SQLAlchemy ORM + Point-in-Time Financial Repositories.
- **AI Core:** Ollama chạy 100% cục bộ trên GPU máy trạm (`qwen3.5:9b-q4_K_M`), không gửi dữ liệu ra ngoài (Zero External Leak).
- **Cơ sở dữ liệu:** SQLite Canonical Database (`data/trading.db`) với chế độ bảo vệ ghi nghiêm ngặt `ALLOW_PRODUCTION_DB_WRITE=false`.

---

## 2. KHỞI ĐỘNG NHANH (QUICK START)

### Cách 1: Khởi động 1-Click trên Windows
Nhấp đúp vào các tệp thực thi ở thư mục gốc:
- **`Start-InvestIntel.bat`**: Khởi động tự động toàn bộ 3 dịch vụ (Ollama, FastAPI, Next.js).
- **`Status-InvestIntel.bat`**: Kiểm tra trạng thái các tiến trình đang chạy.
- **`Doctor-InvestIntel.bat`**: Chẩn đoán tính toàn vẹn hệ thống và cơ sở dữ liệu.
- **`Stop-InvestIntel.bat`**: Dừng an toàn toàn bộ các dịch vụ.

### Cách 2: Khởi động qua PowerShell Orchestrator
```powershell
powershell -ExecutionPolicy Bypass -File scripts/local/start-investintel.ps1
```

### Địa chỉ truy cập:
- **Giao diện Web:** `http://localhost:3000`
- **Tài liệu API (Swagger):** `http://127.0.0.1:8000/docs`
- **Kiểm tra sức khỏe Backend:** `http://127.0.0.1:8000/api/v1/health`

---

## 3. CÁC LỆNH THƯỜNG DÙNG

```bash
# 1. Chạy toàn bộ 474 bài kiểm thử của repository
.venv\Scripts\python.exe -m pytest

# 2. Chạy bộ kiểm thử hồi quy tính nhất quán tài chính và bảo mật JWT
.venv\Scripts\python.exe -m pytest tests/test_one_pass_final_hardening.py tests/test_screener_ai_consistency.py tests/test_jwt_auth_hardening.py

# 3. Kiểm tra kiểu dữ liệu TypeScript của Frontend
powershell -Command "Set-Location apps/web; .\node_modules\.bin\tsc.cmd --noEmit"

# 4. Kiểm thử Production Build Next.js
npm --prefix apps/web run build

# 5. Kiểm tra mã băm bảo vệ cơ sở dữ liệu sản xuất
powershell -Command "Get-FileHash data/trading.db -Algorithm SHA256"
```

---

## 4. CẤU TRÚC THƯ MỤC CHUẨN HÓA

```
investintel/
├── apps/
│   ├── api/               # FastAPI Backend Application & Routers
│   └── web/               # Next.js 16 Web Frontend (React 19, Three.js components)
├── database/              # Canonical models, schema & connection managers
├── docs/                  # Tài liệu kiến trúc, trạng thái và nghiệm thu
│   ├── ARCHITECTURE.md    # Đặc tả kiến trúc toàn diện
│   ├── DEVELOPMENT.md     # Hướng dẫn môi trường lập trình & vận hành
│   ├── PROJECT_STATUS.md  # Trạng thái dự án & bảng dữ liệu kiểm chứng
│   ├── audits/            # Báo cáo nghiệm thu chính thức & tổng hợp lịch sử
│   └── implementation/    # Báo cáo triển khai kỹ thuật 3D Three.js
├── data/                  # Canonical SQLite Database (trading.db)
├── scripts/               # Scripts vận hành, seed dữ liệu & local supervisor
├── services/              # Domain Services (AI, Fundamentals, Valuation, Screener, Risk)
├── tests/                 # Test Suite chuẩn hóa (Unit, Integration, Contract, Regression)
├── Start-InvestIntel.bat  # Launcher khởi động nhanh
├── pytest.ini             # Cấu hình test runner chính thức
└── .env.example           # Mẫu cấu hình môi trường chuẩn
```

---

## 5. TÀI LIỆU LIÊN QUAN

- [Đặc tả Kiến trúc Hệ thống](docs/ARCHITECTURE.md)
- [Hướng dẫn Phát triển & Vận hành](docs/DEVELOPMENT.md)
- [Trạng thái Dự án & Bảng Dữ liệu Kiểm chứng](docs/PROJECT_STATUS.md)
- [Báo cáo Nghiệm thu Kỹ thuật & Nghiệp vụ Cuối cùng](docs/audits/INVESTINTEL_FINAL_ACCEPTANCE_2026-11-02.md)
- [Báo cáo Triển khai Đồ họa 3D Three.js](docs/implementation/INVESTINTEL_THREEJS_IMPLEMENTATION.md)
- [Tổng hợp Lịch sử Kiểm toán](docs/audits/HISTORICAL_AUDITS_SUMMARY.md)
