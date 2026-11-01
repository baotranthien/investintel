"""
InvestIntel AI & Hardware Telemetry Engine
Phase 6E: Performance Profiling, Hardware Metrics, VRAM Monitoring, and Inference Telemetry.
Primary Model: qwen3.5:9b-q4_K_M
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
METRICS_LOG = PROJECT_ROOT / "logs" / "ollama_metrics.jsonl"


def get_hardware_diagnostics() -> Dict[str, Any]:
    """
    Collects real-time hardware diagnostics (GPU, VRAM, RAM).
    Gracefully handles missing GPU/nvidia-smi without fake zero values.
    """
    gpu_data: Dict[str, Any] = {
        "status": "UNKNOWN",
        "name": None,
        "vram_total_mb": None,
        "vram_used_mb": None,
        "vram_free_mb": None,
        "utilization_pct": None,
        "temperature_c": None,
    }

    # 1. Query NVIDIA GPU via nvidia-smi
    nvidia_smi = "C:\\Windows\\System32\\nvidia-smi.exe"
    if os.path.exists(nvidia_smi):
        try:
            cmd = [
                nvidia_smi,
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 6:
                    gpu_data["status"] = "ACTIVE"
                    gpu_data["name"] = parts[0]
                    gpu_data["vram_total_mb"] = int(parts[1])
                    gpu_data["vram_used_mb"] = int(parts[2])
                    gpu_data["vram_free_mb"] = int(parts[3])
                    gpu_data["utilization_pct"] = int(parts[4])
                    gpu_data["temperature_c"] = int(parts[5])
        except Exception as e:
            gpu_data["status"] = f"ERROR ({e})"
    else:
        gpu_data["status"] = "UNAVAILABLE (nvidia-smi not found)"

    # 2. Query System RAM via Python / OS
    ram_data: Dict[str, Any] = {
        "total_mb": None,
        "available_mb": None,
        "used_pct": None,
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_data["total_mb"] = round(vm.total / (1024 * 1024), 1)
        ram_data["available_mb"] = round(vm.available / (1024 * 1024), 1)
        ram_data["used_pct"] = vm.percent
    except ImportError:
        # Fallback using Windows WMIC / PowerShell if psutil not present
        try:
            ps_cmd = ["powershell.exe", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem) | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"]
            ps_res = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=3)
            if ps_res.returncode == 0:
                data = json.loads(ps_res.stdout)
                total_kb = data.get("TotalVisibleMemorySize", 0)
                free_kb = data.get("FreePhysicalMemory", 0)
                ram_data["total_mb"] = round(total_kb / 1024, 1)
                ram_data["available_mb"] = round(free_kb / 1024, 1)
                if total_kb > 0:
                    ram_data["used_pct"] = round(((total_kb - free_kb) / total_kb) * 100, 1)
        except Exception:
            pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gpu": gpu_data,
        "system_ram": ram_data,
    }


def get_ollama_runtime_status() -> Dict[str, Any]:
    """
    Checks active models loaded in VRAM via Ollama /api/ps and installed models.
    """
    result: Dict[str, Any] = {
        "ollama_listening": False,
        "primary_model": os.getenv("OLLAMA_MODEL", "qwen3.5:9b-q4_K_M"),
        "loaded_models": [],
        "installed_models": [],
    }

    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

    # Check installed models
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "InvestIntel/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result["ollama_listening"] = True
            result["installed_models"] = [m["name"] for m in data.get("models", [])]
    except Exception:
        result["ollama_listening"] = False
        return result

    # Check active models in VRAM via /api/ps (Ollama v0.1.33+)
    try:
        req = urllib.request.Request(f"{base_url}/api/ps", headers={"User-Agent": "InvestIntel/1.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("models", []):
                result["loaded_models"].append({
                    "name": m.get("name"),
                    "size_vram_mb": round(m.get("size_vram", 0) / (1024 * 1024), 1),
                    "size_total_mb": round(m.get("size", 0) / (1024 * 1024), 1),
                    "expires_at": m.get("expires_at"),
                })
    except Exception:
        pass

    return result


def record_inference_telemetry(meta: Dict[str, Any], prompt_length: int = 0) -> Dict[str, Any]:
    """
    Computes tokens per second (TPS) and latency metrics from Ollama response metadata
    and appends to logs/ollama_metrics.jsonl.
    """
    METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)

    eval_count = meta.get("eval_count") or 0
    eval_duration_ns = meta.get("eval_duration_ns") or 0
    prompt_eval_count = meta.get("prompt_eval_count") or 0
    prompt_eval_duration_ns = meta.get("prompt_eval_duration_ns") or 0
    total_duration_ns = meta.get("total_duration_ns") or 0
    load_duration_ns = meta.get("load_duration_ns") or 0

    generation_tps = round(eval_count / (eval_duration_ns / 1e9), 2) if eval_duration_ns > 0 else 0.0
    prompt_eval_tps = round(prompt_eval_count / (prompt_eval_duration_ns / 1e9), 2) if prompt_eval_duration_ns > 0 else 0.0
    total_duration_sec = round(total_duration_ns / 1e9, 3)
    ttft_sec = round((load_duration_ns + prompt_eval_duration_ns) / 1e9, 3)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": meta.get("model", "qwen3.5:9b-q4_K_M"),
        "total_duration_sec": total_duration_sec,
        "ttft_sec": ttft_sec,
        "generation_tps": generation_tps,
        "prompt_eval_tps": prompt_eval_tps,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "prompt_length_chars": prompt_length,
    }

    try:
        with open(METRICS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"Failed to append inference telemetry: {e}")

    return record


def get_inference_summary() -> Dict[str, Any]:
    """
    Calculates aggregate performance telemetry (median TPS, median TTFT, total inferences).
    """
    if not METRICS_LOG.exists():
        return {
            "total_logged": 0,
            "median_generation_tps": 0.0,
            "median_ttft_sec": 0.0,
            "last_record": None,
        }

    records = []
    try:
        with open(METRICS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line.strip()))
    except Exception:
        pass

    if not records:
        return {
            "total_logged": 0,
            "median_generation_tps": 0.0,
            "median_ttft_sec": 0.0,
            "last_record": None,
        }

    tps_values = sorted([r["generation_tps"] for r in records if r.get("generation_tps", 0) > 0])
    ttft_values = sorted([r["ttft_sec"] for r in records if r.get("ttft_sec", 0) > 0])

    median_tps = tps_values[len(tps_values) // 2] if tps_values else 0.0
    median_ttft = ttft_values[len(ttft_values) // 2] if ttft_values else 0.0

    return {
        "total_logged": len(records),
        "median_generation_tps": median_tps,
        "median_ttft_sec": median_ttft,
        "last_record": records[-1] if records else None,
    }


def run_local_benchmark(model: str = "qwen3.5:9b-q4_K_M") -> Dict[str, Any]:
    """
    Runs a reproducible local benchmark with a standard financial diagnostic prompt.
    Captures TTFT, generation TPS, VRAM, and total duration.
    """
    from services.ai.config import OllamaConfig
    from services.ai.providers import OllamaProvider
    import asyncio

    test_prompt = (
        "Analyze the following financial metrics for BMP (Binh Minh Plastics): "
        "Revenue 2024: 5,142B VND, Net Income: 1,041B VND, Net Margin: 20.2%, "
        "ROE: 38.4%, Debt-to-Equity: 0.12x. "
        "Provide a concise 3-sentence institutional assessment."
    )

    t0 = time.time()
    config = OllamaConfig(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        primary_model=model,
        timeout_seconds=60.0,
        num_ctx=2048,
        num_predict=256,
        think=False,
    )
    provider = OllamaProvider(config=config)

    # Capture pre-inference hardware
    hw_before = get_hardware_diagnostics()

    # Run inference
    async def _execute():
        return await provider._generate_result(prompt=test_prompt)

    text, meta = asyncio.run(_execute())
    total_time = round(time.time() - t0, 3)

    # Capture post-inference hardware
    hw_after = get_hardware_diagnostics()
    telemetry = record_inference_telemetry(meta, prompt_length=len(test_prompt))

    return {
        "model": model,
        "prompt_chars": len(test_prompt),
        "response_chars": len(text),
        "total_wall_time_sec": total_time,
        "generation_tps": telemetry["generation_tps"],
        "prompt_eval_tps": telemetry["prompt_eval_tps"],
        "ttft_sec": telemetry["ttft_sec"],
        "eval_count": telemetry["eval_count"],
        "prompt_eval_count": telemetry["prompt_eval_count"],
        "hardware_pre": hw_before,
        "hardware_post": hw_after,
        "sample_response": text[:150] + "...",
    }

