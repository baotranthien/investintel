# INVESTINTEL — PHASE 6E: QWEN, HARDWARE & PERFORMANCE OPTIMIZATION AUDIT REPORT

**Author**: Lead Software Engineer / AI & Hardware Performance Engineer  
**Branch**: `phase6-local-stability`  
**Date**: November 2, 2026  
**Status**: **COMPLETE & VERIFIED (5/5 AUTOMATED TESTS PASS)**

---

## 1. Executive Summary

Phase 6E establishes hardware-grounded performance profiling and real-time inference telemetry for InvestIntel's local AI Analyst. The primary model is strictly preserved as **`qwen3.5:9b-q4_K_M`** running locally via Ollama on an **NVIDIA GeForce RTX 3050 Laptop GPU** (4GB VRAM).

Zero external cloud AI APIs (Gemini, OpenAI, Anthropic) or AnythingLLM wrappers are utilized. The platform captures fine-grained token throughput, Time To First Token (TTFT), VRAM residency, and system memory to prevent silent fallback to CPU inference.

---

## 2. Benchmark & Performance Results

### Benchmark Methodology
- **Model**: `qwen3.5:9b-q4_K_M` (Q4_K_M quantized GGUF).
- **Prompt**: Standard institutional assessment prompt for Binh Minh Plastics (BMP), passing 2024 Revenue, Net Margin (20.2%), ROE (38.4%), and D/E (0.12x).
- **Hardware Profile**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB VRAM), 16GB System RAM, Windows 11.

### Cold vs. Warm Inference Benchmark Data

| Metric | Cold Run (First Model Load) | Warm Run (Residency in VRAM) | Delta / Improvement |
| :--- | :--- | :--- | :--- |
| **Time To First Token (TTFT)** | `19.551 s` | **`0.469 s`** | **97.6% faster** (< 500ms TTFT) |
| **Prompt Evaluation Speed** | `96.16 tok/s` | **`214.82 tok/s`** | **123.4% faster** |
| **Generation Throughput** | `5.44 tok/s` | **`5.54 tok/s`** | Consistent (~5.5 tok/s) |
| **VRAM Allocated** | `191 MB -> 2,715 MB` | `2,707 MB (Steady)` | GPU-accelerated |
| **GPU Temperature** | `43 °C -> 50 °C` | `49 °C -> 54 °C` | Thermal headroom safe |
| **Total Response Time (96 tokens)** | `37.429 s` | **`18.431 s`** | **50.8% faster overall** |

---

## 3. Architecture & Components Implemented

### 3.1 Telemetry Engine: `services/ai/telemetry.py`
- **Real-Time Hardware Metrics**: Queries `nvidia-smi` directly for GPU name, total VRAM, used VRAM, free VRAM, GPU utilization %, and temperature without emitting fake zeroes when unavailable.
- **System Memory Profiling**: Captures total physical RAM, available RAM, and memory pressure.
- **Inference Metric Logging**: Extracts `eval_count`, `eval_duration`, `prompt_eval_count`, and `prompt_eval_duration` from Ollama generate responses and appends structured records to `logs/ollama_metrics.jsonl`.
- **Aggregate Telemetry**: Calculates median generation TPS and median TTFT across historical inferences.

### 3.2 System Diagnostics Endpoint
- **`GET /api/v1/system/diagnostics`**:
  - Exposes database health, GPU/RAM telemetry, active Ollama model, VRAM placement, and median inference throughput.
  - Exempted from authentication cookie requirements for local monitoring dashboards.

---

## 4. Automated Test Verification

Automated test suite: `tests/test_phase6e_ai_hardware_performance.py`

| Test Case | Objective | Result | Duration |
| :--- | :--- | :--- | :--- |
| `test_primary_model_preservation` | Confirms primary model is strictly `qwen3.5:9b-q4_K_M` | **PASS** | 0.01s |
| `test_hardware_diagnostics_telemetry` | Validates GPU VRAM (4096MB) and RAM (16GB) parsing | **PASS** | 0.45s |
| `test_ollama_runtime_status` | Validates Ollama listening state and model registry | **PASS** | 0.02s |
| `test_inference_telemetry_metrics_logged` | Verifies `logs/ollama_metrics.jsonl` contains median TPS and TTFT | **PASS** | 0.01s |
| `test_system_diagnostics_endpoint` | Verifies `/api/v1/system/diagnostics` endpoint schema and live data | **PASS** | 0.85s |

**Total Suite Result**: 5 passed in 36.89s.

---

## 5. Phase 6E Acceptance Sign-off

- [x] Primary model preserved as `qwen3.5:9b-q4_K_M`.
- [x] Zero cloud AI inference or AnythingLLM dependencies.
- [x] Cold vs. warm benchmark performed and logged.
- [x] Warm TTFT achieves sub-second latency (0.469s).
- [x] GPU VRAM and system memory monitored via `nvidia-smi`.
- [x] Inference metrics appended to structured log `logs/ollama_metrics.jsonl`.
- [x] Diagnostics API endpoint `/api/v1/system/diagnostics` operational.
- [x] Phase 6E complete; ready to proceed automatically to **Phase 6F: Local Monitoring, Logging & Self-Recovery**.

