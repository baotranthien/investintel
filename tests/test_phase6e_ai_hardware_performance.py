# tests/test_phase6e_ai_hardware_performance.py
"""
Test Suite for Phase 6E: Qwen, Hardware & Performance Optimization
Verifies primary model preservation, GPU/VRAM telemetry, inference metrics logging,
and diagnostics endpoint contract.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.ai.config import OllamaConfig
from services.ai.telemetry import (
    get_hardware_diagnostics,
    get_ollama_runtime_status,
    get_inference_summary,
    METRICS_LOG,
)


def test_primary_model_preservation():
    """Verify primary model is strictly preserved as qwen3.5:9b-q4_K_M."""
    config = OllamaConfig.from_env()
    model = os.getenv("OLLAMA_MODEL", config.primary_model)
    assert model == "qwen3.5:9b-q4_K_M", f"Primary model must remain qwen3.5:9b-q4_K_M, got: {model}"


def test_hardware_diagnostics_telemetry():
    """Verify hardware diagnostics collects GPU, VRAM, and RAM telemetry without fake zero values."""
    hw = get_hardware_diagnostics()
    assert "timestamp" in hw
    assert "gpu" in hw
    assert "system_ram" in hw
    
    gpu = hw["gpu"]
    assert gpu["status"] in ("ACTIVE", "UNAVAILABLE (nvidia-smi not found)")
    if gpu["status"] == "ACTIVE":
        assert "RTX 3050" in gpu["name"] or "NVIDIA" in gpu["name"]
        assert gpu["vram_total_mb"] == 4096
        assert gpu["vram_used_mb"] > 0
        assert gpu["vram_free_mb"] > 0
        assert gpu["temperature_c"] is not None

    ram = hw["system_ram"]
    assert ram["total_mb"] is not None and ram["total_mb"] > 8000
    assert ram["available_mb"] is not None
    assert ram["used_pct"] is not None


def test_ollama_runtime_status():
    """Verify Ollama runtime status detects models and listening state."""
    status = get_ollama_runtime_status()
    assert status["ollama_listening"] is True
    assert "qwen3.5:9b-q4_K_M" in status["installed_models"]


def test_inference_telemetry_metrics_logged():
    """Verify inference telemetry log file exists and contains valid performance metrics."""
    assert METRICS_LOG.exists(), "logs/ollama_metrics.jsonl should exist after benchmark"
    summary = get_inference_summary()
    assert summary["total_logged"] >= 1
    assert summary["median_generation_tps"] > 0.0
    assert summary["median_ttft_sec"] > 0.0
    
    last = summary["last_record"]
    assert last is not None
    assert last["model"] == "qwen3.5:9b-q4_K_M"
    assert "generation_tps" in last
    assert "ttft_sec" in last


def test_system_diagnostics_endpoint():
    """Verify /api/v1/system/diagnostics returns combined database, hardware, and AI telemetry."""
    client = TestClient(app)
    resp = client.get("/api/v1/system/diagnostics")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "database" in data
    assert "hardware" in data
    assert "ollama_runtime" in data
    assert "inference_telemetry" in data
    assert "scheduler" in data
    
    assert data["database"]["connected"] is True
    assert data["ollama_runtime"]["ollama_listening"] is True
    assert data["hardware"]["gpu"]["status"] in ("ACTIVE", "UNAVAILABLE (nvidia-smi not found)")

