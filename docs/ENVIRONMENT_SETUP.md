# ENVIRONMENT SETUP & RECOVERY GUIDE

**Date:** 2026-09-30  
**Target Architecture:** Personal Investment Intelligence Platform  
**System Operating Mode:** Local development fallback (Native Python + SQLite / Local PostgreSQL) with Docker Production target.

---

## 1. HOST AUDIT STATUS

A full audit of the current host machine was executed:

| Tool | Status | Binary Path / Version | Notes |
|------|--------|-----------------------|-------|
| **Python** | ✅ Available | `C:\Users\baotr\AppData\Local\Programs\Python\Python310\python.exe` (3.10.6) | Runtime ready |
| **Node.js** | ✅ Available | `C:\Program Files\nodejs\node.exe` (v24.14.0) | Runtime ready |
| **npm** | ✅ Available | `C:\Program Files\nodejs\npm.ps1` (11.1.0) | Package manager ready |
| **Docker** | ❌ Not Found | Not installed on host PATH | Blocked |
| **Docker Compose**| ❌ Not Found | Not installed on host PATH | Blocked |
| **psql / Postgres**| ❌ Not Found | Not running as a background service on host | Blocked |
| **Redis** | ❌ Not Found | Not installed on host PATH | In-memory fallback |
| **Ollama** | ❌ Not Found | Not detected on `localhost:11434` | Fallback mode |

---

## 2. DUAL-TARGET ENVIRONMENT STRATEGY

To prevent artificial simulation while preserving architectural integrity:

1. **Production Target (Docker Compose):**
   - Defined in [docker-compose.yml](file:///c:/Users/baotr/Downloads/trading/docker-compose.yml).
   - PostgreSQL 16 on port `5432` with pgvector.
   - Redis 7 on port `6379`.
   - Python FastAPI API on port `8766`.
   - Next.js Web on port `3000`.

2. **Native Development Fallback (Running Now):**
   - **Database:** SQLAlchemy dual-engine support.
     - When `DATABASE_URL` is set to `postgresql://...`, uses PostgreSQL via `psycopg2`.
     - When `DATABASE_URL` is unset or `NOT_CONFIGURED`, falls back safely to local persistent SQLite at `sqlite:///./data/trading.db`.
     - When PostgreSQL is explicitly configured but unreachable, startup fails with an error instead of silently switching databases.
     - Schema and migrations are 100% identical and managed via **Alembic**.
   - **Cache:** In-memory dictionary fallback when Redis is unreachable.
   - **AI:** Graceful degradation reporting `available: false` when Ollama is offline.

---

## 3. PREREQUISITES & INSTALLATION COMMANDS

### Option A: Complete Docker Setup (Recommended for Full Production)
1. Install **Docker Desktop for Windows** with WSL2 backend.
2. Clone repository and start containers:
   ```powershell
   docker compose up -d
   ```
3. Run Alembic migrations inside container:
   ```powershell
   docker compose exec api alembic upgrade head
   ```

### Option B: Native Windows Setup (Current Operating Mode)
1. Ensure Python dependencies are installed:
   ```powershell
   pip install sqlalchemy alembic psycopg2-binary pydantic httpx pytest fastapi uvicorn
   ```
2. Run database migrations:
   ```powershell
   alembic upgrade head
   ```
   Alembic uses the configured `DATABASE_URL` (the local SQLite fallback applies only when PostgreSQL is not explicitly configured).
3. Ingest seed / market data:
   ```powershell
   python -m services.ingestion
   ```
4. Start FastAPI Backend:
   ```powershell
   uvicorn apps.api.main:app --host 127.0.0.1 --port 8766 --reload
   ```
5. Start Next.js Frontend:
   ```powershell
   cd apps/web
   npm run dev
   ```

---

## 4. PORTS & ENVIRONMENT VARIABLES

### Default Ports
- **FastAPI Backend:** `8766`
- **Next.js Web Frontend:** `3000`
- **PostgreSQL Database:** `5432`
- **Redis Cache:** `6379`
- **Ollama Local AI:** `11434`

### Required & Optional Environment Variables (`.env`)
```bash
# Database: PostgreSQL in Docker, or SQLite file in native mode
DATABASE_URL=sqlite:///./data/trading.db
# For PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/investment

# Cache:
REDIS_URL=redis://localhost:6379/0

# Ingestion API Keys (Free / Public):
FRED_API_KEY=your_fred_api_key_here
BLS_API_KEY=your_bls_api_key_here

# Local AI (Ollama):
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 5. TROUBLESHOOTING

1. **`DATABASE_URL` connection error:**
   - If using PostgreSQL: Verify the service, database name, username, and password in `DATABASE_URL` (`Get-Service -Name *postgres*`).
   - To intentionally use local SQLite, unset `DATABASE_URL` or set it to `NOT_CONFIGURED`; an unreachable PostgreSQL URL will not fall back.
   - If using SQLite: Ensure `data/` directory exists and has write permissions.

2. **Alembic migration conflicts:**
   - Run `alembic current` to check active revision.
   - Run `alembic heads` to ensure single branch head.

3. **Ollama connection refused:**
   - Verify Ollama is running (`ollama serve` or desktop app running on port 11434).
   - If Ollama is offline, API continues to function normally with AI status set to `available: false`.
