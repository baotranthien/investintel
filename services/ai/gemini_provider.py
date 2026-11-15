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


_DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
_LEGACY_GEMINI_ALIASES = frozenset(
    {
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    }
)


def _normalize_gemini_model(candidate: str | None, fallback: str = _DEFAULT_GEMINI_MODEL) -> str:
    """Keep active Gemini model names and map retired Flash aliases to the live rolling Flash Lite model."""
    if not candidate:
        return fallback
    cleaned = candidate.strip()
    if not cleaned or cleaned.lower() in _LEGACY_GEMINI_ALIASES:
        return fallback
    return cleaned


class GeminiProvider:
    """High-throughput Gemini Flash provider with multi-key failover and structured outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        api_keys: list[str] | None = None,
    ):
        if api_keys is not None:
            self.api_keys = [k.strip() for k in api_keys if k and len(k.strip()) > 15]
        elif api_key is not None:
            cleaned = api_key.strip()
            self.api_keys = [cleaned] if len(cleaned) > 15 else []
        else:
            from .config import load_gemini_api_keys
            self.api_keys = load_gemini_api_keys()

        self.api_key = self.api_keys[0] if self.api_keys else ""
        self._key_index = 0
        raw_model = model if model is not None else (os.getenv("GEMINI_MODEL") or _DEFAULT_GEMINI_MODEL)
        self.model = _normalize_gemini_model(raw_model)
        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20.0"))
        )
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def is_available(self) -> bool:
        return len(self.api_keys) > 0

    def status(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "available": self.is_available(),
            "model": self.model,
            "has_api_key": bool(self.api_keys),
            "key_count": len(self.api_keys),
            "timeout_seconds": self.timeout_seconds,
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
            prompt, schema=schema, system=system, model=model, json_mode=True
        )
        data = _clean_json(text)
        return data, metadata

    async def _generate_internal(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        system: str = "",
        model: str | None = None,
        json_mode: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        if not self.is_available():
            raise AIProviderAuthError("GEMINI_API_KEY is not configured or too short.")

        model_to_use = _normalize_gemini_model(self.model)
        if model and model.strip().lower().startswith("gemini"):
            model_to_use = _normalize_gemini_model(model, fallback=model_to_use)

        gen_config: dict[str, Any] = {"temperature": 0.2}
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        user_content = prompt
        if json_mode and schema:
            schema_str = json.dumps(schema, separators=(",", ":"))
            if schema_str not in user_content:
                user_content = f"{user_content}\n\nOutput only valid JSON matching this JSON Schema:\n{schema_str}"

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": gen_config,
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)
        key_count = len(self.api_keys)
        start_idx = self._key_index % key_count
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for offset in range(key_count):
                idx = (start_idx + offset) % key_count
                active_key = self.api_keys[idx]
                url = f"{self.base_url}/models/{model_to_use}:generateContent?key={active_key}"
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
                    self._key_index = idx
                    metadata = {
                        "model": model_to_use,
                        "prompt_eval_count": usage.get("promptTokenCount"),
                        "eval_count": usage.get("candidatesTokenCount"),
                        "total_tokens": usage.get("totalTokenCount"),
                        "provider": "gemini",
                        "key_slot": idx + 1,
                        "keys_configured": key_count,
                    }
                    return text, metadata
                except (AIProviderRateLimitError, AIProviderAuthError) as exc:
                    last_exc = exc
                except httpx.TimeoutException:
                    last_exc = AIProviderTimeoutError(f"Gemini API request timed out ({self.timeout_seconds}s).")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        last_exc = AIProviderRateLimitError("Gemini API rate limit exceeded (HTTP 429).")
                    else:
                        last_exc = AIProviderError(
                            f"Gemini API failed with HTTP {exc.response.status_code}: {exc.response.text[:200]}"
                        )
                except httpx.NetworkError as exc:
                    last_exc = AIProviderUnavailableError(f"Gemini API network unreachable: {exc}")
                except AIProviderError as exc:
                    last_exc = exc

                self._key_index = (idx + 1) % key_count

        assert last_exc is not None
        raise last_exc

