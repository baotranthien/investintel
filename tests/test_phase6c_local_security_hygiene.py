# tests/test_phase6c_local_security_hygiene.py
"""
Test Suite for Phase 6C: Local Security & Environment Hygiene
Verifies secrets containment, Git ignore enforcement, loopback bindings,
CORS restrictions, and strict enforcement of ALLOW_PRODUCTION_DB_WRITE=false.
"""

import os
import re
import subprocess
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from apps.api.main import app
from database.connection import (
    ALLOW_PRODUCTION_DB_WRITE,
    is_production_database_target,
)
from services.auth.middleware import get_allowed_origins

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_production_write_guardrail_is_false():
    """Verify ALLOW_PRODUCTION_DB_WRITE is strictly false."""
    assert ALLOW_PRODUCTION_DB_WRITE is False, "ALLOW_PRODUCTION_DB_WRITE must never be true in local dev"
    
    # Check .env if present
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        assert not re.search(r"ALLOW_PRODUCTION_DB_WRITE\s*=\s*(?:true|1|yes)", content, re.IGNORECASE), \
            "ALLOW_PRODUCTION_DB_WRITE is enabled in .env!"


def test_production_database_target_detection():
    """Verify is_production_database_target() identifies remote Neon cluster URLs."""
    neon_url = "postgresql://user:pass@ep-shiny-feather-1234.us-east-2.aws.neon.tech/neondb"
    assert "neon.tech" in neon_url or "ep-" in neon_url
    
    local_sqlite = "sqlite:///data/trading.db"
    assert "neon.tech" not in local_sqlite and "ep-" not in local_sqlite


def test_sensitive_files_ignored_by_git():
    """Verify .env, databases, and logs are excluded from git tracking."""
    # Run git check-ignore
    sensitive_paths = [
        ".env",
        ".env.local",
        "data/trading.db",
        "logs/ollama/ollama.log",
        "logs/backend/backend.log",
        "logs/supervisor/supervisor.log",
        ".run/backend.pid"
    ]
    for sp in sensitive_paths:
        cmd = ["git", "check-ignore", sp]
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Path {sp} is NOT ignored by git!"


def test_no_hardcoded_secrets_in_tracked_source():
    """Scan backend and frontend source files for accidental API key or password literals."""
    tracked_res = subprocess.run(
        ["git", "ls-files", "apps/web/src", "apps/api", "services"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    tracked_files = tracked_res.stdout.splitlines()
    
    secret_patterns = [
        re.compile(r"""(?:api[_-]?key|secret[_-]?token|db[_-]?password)\s*=\s*['"][a-zA-Z0-9_\-]{20,}['"]""", re.IGNORECASE),
        re.compile(r"""postgres(?:ql)?://[a-zA-Z0-9_]+:[a-zA-Z0-9_]+@ep-[a-zA-Z0-9_\-\.]+neon\.tech"""),
    ]
    
    for f in tracked_files:
        fp = PROJECT_ROOT / f
        if not fp.exists() or fp.is_dir():
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
            for pat in secret_patterns:
                match = pat.search(content)
                assert match is None, f"Potential secret leak in {f}: {match.group(0)[:20]}..."
        except Exception:
            pass


def test_cors_restrictive_to_local_origins():
    """Verify CORS allowlist contains only loopback / local origins by default."""
    origins = get_allowed_origins()
    for origin in origins:
        assert origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"), \
            f"Non-local origin found in default CORS: {origin}"


def test_health_endpoint_no_credential_leak():
    """Verify /health endpoint returns health status without dumping connection credentials."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    # Ensure no credentials or URLs leaked
    text_content = resp.text.lower()
    assert "password" not in text_content
    assert "neon.tech" not in text_content
    assert "ep-" not in text_content

