# HƯỚNG DẪN TRIỂN KHAI CLOUD — PERSONAL INVESTMENT INTELLIGENCE PLATFORM

Tài liệu hướng dẫn triển khai nền tảng nghiên cứu đầu tư cá nhân trên hạ tầng Cloud Miễn phí (Free Tier), bảo mật dữ liệu tài chính cá nhân và bảo toàn tính toàn vẹn dữ liệu (Point-In-Time).

---

## 1. Kiến trúc Triển khai (Topology)

| Thành phần | Nền tảng | Gói | Đặc tính vận hành |
|---|---|---|---|
| **Frontend** | **Vercel** | Hobby (Free) | Next.js PWA, SSR/SSG, Relative `/api/v1` rewrites sang Render backend |
| **Backend** | **Render** | Free Web Service | Docker (FastAPI), chịu độ trễ khởi động lạnh (Cold Start ~30-50s) |
| **Database** | **Neon** | Free Tier (PostgreSQL) | SSL (`sslmode=require`), Pooled connection, Tự động ngủ (Compute scale-to-zero) |
| **Redis** | **Upstash / Memory** | Free / Optional | Tuỳ chọn; nếu không cấu hình sẽ tự động dùng in-memory rate-limiting an toàn |
| **Cron Job** | **cron-job.org** | Free | Gọi webhook định kỳ qua HTTP POST có xác thực `X-Cron-Secret` |
| **AI Gateway** | **Gemini / Groq / OpenRouter** | Free tiers | Chuỗi fallback: Gemini (5 attempts) → Groq → OpenRouter (:free) → Typed `AI_UNAVAILABLE` |

---

## 2. Bước 1 — Thiết lập Neon PostgreSQL

1. Đăng ký tài khoản miễn phí tại [neon.tech](https://neon.tech).
2. Tạo dự án mới (ví dụ: `investintel-db`).
3. Trong Dashboard của Neon, lấy chuỗi kết nối **Pooled Connection**:
   - Chọn tab **Connection Details** → tích chọn **Connection pooling**.
   - Chuỗi kết nối có dạng:
     `postgresql://<user>:<password>@ep-<project>-pooler.<region>.aws.neon.tech/neondb?sslmode=require`
4. **Giới hạn dung lượng (Quotas)**:
   - Theo dõi dung lượng lưu trữ thực tế trên Neon Console Dashboard.
   - Không giả định dung lượng cố định 500 MB cũ; hệ thống sử dụng cơ chế bounded retention tự động dọn dẹp staging cũ mà không xoá lịch sử giá hay dòng vết (lineage).
5. **Khởi tạo Schema & Dữ liệu tham chiếu cơ sở**:
   - Chạy lệnh bootstrap an toàn từ máy cá nhân (chỉ chạy một lần, có tính idempotent):
   ```bash
   # Thiết lập tạm DATABASE_URL trỏ tới Neon
   export DATABASE_URL="postgresql://<user>:<password>@ep-<project>-pooler.<region>.aws.neon.tech/neondb?sslmode=require"
   
   # Chạy bootstrap
   python scripts/bootstrap_cloud_db.py
   ```
   > **Lưu ý bảo mật**: Lệnh trên chỉ nạp mã chứng khoán chuẩn (FPT, VCB, MBB, MWG, HPG, VN100) và nguồn dữ liệu. **Tuyệt đối không tự động sao chép danh mục, sổ lệnh hay ghi chú cá nhân lên cloud**.

---

## 3. Bước 2 — Triển khai Backend trên Render

1. Đăng ký tài khoản tại [render.com](https://render.com).
2. Tạo Web Service mới: **New +** → **Web Service** → Kết nối repository Git cá nhân.
3. Cấu hình triển khai:
   - **Environment**: `Docker`
   - **Dockerfile Path**: `./Dockerfile` (sử dụng Dockerfile tại thư mục gốc)
   - **Instance Type**: `Free`
   - **Health Check Path**: `/health` (hoặc `/api/v1/health`)
4. Thiết lập các biến môi trường (**Environment Variables**) trên Render:

| Tên biến | Giá trị đề xuất | Ghi chú |
|---|---|---|
| `APP_ENV` | `production` | Bật chế độ production |
| `CLOUD_MODE` | `true` | Vô hiệu hoá SQLite, bắt buộc xác thực |
| `DATABASE_URL` | `postgresql://...@...neon.tech/neondb?sslmode=require` | Chuỗi Neon pooled connection |
| `DB_POOL_SIZE` | `5` | Giới hạn pool cho Neon Free (max 20 conn) |
| `DB_MAX_OVERFLOW` | `10` | Số kết nối tối đa khi cao điểm |
| `DB_POOL_RECYCLE` | `300` | Tái tạo kết nối mỗi 5 phút |
| `APP_AUTH_ENABLED` | `true` | Bắt buộc xác thực người dùng |
| `APP_AUTH_SECRET` | `openssl rand -hex 32` | Khóa bí mật ký session cookie |
| `APP_AUTH_PASSWORD_HASH` | Tạo qua helper | Hash PBKDF2 của mật khẩu đăng nhập |
| `CRON_SECRET` | `openssl rand -hex 32` | Khóa bí mật cho cron webhook |
| `ENABLE_IN_PROCESS_SCHEDULER` | `false` | Tắt vòng lặp nền trong RAM để tiết kiệm tài nguyên |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` | Domain Vercel được phép gọi API |
| `AI_ALLOW_PAID_APIS` | `false` | Khóa chặt ngân sách = 0 USD |
| `AI_MONTHLY_BUDGET_USD` | `0` | Không cho phép phát sinh chi phí |
| `GEMINI_API_KEY` | Key Gemini từ AI Studio | Key miễn phí của bạn |
| `GROQ_API_KEY` | Key Groq (tuỳ chọn) | Nếu muốn dùng fallback Groq |
| `OPENROUTER_API_KEY` | Key OpenRouter (tuỳ chọn) | Chỉ dùng model có hậu tố `:free` |
| `OLLAMA_ENABLED` | `false` | Mặc định tắt trên cloud (trừ khi có VPN riêng) |

> **Cách tạo mật khẩu ứng dụng**:
> Chạy lệnh sau trên terminal nội bộ để lấy hash:
> ```bash
> python -c "from services.auth.security import hash_password; print(hash_password('MatKhauCuaBan123@'))"
> ```
> Sao chép kết quả (bắt đầu bằng `pbkdf2_sha256$600000$...`) dán vào biến `APP_AUTH_PASSWORD_HASH`.

---

## 4. Bước 3 — Triển khai Frontend trên Vercel

1. Đăng ký tài khoản tại [vercel.com](https://vercel.com).
2. Nhập dự án: **Add New...** → **Project** → Chọn Git repository.
3. Thiết lập **Root Directory**: `apps/web`.
4. Framework Preset: `Next.js`.
5. Cấu hình biến môi trường trên Vercel:

| Tên biến | Giá trị |
|---|---|
| `INTERNAL_BACKEND_URL` | `https://your-backend.onrender.com` (URL backend Render vừa tạo) |
| `NEXT_PUBLIC_API_URL` | `https://your-backend.onrender.com` |

6. Bấm **Deploy**.
   - Mọi yêu cầu từ trình duyệt sẽ đi qua `https://your-app.vercel.app/api/v1/...` và được Vercel rewrite trực tiếp sang Render backend.
   - Session cookie được set với `SameSite=Strict`, `Path=/`, `HttpOnly`, `Secure` trên domain Vercel.

---

## 5. Bước 4 — Cấu hình Lịch chạy Tự động (cron-job.org)

Đăng ký tài khoản miễn phí tại [cron-job.org](https://cron-job.org).

### Job 1: Nạp Dữ liệu Thị trường Cuối ngày (EOD Ingestion)
- **Title**: `InvestIntel - EOD Ingestion`
- **URL**: `https://your-backend.onrender.com/api/v1/system/cron/run-ingestion`
- **Schedule**: Thứ 2 đến Thứ 6 hàng tuần, lúc **15:45 (Giờ Việt Nam UTC+7)** (sau khi HOSE đóng cửa phiên khớp lệnh định kỳ đóng cửa và giao dịch thoả thuận).
- **HTTP Method**: `POST`
- **HTTP Headers**:
  - `X-Cron-Secret`: `<giá trị biến CRON_SECRET>`
  - `Content-Type`: `application/json`
- **Body**: `{}`
- **Tính Idempotent**: Hệ thống gắn key `INGEST_EOD_YYYY-MM-DD`. Nếu chạy lại trong cùng ngày, backend tự động bỏ qua (trả về `ALREADY_COMPLETED`).

### Job 2: Báo cáo Phân tích Trí tuệ Nhân tạo (Daily Brief)
- **Title**: `InvestIntel - Daily Analyst Brief`
- **URL**: `https://your-backend.onrender.com/api/v1/system/cron/run-analyst`
- **Schedule**: Thứ 2 đến Thứ 6 hàng tuần, lúc **16:30 (Giờ Việt Nam UTC+7)** (sau khi dữ liệu giá và báo cáo đã được nạp và đối soát hoàn tất).
- **HTTP Method**: `POST`
- **HTTP Headers**:
  - `X-Cron-Secret`: `<giá trị biến CRON_SECRET>`
  - `Content-Type`: `application/json`
- **Body**: `{}`
- **Tính Idempotent**: Hệ thống gắn key `DAILY_BRIEF_YYYY-MM-DD`.

---

## 6. Quy trình Sao lưu & Phục hồi Cơ sở Dữ liệu

### 6.1 Sao lưu Định kỳ (Backup)
Chạy lệnh `pg_dump` từ máy cá nhân thông qua đường truyền bảo mật:

```bash
# Export schema và data dưới định dạng nén nhị phân custom
pg_dump "postgresql://<user>:<password>@ep-...neon.tech/neondb?sslmode=require" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="backup_investintel_$(date +%Y%m%d_%H%M%S).dump"
```

> **Nguyên tắc an toàn**:
> - Không commit file backup (`*.dump`, `*.sql`) vào Git.
> - Lưu trữ backup vào ổ cứng mã hóa (BitLocker / FileVault) hoặc dịch vụ private storage có mật khẩu.

### 6.2 Phục hồi Dữ liệu (Restore)
Để phục hồi vào cơ sở dữ liệu mới hoặc môi trường thử nghiệm:

```bash
# Phục hồi từ file backup
pg_restore \
  --dbname="postgresql://<user>:<password>@ep-...neon.tech/neondb?sslmode=require" \
  --clean \
  --if-exists \
  --no-owner \
  "backup_investintel_YYYYMMDD_HHMMSS.dump"
```

### 6.3 Kiểm tra Xác nhận Tính Toàn vẹn (Verification)
Sau khi phục hồi, chạy truy vấn kiểm tra số lượng bản ghi:
```sql
SELECT 
  (SELECT COUNT(*) FROM assets) AS total_assets,
  (SELECT COUNT(*) FROM prices) AS total_prices,
  (SELECT COUNT(*) FROM normalized_income) AS total_income_statements,
  (SELECT COUNT(*) FROM personal_portfolios) AS total_portfolios;
```

---

## 7. Danh mục Kiểm tra Khi Triển khai (Checklist)

### 7.1 Kiểm tra Triển khai Lần đầu (First Deploy)
- [ ] Neon PostgreSQL đã kết nối thành công với SSL (`sslmode=require`).
- [ ] Script `scripts/bootstrap_cloud_db.py` đã chạy hoàn tất và tạo đủ bảng.
- [ ] Biến `APP_AUTH_SECRET` và `APP_AUTH_PASSWORD_HASH` đã được cấu hình trên Render.
- [ ] Thử gọi API `/api/v1/portfolio` không có cookie -> nhận mã lỗi `401 Unauthorized`.
- [ ] Truy cập `/login` trên Vercel, nhập mật khẩu -> nhận cookie `investintel_session` (`HttpOnly`, `SameSite=Strict`, `Secure`).
- [ ] Sau khi đăng nhập, tải trang Dashboard hiển thị đúng dữ liệu.
- [ ] Cron endpoint `/api/v1/system/cron/run-ingestion` trả về `401` nếu thiếu `X-Cron-Secret` và `200/SUCCESS` khi có header hợp lệ.
- [ ] Gọi liên tiếp cron endpoint 2 lần -> lần 2 trả về `ALREADY_COMPLETED`.
- [ ] Bật chế độ ngủ trên Render -> kiểm tra frontend hiển thị Banner Cold-Start với nút thử lại an toàn.

### 7.2 Quy trình Hoàn tác (Rollback Plan)
Nếu phiên bản triển khai gặp lỗi:
1. **Frontend**: Vào Vercel Dashboard → mục **Deployments** → bấm nút ba chấm tại bản deploy ổn định gần nhất → chọn **Instant Rollback**.
2. **Backend**: Vào Render Dashboard → mục **Deploys** → chọn commit ổn định trước đó → bấm **Rollback to this deploy**.
3. **Database**: Nếu schema bị lỗi, sử dụng file `backup_*.dump` gần nhất để chạy lệnh `pg_restore` như hướng dẫn tại mục 6.2.
