"""Local Ollama AI Gateway with cloud environment isolation."""
import asyncio
import logging
import os
import time
from typing import Any
import uuid

from .config import GatewayConfig, OllamaConfig, redact_secrets
from .errors import (
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from .provider import AIProvider
from .providers import OllamaProvider

logger = logging.getLogger(__name__)


def is_cloud_mode() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


class AIGateway:
    """Gateway orchestrating local Ollama as the sole AI provider, with cloud isolation."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        ollama_provider: AIProvider | None = None,
        **kwargs: Any,  # Absorb any legacy provider arguments gracefully
    ):
        self.config = config or GatewayConfig.from_env()
        self._ollama = ollama_provider or OllamaProvider()
        self._last_active_provider: str | None = None

    def get_provider(self, name: str) -> AIProvider:
        name = name.lower()
        if name == "ollama":
            return self._ollama
        raise ValueError(f"Unknown or unsupported AI provider: {name}. Only local Ollama is supported.")

    def is_ollama_reachable(self) -> bool:
        """Check if Ollama is actually reachable (never assumed in cloud mode)."""
        if is_cloud_mode():
            if os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
                return False
        st = self._ollama.status()
        return st.get("status") in ("HEALTHY", "DEGRADED") and bool(st.get("available", False))

    def get_eligible_providers(self) -> list[str]:
        """Returns eligible providers. Only 'ollama' is supported."""
        if self.is_ollama_reachable():
            return ["ollama"]
        return []

    def status(self) -> dict[str, Any]:
        """Observability status for local Ollama, protecting cloud environment from loopback calls."""
        if is_cloud_mode() and os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
            return {
                "status": "LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD",
                "available": False,
                "provider": "ollama",
                "active_provider": "none",
                "version": None,
                "models": [],
                "configured_models": {
                    "fast": self._ollama.config.fast_model,
                    "primary": self._ollama.config.primary_model,
                    "reasoning": self._ollama.config.reasoning_model,
                },
                "configured_model_installed": False,
                "configured_model_loaded": False,
                "running_models": [],
                "gpu": {"available": False, "name": None, "memory_total_mib": None, "memory_used_mib": None},
                "reason": "Local Ollama model is not accessible from the cloud environment.",
                "limits": {
                    "timeout_seconds": self._ollama.config.timeout_seconds,
                    "retries": self._ollama.config.retries,
                    "num_ctx": self._ollama.config.num_ctx,
                    "num_predict": self._ollama.config.num_predict,
                },
            }

        st = self._ollama.status()
        is_avail = bool(st.get("available", False))
        active = "ollama" if is_avail else "none"

        base_status = dict(st)
        base_status.update({
            "active_provider": active,
            "provider": "ollama",
            "provider_priority": ["ollama"],
            "fallback_enabled": False,
        })
        return base_status

    async def generate(
        self, prompt: str, system: str = "", model: str | None = None, correlation_id: str | None = None
    ) -> str:
        if is_cloud_mode() and os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
            raise AIProviderUnavailableError(
                "LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD: Local Ollama AI is not available in the cloud environment."
            )

        st = self._ollama.status()
        if not st.get("available"):
            raise AIProviderUnavailableError(
                f"Ollama is unavailable: {st.get('reason', 'server not responding or model not installed')}."
            )

        text = await self._ollama.generate(prompt, system=system, model=model)
        self._last_active_provider = "ollama"
        return text

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if is_cloud_mode() and os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
            raise AIProviderUnavailableError(
                "LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD: Local Ollama AI is not available in the cloud environment."
            )

        st = self._ollama.status()
        if not st.get("available"):
            raise AIProviderUnavailableError(
                f"Ollama is unavailable: {st.get('reason', 'server not responding or model not installed')}."
            )

        data, metadata = await self._ollama.generate_structured(
            prompt, schema=schema, system=system, model=model
        )
        self._last_active_provider = "ollama"
        return data, metadata
