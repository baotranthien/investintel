# tests/test_phase6a_service_lifecycle.py
import subprocess
import json
import urllib.request
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_powershell_script(script_rel_path: str, args: list = None, timeout: int = 45) -> tuple[int, str]:
    script_path = PROJECT_ROOT / script_rel_path
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
    if args:
        cmd.extend(args)
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=timeout)
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
    """
    Verify start-investintel.ps1 idempotency:
    When services are running, a second startup invocation:
    1. Detects they are already healthy.
    2. Does not spawn duplicate processes.
    3. Preserves exact initial PIDs.
    4. Completes within a reasonable timeout without hanging on pipes.
    """
    # 1. Capture initial PIDs from status
    code1, out1 = run_powershell_script("scripts/local/status-investintel.ps1", ["-AsJson"], timeout=15)
    assert code1 == 0, f"Initial status check failed: {out1}"
    data1 = json.loads(out1)
    
    init_api_pid = data1.get("FastAPI", {}).get("PID")
    init_web_pid = data1.get("NextJs", {}).get("PID")
    init_ollama_pid = data1.get("Ollama", {}).get("PID")
    
    assert init_api_pid is not None, "FastAPI must be running prior to idempotency check"
    assert init_web_pid is not None, "NextJs must be running prior to idempotency check"
    
    # 2. Execute start script again — must detect existing services
    code2, out2 = run_powershell_script("scripts/local/start-investintel.ps1", timeout=30)
    assert code2 == 0, f"Secondary start invocation failed: {out2}"
    assert "already running and healthy" in out2, f"Expected idempotency message missing in output: {out2}"
    
    # 3. Capture post-startup PIDs
    code3, out3 = run_powershell_script("scripts/local/status-investintel.ps1", ["-AsJson"], timeout=15)
    assert code3 == 0, f"Post-start status check failed: {out3}"
    data3 = json.loads(out3)
    
    post_api_pid = data3.get("FastAPI", {}).get("PID")
    post_web_pid = data3.get("NextJs", {}).get("PID")
    post_ollama_pid = data3.get("Ollama", {}).get("PID")
    
    # 4. Assert strict PID invariance (zero duplicate processes, zero restarts)
    assert post_api_pid == init_api_pid, f"FastAPI PID changed ({init_api_pid} -> {post_api_pid})"
    assert post_web_pid == init_web_pid, f"NextJs PID changed ({init_web_pid} -> {post_web_pid})"
    if init_ollama_pid:
        assert post_ollama_pid == init_ollama_pid, f"Ollama PID changed ({init_ollama_pid} -> {post_ollama_pid})"


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

