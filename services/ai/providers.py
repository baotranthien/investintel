from dataclasses import asdict, dataclass
import json
import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger(__name__)

from .config import OllamaConfig
from .provider import AIProvider


from .errors import (
    AIPaidProviderBlockedError,
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)


@dataclass
class GenerationMetadata:
    model: str
    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_count: int | None = None
    eval_duration_ns: int | None = None
    done_reason: str | None = None


def _generation_metadata(payload: dict[str, Any], model: str) -> dict[str, Any]:
    return asdict(GenerationMetadata(
        model=payload.get("model", model),
        total_duration_ns=payload.get("total_duration"),
        load_duration_ns=payload.get("load_duration"),
        prompt_eval_count=payload.get("prompt_eval_count"),
        prompt_eval_duration_ns=payload.get("prompt_eval_duration"),
        eval_count=payload.get("eval_count"),
        eval_duration_ns=payload.get("eval_duration"),
        done_reason=payload.get("done_reason"),
    ))

def _clean_and_parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Thử parse trực tiếp
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Thử tìm object JSON bao ngoài {...}
    match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Thử tự động đóng chuỗi và ngoặc nếu bị cắt cụt do giới hạn token
    repaired = cleaned
    first_brace = repaired.find("{")
    if first_brace != -1:
        repaired = repaired[first_brace:]
    if repaired.count('"') % 2 != 0:
        repaired += '"'
    open_brackets = repaired.count('[') - repaired.count(']')
    if open_brackets > 0:
        repaired += ']' * open_brackets
    open_braces = repaired.count('{') - repaired.count('}')
    if open_braces > 0:
        repaired += '}' * open_braces

    try:
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    raise AIProviderError("Ollama returned invalid JSON for a structured response.")


def ensure_ollama_server() -> bool:
    """Check if Ollama is listening on 11434; if not and local binary exists, auto-start `ollama serve`."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    if os.getenv("CLOUD_MODE", "false").lower() in {"1", "true", "yes"}:
        return False

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 11434))
        s.close()
        return True
    except (socket.error, ConnectionRefusedError, TimeoutError, OSError):
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass

    candidates = [
        Path(r"C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe"),
        Path(os.path.expanduser("~")) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
    ]
    which_ollama = shutil.which("ollama")
    if which_ollama:
        candidates.insert(0, Path(which_ollama))

    for exe_path in candidates:
        if exe_path.exists():
            try:
                flags = 0
                if os.name == "nt":
                    # CREATE_NO_WINDOW = 0x08000000, DETACHED_PROCESS = 0x00000008
                    flags = 0x08000000 | 0x00000008
                subprocess.Popen([str(exe_path), "serve"], creationflags=flags)
                logger.info("Auto-started Ollama server from %s", exe_path)
                return True
            except Exception as e:
                logger.warning("Failed to auto-start Ollama: %s", e)
    return False


class OllamaProvider:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig.from_env()
        self.base_url = self.config.base_url
        self.default_model = self.config.primary_model
        if "127.0.0.1:11434" in self.base_url or "localhost:11434" in self.base_url:
            ensure_ollama_server()
            if "PYTEST_CURRENT_TEST" not in os.environ and os.getenv("CLOUD_MODE", "false").lower() not in {"1", "true", "yes"}:
                try:
                    import threading
                    threading.Thread(target=self.prewarm, daemon=True).start()
                except Exception:
                    pass

    def prewarm(self) -> None:
        """Send a keep-alive ping to ensure the configured model stays loaded in memory."""
        if "PYTEST_CURRENT_TEST" in os.environ or os.getenv("CLOUD_MODE", "false").lower() in {"1", "true", "yes"}:
            return
        try:
            timeout = httpx.Timeout(45.0, connect=3.0)
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.default_model, "keep_alive": self.config.keep_alive},
                )
        except Exception:
            pass

    async def _generate_result(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        model_to_use = model or self.default_model
        options = {
            "num_ctx": self.config.num_ctx,
            "num_predict": self.config.num_predict,
            "num_thread": getattr(self.config, "num_thread", 6),
        }
        payload: dict[str, Any] = {
            "model": model_to_use,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": self.config.keep_alive,
            "options": options,
        }
        if not self.config.think:
            payload["think"] = False
        if schema is not None:
            payload["format"] = schema

        timeout = httpx.Timeout(
            self.config.timeout_seconds,
            connect=self.config.connect_timeout_seconds,
        )
        for attempt in range(self.config.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                try:
                    result = response.json()
                except ValueError as error:
                    raise AIProviderError("Ollama returned invalid response JSON.") from error
                if not isinstance(result, dict):
                    raise AIProviderError("Ollama response must be a JSON object.")
                text = result.get("response")
                if not isinstance(text, str) or not text.strip():
                    raise AIProviderError("Ollama returned an empty response.")
                return text, _generation_metadata(result, model_to_use)
            except httpx.HTTPStatusError as error:
                detail = error.response.text[:500]
                if error.response.status_code == 404:
                    raise AIProviderUnavailableError(f"Configured Ollama model '{model_to_use}' is unavailable.") from error
                if error.response.status_code < 500 or attempt >= self.config.retries:
                    raise AIProviderError(f"Ollama request failed with HTTP {error.response.status_code}: {detail}") from error
            except httpx.TimeoutException as error:
                if attempt >= self.config.retries:
                    raise AIProviderTimeoutError(f"Ollama request timed out at {self.base_url}.") from error
            except httpx.NetworkError as error:
                if attempt >= self.config.retries:
                    raise AIProviderUnavailableError(f"Ollama is unavailable at {self.base_url}.") from error
        raise AIProviderUnavailableError("Ollama request failed after configured retries.")


    async def generate(self, prompt: str, system: str = "", model: str | None = None) -> str:
        text, _ = await self._generate_result(prompt, system, model)
        return text

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        text, metadata = await self._generate_result(prompt, system, model, schema)
        data = _clean_and_parse_json(text)
        return data, metadata

    def _detect_gpu(self) -> dict[str, Any]:
        """In-process GPU telemetry via nvml.dll (ctypes) — 100% silent, zero subprocess/console window."""
        try:
            import ctypes
            nvml = ctypes.CDLL("nvml.dll")
            nvml.nvmlInit()
            handle = ctypes.c_void_p()
            nvml.nvmlDeviceGetHandleByIndex(0, ctypes.byref(handle))

            class nvmlMemory_t(ctypes.Structure):
                _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]

            mem = nvmlMemory_t()
            nvml.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(mem))
            name_buf = ctypes.create_string_buffer(64)
            nvml.nvmlDeviceGetName(handle, name_buf, 64)
            name = name_buf.value.decode("utf-8")
            total_mib = int(mem.total // (1024 * 1024))
            used_mib = int(mem.used // (1024 * 1024))
            nvml.nvmlShutdown()
            return {"available": True, "name": name, "memory_total_mib": total_mib, "memory_used_mib": used_mib}
        except Exception:
            pass
        return {"available": False, "name": None, "memory_total_mib": None, "memory_used_mib": None}

    def status(self) -> dict[str, Any]:
        try:
            timeout = httpx.Timeout(2.0, connect=min(1.0, self.config.connect_timeout_seconds))
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                version = client.get(f"{self.base_url}/api/version")
                version.raise_for_status()
                tags = client.get(f"{self.base_url}/api/tags")
                tags.raise_for_status()
                running = client.get(f"{self.base_url}/api/ps")
                running.raise_for_status()
            models = [item.get("name", "") for item in tags.json().get("models", [])]
            configured = self.config.primary_model
            installed = configured in models or any(name.split(":", 1)[0] == configured.split(":", 1)[0] for name in models)
            running_models = running.json().get("models", [])
            loaded = any(
                item.get("name", "").split(":", 1)[0] == configured.split(":", 1)[0]
                for item in running_models
            )
            if not installed:
                return {
                    "status": "MODEL_NOT_FOUND",
                    "available": False,
                    "provider": "ollama",
                    "version": version.json().get("version"),
                    "models": models,
                    "configured_models": {
                        "fast": self.config.fast_model,
                        "primary": self.config.primary_model,
                        "reasoning": self.config.reasoning_model,
                    },
                    "configured_model_installed": False,
                    "configured_model_loaded": False,
                    "running_models": running_models,
                    "gpu": self._detect_gpu(),
                    "reason": f"Configured model '{configured}' is not installed in Ollama. Installed models: {models}",
                }
            if not loaded and "PYTEST_CURRENT_TEST" not in os.environ and os.getenv("CLOUD_MODE", "false").lower() not in {"1", "true", "yes"}:
                try:
                    import threading
                    threading.Thread(target=self.prewarm, daemon=True).start()
                except Exception:
                    pass
            return {
                "status": "HEALTHY",
                "available": True,
                "model_state": "LOADED" if loaded else "STANDBY",
                "provider": "ollama",
                "version": version.json().get("version"),
                "models": models,
                "configured_models": {
                    "fast": self.config.fast_model,
                    "primary": self.config.primary_model,
                    "reasoning": self.config.reasoning_model,
                },
                "configured_model_installed": True,
                "configured_model_loaded": loaded,
                "running_models": running_models,
                "gpu": self._detect_gpu(),
                "limits": {
                    "timeout_seconds": self.config.timeout_seconds,
                    "retries": self.config.retries,
                    "num_ctx": self.config.num_ctx,
                    "num_predict": self.config.num_predict,
                    "num_thread": getattr(self.config, "num_thread", 6),
                    "think": self.config.think,
                },
            }
        except (httpx.HTTPError, ValueError, KeyError):
            pass
        return {
            "status": "UNAVAILABLE",
            "available": False,
            "provider": "ollama",
            "models": [],
            "configured_model_installed": False,
            "running_models": [],
            "gpu": self._detect_gpu(),
            "reason": f"Ollama is not responding at {self.base_url}.",
        }
