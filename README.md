# Personal Investment Intelligence Platform

Nền tảng Thông minh Đầu tư Cá nhân cho thị trường chứng khoán Việt Nam.

## Kiến trúc
Hệ thống sử dụng kiến trúc **Modular Monolith** kết hợp **Local AI** để tiết kiệm chi phí API.
- **Frontend**: Next.js, React, Vanilla CSS.
- **Backend**: FastAPI, SQLAlchemy.
- **Database**: PostgreSQL, Redis.
- **AI**: Ollama chạy local.

## Cấu trúc thư mục
- `apps/web`: Frontend Next.js
- `apps/api`: Backend FastAPI
- `services/`: Các module domain logic
- `database/`: Database schema, migrations
- `docs/`: Tài liệu dự án

## Yêu cầu môi trường
- Docker & Docker Compose
- Node.js (cho local web dev)
- Python 3.10+ (cho local api dev)
- Ollama (để chạy local AI)

## Cách chạy (Development)
1. Copy file biến môi trường:
```bash
cp .env.example .env
```
2. Khởi động toàn bộ stack bằng Docker Compose:
```bash
docker compose up -d
```
3. Truy cập:
- Frontend: `http://localhost:3000`
- API Health: `http://localhost:8000/api/v1/health`

## Trạng thái Phase 5 (Local AI Research Intelligence)
- Đã thiết lập `OllamaProvider` để gọi Local LLM hoàn toàn miễn phí và bảo mật.
- Đã triển khai `AIRouter` tối ưu hóa lựa chọn model theo tác vụ (tiết kiệm tài nguyên cho máy 16GB RAM).
- Đã xây dựng cơ chế Tool Calling thông qua `AITools` giúp AI đọc trực tiếp dữ liệu từ các engine (Phase 1-4).
- Xây dựng `AIAnalyst` tạo báo cáo Daily Brief và phân tích chuyên sâu cổ phiếu bằng Tiếng Việt (chỉ dựa vào dữ liệu định lượng, không tự bịa số liệu).
- Tích hợp thành công UI Research Analyst `/research` vào Frontend.
- Sẵn sàng tiến tới Phase 6 (Production UX & Alerts).
