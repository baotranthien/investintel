# tests/test_phase6f_local_monitoring_recovery.py
"""
Test Suite for Phase 6F: Local Monitoring, Logging & Self-Recovery
Verifies error classification, safe remediation rules, system observability page,
and recovery runbooks.
"""

import pytest
import sqlite3
import urllib.request
from fastapi.testclient import TestClient

from apps.api.main import app
from services.maintenance.self_recovery import (
    classify_error,
    ErrorCategory,
    ERROR_RUNBOOK,
)


def test_error_classification_mappings():
    """Verify runtime exceptions map to institutional error categories with remediation advice."""
    cases = [
        (ConnectionRefusedError("Connection refused on port 8000"), ErrorCategory.SERVICE_UNAVAILABLE),
        (sqlite3.DatabaseError("database disk image is malformed"), ErrorCategory.DATABASE_FAILURE),
        (TimeoutError("Ollama /api/generate timed out after 120s"), ErrorCategory.INFERENCE_TIMEOUT),
        (RuntimeError("External provider Entrade returned HTTP 503"), ErrorCategory.DATA_PROVIDER_FAILURE),
        (OSError("No space left on device: enospc"), ErrorCategory.STORAGE_FAILURE),
    ]
    for exc, expected_cat in cases:
        report = classify_error(exc)
        assert report["category"] == expected_cat.value
        assert report["severity"] in ("CRITICAL", "WARNING", "INFO")
        assert len(report["runbook_instruction"]) > 0
        assert len(report["safe_auto_recovery"]) > 0


def test_all_categories_have_runbooks():
    """Verify every ErrorCategory has a documented runbook entry."""
    for cat in ErrorCategory:
        if cat != ErrorCategory.UNKNOWN:
            assert cat in ERROR_RUNBOOK, f"Missing runbook entry for category: {cat}"
            entry = ERROR_RUNBOOK[cat]
            assert "severity" in entry
            assert "description" in entry
            assert "safe_auto_recovery" in entry
            assert "runbook_instruction" in entry


def test_system_observability_api_contract():
    """Verify /api/v1/system/diagnostics supplies complete data for the monitoring dashboard."""
    client = TestClient(app)
    resp = client.get("/api/v1/system/diagnostics")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["database"]["connected"] is True
    assert "hardware" in data
    assert "ollama_runtime" in data
    assert "scheduler" in data
    assert data["scheduler"]["timezone"] == "Asia/Ho_Chi_Minh"


def test_system_frontend_page_renders():
    """Verify Next.js frontend route /system returns HTTP 200 and loads successfully."""
    url = "http://localhost:3000/system"
    req = urllib.request.Request(url, headers={"User-Agent": "InvestIntel-Test/1.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    assert resp.status in (200, 307, 308)
    html = resp.read().decode("utf-8")
    assert "html" in html.lower()

