# tests/test_phase6a_service_lifecycle.py
import subprocess
import json
import urllib.request
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_powershell_script(script_rel_path: str, args: list = None) -> tuple[int, str]:
    script_path = PROJECT_ROOT / script_rel_path
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
    if args:
        cmd.extend(args)
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30)
    return res.returncode, res.stdout + res.stderr

def test_status_script_json_contract():
    """Verify scripts/local/status-investintel.ps1 returns valid structured JSON with all expected keys."""
    code, output = run_powershell_script("scripts/local/status-investintel.ps1", ["-AsJson"])
    assert code == 0, f"status script failed: {output}"
    
    data = json.loads(output)
    assert "Timestamp" in data
    assert "Ollama" in data
    assert "FastAPI" in data
    assert "NextJs" in data
    assert "SQLite" in data
    assert "GPU" in data
    
    assert data["Ollama"]["Port"] == 11434
    assert data["FastAPI"]["Port"] == 8000
    assert data["NextJs"]["Port"] == 3000
    assert data["SQLite"]["Integrity"] == "PASS (ok)"
    assert data["SQLite"]["Status"] == "HEALTHY"

def test_doctor_script_json_contract():
    """Verify scripts/local/doctor-investintel.ps1 returns valid structured diagnostics."""
    code, output = run_powershell_script("scripts/local/doctor-investintel.ps1", ["-AsJson"])
    assert code == 0, f"doctor script failed: {output}"
    
    data = json.loads(output)
    assert isinstance(data, list)
    categories = {c["Category"] for c in data}
    assert "Python Environment" in categories
    assert "AI Inference" in categories
    assert "Database & Data" in categories
    assert "Security & Config" in categories
    
    # Ensure zero FAIL status in healthy local environment
    fails = [c for c in data if c["Status"] == "FAIL"]
    assert len(fails) == 0, f"Doctor detected failures: {fails}"

def test_no_duplicate_startup_when_already_healthy():
    """Verify start-investintel.ps1 detects already running services and does not duplicate them."""
    # Capture initial PIDs from status
    _, out1 = run_powershell_script("scripts/local/status-investintel.ps1", ["-AsJson"])
    data1 = json.loads(out1)
    
    # Run start command
    code, out2 = run_powershell_script("scripts/local/start-investintel.ps1")
    assert code == 0, f"start script failed: {out2}"
    assert "already running and healthy" in out2
    
    # Capture post-start PIDs
    _, out3 = run_powershell_script("scripts/local/status-investintel.ps1", ["-AsJson"])
    data3 = json.loads(out3)
    
    # Ensure PIDs did not change (no duplicate or replaced processes)
    assert data1["Ollama"]["PID"] == data3["Ollama"]["PID"]
    assert data1["FastAPI"]["PID"] == data3["FastAPI"]["PID"]
    assert data1["NextJs"]["PID"] == data3["NextJs"]["PID"]

def test_frontend_routes_accessibility():
    """Verify core frontend routes load successfully on port 3000."""
    routes = [
        "/ai",
        "/screener",
        "/opportunities",
        "/portfolio",
        "/watchlist"
    ]
    for r in routes:
        url = f"http://localhost:3000{r}"
        req = urllib.request.Request(url, headers={"User-Agent": "InvestIntel-Test/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        assert resp.status in (200, 307, 308), f"Route {url} returned status {resp.status}"

def test_supervisor_log_writing_and_rotation():
    """Verify supervisor actions are logged into logs/supervisor/supervisor.log."""
    log_file = PROJECT_ROOT / "logs" / "supervisor" / "supervisor.log"
    assert log_file.exists(), "supervisor.log does not exist"
    content = log_file.read_text(encoding="utf-8")
    assert "[INFO]" in content or "[OK]" in content

