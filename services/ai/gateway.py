"""Multi-Provider AI Gateway orchestrating Groq -> Gemini -> Local Ollama with graceful failover."""
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
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from .provider import AIProvider
from .providers import OllamaProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider

logger = logging.getLogger(__name__)


def is_cloud_mode() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


class AIGateway:
    """Gateway orchestrating Groq (Primary) -> Gemini (Secondary) -> Local Ollama (Tertiary)."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        ollama_provider: AIProvider | None = None,
        gemini_provider: AIProvider | None = None,
        groq_provider: AIProvider | None = None,
        **kwargs: Any,  # Absorb any legacy provider arguments gracefully
    ):
        self.config = config or GatewayConfig.from_env()
        self._groq = groq_provider or GroqProvider()
        self._gemini = gemini_provider or GeminiProvider()
        self._ollama = ollama_provider or OllamaProvider()
        self._last_active_provider: str | None = None

    @property
    def provider(self) -> AIProvider:
        """Returns the primary active provider for backwards compatibility."""
        active_name = self.status().get("active_provider")
        if active_name and active_name != "none":
            return self.get_provider(active_name)
        return self._ollama

    def get_provider(self, name: str) -> AIProvider:
        name = name.lower()
        if name == "groq":
            return self._groq
        if name == "gemini":
            return self._gemini
        if name == "ollama":
            return self._ollama
        raise ValueError(f"Unknown or unsupported AI provider: {name}. Supported: 'groq', 'gemini', 'ollama'.")

    def is_ollama_reachable(self) -> bool:
        """Check if Ollama is actually reachable (never assumed in cloud mode)."""
        if is_cloud_mode():
            if os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
                return False
        st = self._ollama.status()
        return st.get("status") in ("HEALTHY", "DEGRADED") and bool(st.get("available", False))

    def get_eligible_providers(self) -> list[str]:
        eligible = []
        if self._groq and self._groq.is_available():
            eligible.append("groq")
        if self._gemini and self._gemini.is_available():
            eligible.append("gemini")
        if self.is_ollama_reachable():
            eligible.append("ollama")
        return eligible

    def status(self) -> dict[str, Any]:
        """Observability status across all three providers with active failover priority."""
        ollama_st = self._ollama.status()
        ollama_avail = bool(ollama_st.get("available", False))
        gemini_avail = bool(self._gemini and self._gemini.is_available())
        groq_avail = bool(self._groq and self._groq.is_available())

        # Determine active priority order based on config and availability
        active_priority = []
        for p in self.config.provider_priority:
            if p == "groq" and groq_avail:
                active_priority.append("groq")
            elif p == "gemini" and gemini_avail:
                active_priority.append("gemini")
            elif p == "ollama" and ollama_avail:
                active_priority.append("ollama")

        # Fallback to any available if configured list is empty
        if not active_priority:
            if groq_avail:
                active_priority.append("groq")
            if gemini_avail:
                active_priority.append("gemini")
            if ollama_avail:
                active_priority.append("ollama")

        active = active_priority[0] if active_priority else "none"

        base_status = dict(ollama_st)
        base_status.update({
            "active_provider": active,
            "provider": active,
            "provider_priority": active_priority,
            "fallback_enabled": len(active_priority) > 1,
            "groq": self._groq.status() if self._groq else None,
            "gemini": self._gemini.status() if self._gemini else None,
        })
        return base_status

    async def generate(
        self, prompt: str, system: str = "", model: str | None = None, correlation_id: str | None = None
    ) -> str:
        errors = []
        for provider_name in self.config.provider_priority:
            if provider_name == "groq" and self._groq and self._groq.is_available():
                try:
                    text = await self._groq.generate(prompt, system=system, model=model)
                    self._last_active_provider = "groq"
                    return text
                except Exception as exc:
                    logger.warning("Groq generation failed (%s). Failing over to next provider.", exc)
                    errors.append(f"groq: {exc}")

            elif provider_name == "gemini" and self._gemini and self._gemini.is_available():
                try:
                    text = await self._gemini.generate(prompt, system=system, model=model)
                    self._last_active_provider = "gemini"
                    return text
                except Exception as exc:
                    logger.warning("Gemini generation failed (%s). Failing over to next provider.", exc)
                    errors.append(f"gemini: {exc}")

            elif provider_name == "ollama":
                if is_cloud_mode() and os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
                    errors.append("ollama: LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD")
                    continue

                st = self._ollama.status()
                if not st.get("available"):
                    errors.append(f"ollama unavailable: {st.get('reason', 'offline')}")
                    continue

                try:
                    text = await self._ollama.generate(prompt, system=system, model=model)
                    self._last_active_provider = "ollama"
                    return text
                except Exception as exc:
                    logger.warning("Ollama generation failed (%s).", exc)
                    errors.append(f"ollama: {exc}")

        raise AIProviderUnavailableError(f"All AI providers in priority chain failed. Errors: {'; '.join(errors)}")

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        errors = []
        for provider_name in self.config.provider_priority:
            if provider_name == "groq" and self._groq and self._groq.is_available():
                try:
                    data, metadata = await self._groq.generate_structured(
                        prompt, schema=schema, system=system, model=model
                    )
                    self._last_active_provider = "groq"
                    return data, metadata
                except Exception as exc:
                    logger.warning("Groq structured generation failed (%s). Failing over to next provider.", exc)
                    errors.append(f"groq: {exc}")

            elif provider_name == "gemini" and self._gemini and self._gemini.is_available():
                try:
                    data, metadata = await self._gemini.generate_structured(
                        prompt, schema=schema, system=system, model=model
                    )
                    self._last_active_provider = "gemini"
                    return data, metadata
                except Exception as exc:
                    logger.warning("Gemini structured generation failed (%s). Failing over to next provider.", exc)
                    errors.append(f"gemini: {exc}")

            elif provider_name == "ollama":
                if is_cloud_mode() and os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
                    errors.append("ollama: LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD")
                    continue

                st = self._ollama.status()
                if not st.get("available"):
                    errors.append(f"ollama unavailable: {st.get('reason', 'offline')}")
                    continue

                try:
                    data, metadata = await self._ollama.generate_structured(
                        prompt, schema=schema, system=system, model=model
                    )
                    self._last_active_provider = "ollama"
                    return data, metadata
                except Exception as exc:
                    logger.warning("Ollama structured generation failed (%s).", exc)
                    errors.append(f"ollama: {exc}")

        raise AIProviderUnavailableError(f"All AI providers in priority chain failed. Errors: {'; '.join(errors)}")
