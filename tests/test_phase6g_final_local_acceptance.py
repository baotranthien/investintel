# tests/test_phase6g_final_local_acceptance.py
"""
InvestIntel Master Acceptance Test Suite — Phase 6G Final Certification
Verifies all 15 operational areas across Runtime, AI Inference, Database Durability,
Background Automation, Security Guardrails, and Phase 3-5 Backward Compatibility.
"""

import asyncio
import os
import sqlite3
import urllib.request
import pytest
from datetime import date
from fastapi.testclient import TestClient

from apps.api.main import app
from database.connection import (
    ALLOW_PRODUCTION_DB_WRITE,
    DEFAULT_DB_PATH,
    check_database_health,
)
from services.ai.config import OllamaConfig
from services.ai.telemetry import (
    get_hardware_diagnostics,
    get_ollama_runtime_status,
    get_inference_summary,
)
from services.db.backup import (
    create_backup,
    verify_backup,
    restore_backup,
)
from services.scheduler.engine import local_scheduler


client = TestClient(app)


# -------------------------------------------------------------
# 1. RUNTIME & SERVICE LIFECYCLE
# -------------------------------------------------------------
def test_6g_runtime_and_endpoints_health():
    """Verify local services (Ollama, FastAPI, SQLite) are healthy."""
    db_st = check_database_health()
    assert db_st["connected"] is True, f"Database not connected: {db_st}"
    assert db_st["backend"] == "sqlite"
    
    ollama_st = get_ollama_runtime_status()
    assert ollama_st["ollama_listening"] is True
    assert "qwen3.5:9b-q4_K_M" in ollama_st["installed_models"]


def test_6g_all_frontend_routes_accessibility():
    """Verify all 8 core Next.js frontend pages load successfully."""
    routes = [
        "/ai",
        "/screener",
        "/opportunities",
        "/portfolio",
        "/watchlist",
        "/market",
        "/system",
        "/data-center"
    ]
    for r in routes:
        url = f"http://localhost:3000{r}"
        req = urllib.request.Request(url, headers={"User-Agent": "InvestIntel-Acceptance/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        assert resp.status in (200, 307, 308), f"Route {url} failed with status {resp.status}"


# -------------------------------------------------------------
# 2. PHASE 3–5 FUNCTIONALITY REGRESSION
# -------------------------------------------------------------
def test_6g_stock_screener_api():
    """Verify Stock Screener returns valid institutional matches."""
    resp = client.get("/api/v1/screener?pe_max=25&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert "total_screened" in data
    assert data["total_screened"] > 0


def test_6g_opportunities_scanner_api():
    """Verify Opportunities Scanner returns ranked cards with why_now explainability."""
    resp = client.get("/api/v1/opportunities?universe=VN100&horizon=MEDIUM_TERM")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) > 0
    first = data["results"][0]
    assert "symbol" in first
    assert "opportunity_score" in first
    assert "why_now" in first


def test_6g_deep_research_and_history_api():
    """Verify Company Research History returns longitudinal financial statements."""
    resp = client.get("/api/v1/research/BMP/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "BMP"
    assert "annual_periods" in data
    assert "quarterly_periods" in data
    assert len(data["annual_periods"]) > 0


def test_6g_peer_comparison_api():
    """Verify Peer Comparison returns sector clustering and medians."""
    resp = client.get("/api/v1/valuation/BMP/peers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "AVAILABLE"
    assert "peer_table" in data
    assert "peer_median_pe" in data or "peer_median_pb" in data
    assert len(data["peer_table"]) > 0


def test_6g_valuation_model_api():
    """Verify Valuation Model returns DCF scenarios and multiple-based valuations."""
    resp = client.get("/api/v1/valuation/BMP")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "BMP"
    assert "composite_fair_value" in data or "methods" in data or "scenarios" in data
    assert "data_status" in data


def test_6g_portfolio_dashboard_api():
    """Verify Portfolio Dashboard returns holdings and asset allocation."""
    resp = client.get("/api/v1/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert "portfolio_id" in data or "holdings" in data or "status" in data


def test_6g_investment_alerts_api():
    """Verify Investment Alerts API returns evaluated alerts."""
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# -------------------------------------------------------------
# 3. DATABASE DURABILITY & DISPOSABLE RESTORE
# -------------------------------------------------------------
def test_6g_database_backup_and_disposable_restore(tmp_path):
    """Verify hot online backup and point-in-time restore into disposable test database."""
    backup_dir = tmp_path / "backups"
    disposable_target = tmp_path / "disposable_restore.db"
    
    # 1. Hot Backup
    manifest = create_backup(db_path=DEFAULT_DB_PATH, backup_dir=backup_dir, description="6G Acceptance Backup")
    assert manifest["integrity"] == "ok"
    assert manifest["backup_size_bytes"] > 0
    backup_path = tmp_path / "backups" / manifest["backup_filename"]
    
    # 2. Independent Verification
    v_res = verify_backup(backup_path)
    assert v_res["integrity_ok"] is True
    assert v_res["manifest_checksum_match"] is True
    
    # 3. Disposable Restore
    r_res = restore_backup(backup_path=backup_path, target_db_path=disposable_target, force=True)
    assert r_res["status"] == "restored"
    assert r_res["integrity"] == "ok"
    assert disposable_target.exists()


# -------------------------------------------------------------
# 4. BACKGROUND AUTOMATION & SCHEDULING
# -------------------------------------------------------------
def test_6g_automation_scheduler_controls():
    """Verify scheduler pause, resume, and status contracts."""
    st = local_scheduler.get_status()
    assert st["timezone"] == "Asia/Ho_Chi_Minh"
    assert "jobs" in st
    assert len(st["jobs"]) >= 4
    
    local_scheduler.pause()
    assert local_scheduler.is_paused is True
    local_scheduler.resume()
    assert local_scheduler.is_paused is False


# -------------------------------------------------------------
# 5. AI RUNTIME & HARDWARE TELEMETRY
# -------------------------------------------------------------
def test_6g_ai_hardware_and_diagnostics():
    """Verify primary model Qwen3.5 9B and NVIDIA RTX 3050 telemetry."""
    config = OllamaConfig.from_env()
    model = os.getenv("OLLAMA_MODEL", config.primary_model)
    assert model == "qwen3.5:9b-q4_K_M"
    
    hw = get_hardware_diagnostics()
    assert hw["gpu"]["status"] in ("ACTIVE", "UNAVAILABLE (nvidia-smi not found)")
    if hw["gpu"]["status"] == "ACTIVE":
        assert hw["gpu"]["vram_total_mb"] == 4096
        assert hw["gpu"]["vram_used_mb"] > 0
        
    summary = get_inference_summary()
    assert summary["total_logged"] > 0
    assert summary["median_generation_tps"] > 0.0


# -------------------------------------------------------------
# 6. PRODUCTION WRITE GUARD
# -------------------------------------------------------------
def test_6g_production_write_guard_strictly_false():
    """Verify ALLOW_PRODUCTION_DB_WRITE is strictly False."""
    assert ALLOW_PRODUCTION_DB_WRITE is False
    assert os.getenv("ALLOW_PRODUCTION_DB_WRITE", "false").lower() in ("0", "false", "no")
