"""Cloud AI Providers: Groq and OpenRouter (free-only models) with strict cost-guardrails."""
import json
import logging
import os
import re
from typing import Any, Optional, Tuple
import httpx

from .errors import (
    AIPaidProviderBlockedError,
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)

logger = logging.getLogger(__name__)


def _is_paid_allowed() -> bool:
    return os.getenv("AI_ALLOW_PAID_APIS", "false").lower() in ("true", "1", "yes")


class GroqProvider:
    """Groq Cloud AI Provider using developer free tier."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 25.0,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        enabled = os.getenv("GROQ_ENABLED", "true").lower() in ("true", "1", "yes")
        if not enabled or not self.api_key:
            return False
        clean = self.api_key.strip()
        return bool(clean and not clean.startswith("PASTE_") and clean != "NOT_CONFIGURED")

    def status(self) -> dict[str, Any]:
        configured = self.is_configured
        return {
            "provider": "groq",
            "status": "HEALTHY" if configured else "NOT_CONFIGURED",
            "available": configured,
            "model": self.model,
            "endpoint": self.BASE_URL,
            "cost_guard": "free_tier_only",
        }

    async def _post_chat(self, messages: list[dict[str, str]], model: Optional[str] = None, response_format: Optional[dict] = None) -> dict[str, Any]:
        if not self.is_configured:
            raise AIProviderError("Groq API is not configured or disabled.")

        model_to_use = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0)) as client:
                resp = await client.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 401:
                    raise AIProviderAuthError("Groq authentication failed (invalid API key).")
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    delay = float(retry_after) if retry_after else 30.0
                    raise AIProviderRateLimitError("Groq rate limit exceeded.", retry_after=delay)
                if resp.status_code >= 500:
                    raise AIProviderUnavailableError(f"Groq service unavailable: HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"Groq request timed out after {self.timeout_seconds}s.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise AIProviderUnavailableError(f"Network error connecting to Groq: {exc}") from exc

    async def generate(self, prompt: str, system: str = "", model: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = await self._post_chat(messages, model=model)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIProviderError("Groq returned unexpected response structure.") from exc

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: Optional[str] = None,
    ) -> Tuple[dict[str, Any], dict[str, Any]]:
        structured_system = (
            (system + "\n\n" if system else "")
            + "Respond with a valid JSON object strictly matching this schema:\n"
            + json.dumps(schema)
        )
        messages = [
            {"role": "system", "content": structured_system},
            {"role": "user", "content": prompt},
        ]
        data = await self._post_chat(
            messages,
            model=model,
            response_format={"type": "json_object"},
        )
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        usage = data.get("usage", {})
        return parsed, usage


class OpenRouterProvider:
    """OpenRouter Provider with strict free-only model contract verification."""

    DEFAULT_FREE_MODEL = "meta-llama/llama-3.2-3b-instruct:free"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 25.0,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENROUTER_MODEL", self.DEFAULT_FREE_MODEL)
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        enabled = os.getenv("OPENROUTER_ENABLED", "true").lower() in ("true", "1", "yes")
        if not enabled or not self.api_key:
            return False
        clean = self.api_key.strip()
        return bool(clean and not clean.startswith("PASTE_") and clean != "NOT_CONFIGURED")

    def _verify_free_model(self, model: str) -> None:
        """Enforce that model ID satisfies free-tier contract (:free suffix) unless paid is allowed."""
        if _is_paid_allowed():
            return
        clean_model = model.strip().lower()
        if not clean_model.endswith(":free"):
            raise AIPaidProviderBlockedError(
                f"OpenRouter model '{model}' is rejected. Zero-budget guard requires free models ending with ':free' (e.g. '{self.DEFAULT_FREE_MODEL}')."
            )

    def status(self) -> dict[str, Any]:
        configured = self.is_configured
        return {
            "provider": "openrouter",
            "status": "HEALTHY" if configured else "NOT_CONFIGURED",
            "available": configured,
            "model": self.model,
            "endpoint": self.BASE_URL,
            "free_only_enforced": True,
        }

    async def _post_chat(self, messages: list[dict[str, str]], model: Optional[str] = None, response_format: Optional[dict] = None) -> dict[str, Any]:
        if not self.is_configured:
            raise AIProviderError("OpenRouter API is not configured or disabled.")

        model_to_use = model or self.model
        self._verify_free_model(model_to_use)

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "HTTP-Referer": "https://investintel.personal",
            "X-Title": "Personal Investment Intelligence",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0)) as client:
                resp = await client.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 401:
                    raise AIProviderAuthError("OpenRouter authentication failed (invalid API key).")
                if resp.status_code == 402:
                    raise AIPaidProviderBlockedError("OpenRouter payment required. Refusing paid usage.")
                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    delay = float(retry_after) if retry_after else 30.0
                    raise AIProviderRateLimitError("OpenRouter rate limit exceeded.", retry_after=delay)
                if resp.status_code >= 500:
                    raise AIProviderUnavailableError(f"OpenRouter service unavailable: HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"OpenRouter request timed out after {self.timeout_seconds}s.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise AIProviderUnavailableError(f"Network error connecting to OpenRouter: {exc}") from exc

    async def generate(self, prompt: str, system: str = "", model: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data = await self._post_chat(messages, model=model)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIProviderError("OpenRouter returned unexpected response structure.") from exc

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: Optional[str] = None,
    ) -> Tuple[dict[str, Any], dict[str, Any]]:
        structured_system = (
            (system + "\n\n" if system else "")
            + "Respond with a valid JSON object strictly matching this schema:\n"
            + json.dumps(schema)
        )
        messages = [
            {"role": "system", "content": structured_system},
            {"role": "user", "content": prompt},
        ]
        data = await self._post_chat(
            messages,
            model=model,
            response_format={"type": "json_object"},
        )
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        usage = data.get("usage", {})
        return parsed, usage
