# InvestIntel Local Services Supervision Architecture & Runbook

This document defines the stable service lifecycle and exact verification procedures for running InvestIntel locally.

## 1. Verified Local Service Topology

| Service | Host & Port | Executable / Runtime | Health Verification | Working Directory |
| :--- | :--- | :--- | :--- | :--- |
| **Ollama Local LLM** | `http://127.0.0.1:11434` | `C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe` | `GET /api/tags` -> contains `qwen3.5:9b-q4_K_M` | Workspace Root |
| **FastAPI Backend** | `http://127.0.0.1:8000` | `.\.venv\Scripts\python.exe` (Python 3.10.6) | `GET /health` -> `{"status": "ok"}` | Workspace Root (`C:\Users\baotr\Downloads\trading`) |
| **Next.js Web UI** | `http://localhost:3000` | Node.js 20+ / `npm --prefix apps/web run dev` | `GET /ai` -> HTTP 200 | `apps/web` |

---

## 2. Startup Procedures & Commands

### 2.1 Ollama Local LLM Server
```powershell
# 1. Check if port is already active:
Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue

# 2. Start daemon if not running:
& "C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe" serve

# 3. Health & Model Verification:
& ".\.venv\Scripts\python.exe" -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:11434/api/tags'); print([m['name'] for m in json.loads(res.read())['models']])"
```

### 2.2 FastAPI Backend Server
```powershell
# 1. Check if port is already active:
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

# 2. Start Uvicorn daemon using project .venv:
& ".\.venv\Scripts\python.exe" -m uvicorn apps.api.main:app --port 8000 --reload

# 3. Health & Database Verification:
& ".\.venv\Scripts\python.exe" -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:8000/health'); print(json.loads(res.read()))"
```

### 2.3 Next.js Web UI
```powershell
# 1. Check if port is already active:
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue

# 2. Start Next.js Turbopack dev server:
npm --prefix apps/web run dev

# 3. Verification:
& ".\.venv\Scripts\python.exe" -c "import urllib.request; print(urllib.request.urlopen('http://localhost:3000/ai').status)"
```

---

## 3. Safe Shutdown Procedures

```powershell
# Stop FastAPI on port 8000:
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force }

# Stop Next.js on port 3000:
$conn = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force }

# Stop Ollama on port 11434:
$conn = Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force }
```

---

## 4. Production Safety Policy
- `ALLOW_PRODUCTION_DB_WRITE=false` is enforced at all times.
- Zero writes to Neon PostgreSQL production database.
- Local SQLite database and transaction-isolated pytest fixtures only.

