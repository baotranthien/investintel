from dataclasses import asdict, dataclass
import json
import subprocess
from typing import Any
import httpx

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

class OllamaProvider:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig.from_env()
        self.base_url = self.config.base_url
        self.default_model = self.config.primary_model

    async def _generate_result(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        model_to_use = model or self.default_model
        payload: dict[str, Any] = {
            "model": model_to_use,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": self.config.keep_alive,
            "options": {"num_ctx": self.config.num_ctx, "num_predict": self.config.num_predict},
        }
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
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise AIProviderError("Ollama returned invalid JSON for a structured response.") from error
        if not isinstance(data, dict):
            raise AIProviderError("Ollama structured response must be a JSON object.")
        return data, metadata

    def _detect_gpu(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {"available": False, "name": None, "memory_total_mib": None, "memory_used_mib": None}
            name, total, used = (part.strip() for part in result.stdout.splitlines()[0].split(",", 2))
            return {"available": True, "name": name, "memory_total_mib": int(total), "memory_used_mib": int(used)}
        except (FileNotFoundError, subprocess.TimeoutExpired):
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
            return {
                "status": "HEALTHY" if loaded else "DEGRADED",
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
