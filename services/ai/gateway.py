"""Multi-provider AI Gateway with automatic failover and circuit breaker."""
import asyncio
import logging
import os
import time
from typing import Any
import uuid

from .config import GatewayConfig, GeminiConfig, OllamaConfig, redact_secrets
from .errors import (
    AIPaidProviderBlockedError,
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from .cloud_providers import GroqProvider, OpenRouterProvider
from .gemini_provider import GeminiProvider
from .provider import AIProvider
from .providers import OllamaProvider

logger = logging.getLogger(__name__)


def is_cloud_mode() -> bool:
    return (
        os.getenv("CLOUD_MODE", "false").lower() in ("1", "true", "yes")
        or os.getenv("APP_ENV", "development").lower() == "production"
    )


class PlaceholderProvider:
    """Placeholder for unconfigured cloud providers (OpenAI, Grok, DeepSeek)."""

    def __init__(self, name: str, env_var: str):
        self.name = name
        self.env_var = env_var

    @property
    def is_configured(self) -> bool:
        key = os.getenv(self.env_var)
        return bool(key and key.strip() and not key.startswith("PASTE_"))

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "status": "AVAILABLE" if self.is_configured else "NOT_CONFIGURED",
            "available": self.is_configured,
            "reason": None if self.is_configured else f"{self.env_var} is not configured.",
        }

    async def generate(self, prompt: str, system: str = "", model: str | None = None) -> str:
        raise AIProviderError(f"{self.name.capitalize()} API is not configured or enabled.")

    async def generate_structured(
        self, prompt: str, schema: dict[str, Any], system: str = "", model: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raise AIProviderError(f"{self.name.capitalize()} API is not configured or enabled.")


class AIGateway:
    """Gateway orchestrating multiple AI providers with failover and health tracking."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        gemini_provider: AIProvider | None = None,
        ollama_provider: AIProvider | None = None,
        groq_provider: AIProvider | None = None,
        openrouter_provider: AIProvider | None = None,
    ):
        self.config = config or GatewayConfig.from_env()
        self._gemini = gemini_provider or GeminiProvider()
        self._groq = groq_provider or GroqProvider()
        self._openrouter = openrouter_provider or OpenRouterProvider()
        self._ollama = ollama_provider or OllamaProvider()
        self._openai = PlaceholderProvider("openai", "OPENAI_API_KEY")
        self._grok = PlaceholderProvider("grok", "XAI_API_KEY")
        self._deepseek = PlaceholderProvider("deepseek", "DEEPSEEK_API_KEY")

        self._cooldowns: dict[str, float] = {}
        self._auth_failed: set[str] = set()
        self._last_active_provider: str | None = None

    def get_provider(self, name: str) -> AIProvider:
        name = name.lower()
        if name == "gemini":
            return self._gemini
        if name == "groq":
            return self._groq
        if name == "openrouter":
            return self._openrouter
        if name == "ollama":
            return self._ollama
        if name == "openai":
            return self._openai
        if name == "grok":
            return self._grok
        if name == "deepseek":
            return self._deepseek
        raise ValueError(f"Unknown AI provider: {name}")

    def is_in_cooldown(self, name: str) -> bool:
        until = self._cooldowns.get(name.lower(), 0.0)
        return time.time() < until

    def set_cooldown(self, name: str, seconds: float) -> None:
        self._cooldowns[name.lower()] = max(self._cooldowns.get(name.lower(), 0.0), time.time() + max(1.0, seconds))

    def mark_auth_failed(self, name: str) -> None:
        self._auth_failed.add(name.lower())

    def is_ollama_reachable(self) -> bool:
        """Check if Ollama is explicitly enabled and actually reachable (never assume laptop Ollama in cloud)."""
        if is_cloud_mode():
            if os.getenv("OLLAMA_ENABLED", "false").lower() not in ("1", "true", "yes"):
                return False
        st = self._ollama.status()
        return st.get("status") in ("HEALTHY", "DEGRADED") and bool(st.get("available", False))

    def get_eligible_providers(self) -> list[str]:
        """Returns list of configured providers in priority order, skipping inoperative ones."""
        eligible = []
        for name in self.config.provider_priority:
            name_lower = name.lower()
            if name_lower in self._auth_failed:
                continue
            if self.is_in_cooldown(name_lower):
                continue
            try:
                provider = self.get_provider(name_lower)
            except ValueError:
                continue

            if name_lower == "ollama":
                if self.is_ollama_reachable():
                    eligible.append("ollama")
                continue

            status = provider.status()
            if status.get("status") == "NOT_CONFIGURED" or not status.get("available", False):
                continue
            eligible.append(name_lower)

        return eligible

    def status(self) -> dict[str, Any]:
        """Combined observability status for the gateway and all registered providers."""
        gemini_st = self._gemini.status()
        groq_st = self._groq.status()
        openrouter_st = self._openrouter.status()
        ollama_st = self._ollama.status()
        openai_st = self._openai.status()
        grok_st = self._grok.status()
        deepseek_st = self._deepseek.status()

        active = self._last_active_provider
        if not active:
            if gemini_st.get("available"):
                active = "gemini"
            elif groq_st.get("available"):
                active = "groq"
            elif openrouter_st.get("available"):
                active = "openrouter"
            elif ollama_st.get("available"):
                active = "ollama"
            else:
                active = "none"

        gemini_ok = bool(gemini_st.get("available"))
        groq_ok = bool(groq_st.get("available"))
        openrouter_ok = bool(openrouter_st.get("available"))
        ollama_ok = bool(ollama_st.get("available"))
        overall_available = gemini_ok or groq_ok or openrouter_ok or ollama_ok

        if gemini_ok or groq_ok or openrouter_ok or ollama_st.get("status") == "HEALTHY":
            overall_status = "HEALTHY"
        elif overall_available:
            overall_status = "DEGRADED"
        else:
            overall_status = "UNAVAILABLE"

        gemini_cfg = getattr(self._gemini, "config", GeminiConfig.from_env())

        # Retain Ollama fields at root for complete frontend backward-compatibility
        base_status = dict(ollama_st)
        base_status.update({
            "status": overall_status,
            "available": overall_available,
            "active_provider": active,
            "provider": active,
            "providers": {
                "gemini": gemini_st,
                "groq": groq_st,
                "openrouter": openrouter_st,
                "ollama": ollama_st,
                "openai": openai_st,
                "grok": grok_st,
                "deepseek": deepseek_st,
            },
            "provider_priority": list(self.config.provider_priority),
            "fallback_enabled": True,
            "cost_safety": {
                "allow_paid_apis": gemini_cfg.allow_paid_apis,
                "monthly_budget_usd": gemini_cfg.monthly_budget_usd,
            },
            "attempt_budget": {
                "retry_owner": "gateway_and_provider",
                "sdk_internal_retries": "disabled (attempts=1)",
                "max_gemini_upstream_attempts": getattr(self.config, "max_upstream_attempts", 5),
            },
        })
        return base_status

    async def generate(
        self, prompt: str, system: str = "", model: str | None = None, correlation_id: str | None = None
    ) -> str:
        cid = correlation_id or uuid.uuid4().hex[:12]
        eligible = self.get_eligible_providers()
        if not eligible:
            raise AIProviderUnavailableError("No AI providers are currently available (all unconfigured or in cooldown).")

        last_error = None
        for provider_name in eligible:
            provider = self.get_provider(provider_name)
            try:
                if provider_name == "gemini":
                    result = await provider.generate(prompt, system=system, model=model, correlation_id=cid)
                else:
                    result = await provider.generate(prompt, system=system, model=model)
                self._last_active_provider = provider_name
                return result
            except AIProviderRateLimitError as exc:
                logger.warning("Provider %s rate-limited: %s. Failing over to next provider.", provider_name, exc)
                self.set_cooldown(provider_name, getattr(exc, "retry_after", None) or self.config.cooldown_seconds)
                last_error = exc
                continue
            except AIProviderAuthError as exc:
                logger.warning("Provider %s authentication failed: %s. Disabling and failing over.", provider_name, exc)
                self.mark_auth_failed(provider_name)
                last_error = exc
                continue
            except (AIProviderTimeoutError, AIProviderUnavailableError) as exc:
                logger.warning("Provider %s unavailable/timed out: %s. Failing over.", provider_name, exc)
                self.set_cooldown(provider_name, self.config.transient_cooldown_seconds)
                last_error = exc
                continue
            except AIProviderInvalidRequestError as exc:
                logger.warning("Provider %s rejected request: %s. Failing over.", provider_name, exc)
                last_error = exc
                continue
            except AIProviderError as exc:
                logger.warning("Provider %s failed: %s. Failing over.", provider_name, exc)
                last_error = exc
                continue

        raise AIProviderUnavailableError(f"All configured AI providers failed. Last error: {redact_secrets(str(last_error))}")

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        cid = correlation_id or uuid.uuid4().hex[:12]
        eligible = self.get_eligible_providers()
        if not eligible:
            raise AIProviderUnavailableError("No AI providers are currently available (all unconfigured or in cooldown).")

        last_error = None
        for provider_name in eligible:
            provider = self.get_provider(provider_name)
            try:
                if provider_name == "gemini":
                    data, metadata = await provider.generate_structured(
                        prompt, schema, system=system, model=model, correlation_id=cid
                    )
                else:
                    data, metadata = await provider.generate_structured(
                        prompt, schema, system=system, model=model
                    )
                self._last_active_provider = provider_name
                metadata["gateway_active_provider"] = provider_name
                metadata["correlation_id"] = cid
                return data, metadata
            except AIProviderRateLimitError as exc:
                logger.warning("Provider %s rate-limited: %s. Failing over to next provider.", provider_name, exc)
                self.set_cooldown(provider_name, getattr(exc, "retry_after", None) or self.config.cooldown_seconds)
                last_error = exc
                continue
            except AIProviderAuthError as exc:
                logger.warning("Provider %s authentication failed: %s. Disabling and failing over.", provider_name, exc)
                self.mark_auth_failed(provider_name)
                last_error = exc
                continue
            except (AIProviderTimeoutError, AIProviderUnavailableError) as exc:
                logger.warning("Provider %s unavailable/timed out: %s. Failing over.", provider_name, exc)
                self.set_cooldown(provider_name, self.config.transient_cooldown_seconds)
                last_error = exc
                continue
            except AIProviderInvalidRequestError as exc:
                logger.warning("Provider %s rejected request: %s. Failing over.", provider_name, exc)
                last_error = exc
                continue
            except AIProviderError as exc:
                logger.warning("Provider %s failed: %s. Failing over.", provider_name, exc)
                last_error = exc
                continue

        raise AIProviderUnavailableError(f"All configured AI providers failed. Last error: {redact_secrets(str(last_error))}")
