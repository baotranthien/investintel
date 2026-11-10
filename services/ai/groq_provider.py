"""Groq AI Provider using ultra-fast LPU inference (Llama 3.3 / Llama 3.1)."""
import json
import logging
import os
import re
from typing import Any
from dotenv import load_dotenv
import httpx

load_dotenv()

from .errors import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
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

    # Clean up claim-level minor plural / naming variations
    if "claims" in out and isinstance(out["claims"], list):
        for claim in out["claims"]:
            if isinstance(claim, dict):
                # Normalize citation_id -> citation_ids
                if "citation_id" in claim and "citation_ids" not in claim:
                    val = claim.pop("citation_id")
                    claim["citation_ids"] = val if isinstance(val, list) else [val]
                elif "citation_id" in claim:
                    claim.pop("citation_id")
                # Ensure claim_type is uppercase
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


class GroqProvider:
    """High-speed Groq LPU provider supporting Llama 3.3 70B & Llama 3.1 8B."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        self.api_key = (api_key if api_key is not None else (os.getenv("GROQ_API_KEY") or "")).strip()
        # Default to qwen/qwen3.8-27b (ultra-fast 500+ tok/s with superior multilingual & Vietnamese financial reasoning)
        self.model = (model if model is not None else (os.getenv("GROQ_MODEL") or "qwen/qwen3.8-27b")).strip()
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 15)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "groq",
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
            raise AIProviderAuthError("GROQ_API_KEY is not configured or invalid.")

        # Determine appropriate Groq model: if passed model is a valid Groq identifier, use it; otherwise default to self.model
        model_to_use = self.model
        if ":" in model_to_use:
            model_to_use = "llama-3.3-70b-versatile"
        if model:
            m_str = model.strip()
            if ":" not in m_str and ("/" in m_str or any(k in m_str.lower() for k in ("llama", "mixtral", "gemma", "whisper", "deepseek", "qwen"))):
                model_to_use = m_str

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        effective_system = system or ""
        if json_mode and "json" not in effective_system.lower():
            effective_system = f"{effective_system}\nYou must output a valid JSON object matching the requested schema.".strip()

        if effective_system:
            messages.append({"role": "system", "content": effective_system})

        user_content = prompt
        if json_mode and schema and "json" not in user_content.lower():
            user_content = f"{user_content}\n\nOutput only valid JSON according to this schema:\n{json.dumps(schema)}"

        messages.append({"role": "user", "content": user_content})

        payload: dict[str, Any] = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(self.timeout_seconds, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(self.base_url, headers=headers, json=payload)
                if response.status_code == 429:
                    raise AIProviderRateLimitError("Groq API rate limit exceeded (HTTP 429: Too Many Requests / Quota Exhausted).")
                if response.status_code in (401, 403):
                    raise AIProviderAuthError(f"Groq API authentication failed (HTTP {response.status_code}): {response.text[:200]}")
                if response.status_code == 400:
                    raise AIProviderInvalidRequestError(f"Groq API invalid request (HTTP 400): {response.text[:200]}")
                response.raise_for_status()

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise AIProviderError("Groq returned no choices in response.")

                content = choices[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                metadata = {
                    "model": model_to_use,
                    "prompt_eval_count": usage.get("prompt_tokens"),
                    "eval_count": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "provider": "groq",
                }
                return content, metadata
            except httpx.TimeoutException as exc:
                raise AIProviderTimeoutError(f"Groq API request timed out ({self.timeout_seconds}s).") from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise AIProviderRateLimitError("Groq API rate limit exceeded (HTTP 429).") from exc
                raise AIProviderError(f"Groq API failed with HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
            except httpx.NetworkError as exc:
                raise AIProviderUnavailableError(f"Groq API network unreachable: {exc}") from exc

