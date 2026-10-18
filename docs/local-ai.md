# Local AI Setup

## Environment Detected
- **OS**: Windows 11 Home 64-bit
- **CPU**: 12th Gen Intel(R) Core(TM) i5-12500H
- **RAM**: 16 GB
- **GPU**: NVIDIA GeForce RTX 3050 Laptop GPU
- **VRAM**: 4GB

## Ollama Status
- Currently, `ollama` CLI is not installed or not in PATH.
- **Recommended Action**: Install Ollama for Windows from [ollama.com](https://ollama.com/).

## AI Architecture
- We use an abstract `AIProvider` pattern to easily swap implementations.
- Local implementation uses `OllamaProvider`.
- Default fallback mechanism to report "AI unavailable" gracefully when Ollama is offline.

## Model Candidates (Phase 1 Benchmarking)
Due to 4GB VRAM constraint, we should target models smaller than 3B parameters for fast inference:
1. `phi3:mini` (3.8B - might need 4-bit quantization)
2. `qwen2:1.5b` or `qwen2:0.5b`
3. `llama3.2:1b`
4. `gemma2:2b`

## Next Recommended Benchmark
1. Install Ollama.
2. Run `ollama run qwen2:1.5b` and measure tokens/second.
3. Test inference with basic financial entity extraction prompts.
