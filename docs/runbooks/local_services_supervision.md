# InvestIntel Local Services Supervision Runbook

This document defines the exact commands and supervision procedures for running InvestIntel locally.

## 1. Service Map & Ports

| Service | Host & Port | Environment / Executable | Health Endpoint | Working Directory |
| :--- | :--- | :--- | :--- | :--- |
| **Ollama** | `http://127.0.0.1:11434` | `C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe` (or `where.exe ollama`) | `GET /api/tags` | Root |
| **FastAPI Backend** | `http://127.0.0.1:8000` | `.\.venv\Scripts\python.exe` (Python 3.10.6) | `GET /health` | Root (`C:\Users\baotr\Downloads\trading`) |
| **Next.js Web UI** | `http://localhost:3000` | Node.js / `npm` (Next.js 16 Turbopack) | `GET /` | `apps/web` |

---

## 2. Startup Procedures

### 2.1 Ollama Local LLM Server
```powershell
# Check if port is already listening:
Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue

# Start Ollama daemon:
& "C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe" serve

# Verify model availability:
& ".\.venv\Scripts\python.exe" -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:11434/api/tags'); print([m['name'] for m in json.loads(res.read())['models']])"
# Expected: includes 'qwen3.5:9b-q4_K_M'
```

### 2.2 FastAPI Backend
```powershell
# Always execute from workspace root with project .venv
& ".\.venv\Scripts\python.exe" -m uvicorn apps.api.main:app --port 8000 --reload

# Verification:
& ".\.venv\Scripts\python.exe" -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:8000/health'); print(json.loads(res.read()))"
# Expected: {'status': 'ok'}
```

### 2.3 Next.js Frontend
```powershell
npm --prefix apps/web run dev

# Verification:
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
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
- `ALLOW_PRODUCTION_DB_WRITE=false` is enforced across all environments.
- Zero writes to Neon PostgreSQL production database.
- Local tests use SQLite or isolated pytest databases.
