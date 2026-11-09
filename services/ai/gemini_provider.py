import json
import logging
import os
import re
from typing import Any
import httpx

from .errors import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)

logger = logging.getLogger(__name__)


def _normalize_dict_keys(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        norm_k = k.strip()
        if isinstance(v, dict):
            v = _normalize_dict_keys(v)
        elif isinstance(v, list):
            v = [_normalize_dict_keys(item) if isinstance(item, dict) else item for item in v]
        out[norm_k] = v

    if "claims" in out and isinstance(out["claims"], list):
        for claim in out["claims"]:
            if isinstance(claim, dict):
                if "citation_id" in claim and "citation_ids" not in claim:
                    val = claim.pop("citation_id")
                    claim["citation_ids"] = val if isinstance(val, list) else [val]
                elif "citation_id" in claim:
                    claim.pop("citation_id")
                if "claim_type" in claim and isinstance(claim["claim_type"], str):
                    claim["claim_type"] = claim["claim_type"].strip().upper()
    return out


def _clean_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    parsed = json.loads(cleaned)
    if isinstance(parsed, dict):
        return _normalize_dict_keys(parsed)
    return parsed


class GeminiProvider:
    """High-throughput Gemini Flash provider with automatic token usage and structured outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 35.0,
    ):
        self.api_key = (
            api_key
            if api_key is not None
            else (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
        ).strip()
        # Default to gemini-1.5-flash which has 15 RPM / 1500 RPD free tier limit
        self.model = (model if model is not None else (os.getenv("GEMINI_MODEL") or "gemini-1.5-flash")).strip()
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 15)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "available": self.is_available(),
            "model": self.model,
            "has_api_key": bool(self.api_key),
        }

    async def generate(self, prompt: str, system: str = "", model: str | None = None) -> str:
        text, _ = await self._generate_internal(prompt, system=system, model=model, json_mode=False)
        return text

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        text, metadata = await self._generate_internal(
            prompt, system=system, model=model, json_mode=True
        )
        data = _clean_json(text)
        return data, metadata

    async def _generate_internal(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        if not self.is_available():
            raise AIProviderAuthError("GEMINI_API_KEY is not configured or too short.")

        model_to_use = self.model
        if model and model.strip().lower().startswith("gemini"):
            model_to_use = model.strip()

        url = f"{self.base_url}/models/{model_to_use}:generateContent?key={self.api_key}"

        gen_config: dict[str, Any] = {"temperature": 0.2}
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    raise AIProviderRateLimitError("Gemini API rate limit exceeded (HTTP 429: Too Many Requests / Quota Exhausted).")
                if response.status_code in (401, 403):
                    raise AIProviderAuthError(f"Gemini API authentication failed (HTTP {response.status_code}): {response.text[:200]}")
                response.raise_for_status()

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise AIProviderError("Gemini returned no candidates in response.")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise AIProviderError("Gemini candidate has no text parts.")

                text = parts[0].get("text", "")
                usage = data.get("usageMetadata", {})
                metadata = {
                    "model": model_to_use,
                    "prompt_eval_count": usage.get("promptTokenCount"),
                    "eval_count": usage.get("candidatesTokenCount"),
                    "total_tokens": usage.get("totalTokenCount"),
                    "provider": "gemini",
                }
                return text, metadata
            except httpx.TimeoutException as exc:
                raise AIProviderTimeoutError(f"Gemini API request timed out ({self.timeout_seconds}s).") from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise AIProviderRateLimitError("Gemini API rate limit exceeded (HTTP 429).") from exc
                raise AIProviderError(f"Gemini API failed with HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
            except httpx.NetworkError as exc:
                raise AIProviderUnavailableError(f"Gemini API network unreachable: {exc}") from exc

