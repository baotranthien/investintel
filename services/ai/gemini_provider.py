"""Google Gemini Provider using official google-genai SDK with bounded retry and model fallback."""
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
import random
import time
from typing import Any
import uuid

import httpx

from .config import GeminiConfig, redact_secrets
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

# Strict upper limit: FIVE TOTAL HTTP attempts per user request across all Gemini models.
# This includes the initial request — "5 attempts" means 1 initial + up to 4 retries.
# SDK internal retries are disabled (HttpRetryOptions(attempts=1)) so only this
# application-level counter controls how many HTTP requests are made.
MAX_GEMINI_UPSTREAM_ATTEMPTS = 5


def _parse_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After seconds from HTTP headers or RPC error details if present."""
    resp = getattr(exc, "response", None)
    if resp is not None:
        headers = getattr(resp, "headers", None)
        if headers and hasattr(headers, "get"):
            val = headers.get("retry-after") or headers.get("Retry-After")
            if val:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        det_list = details.get("details", [])
        if isinstance(det_list, list):
            for item in det_list:
                if isinstance(item, dict) and "retryDelay" in item:
                    delay_str = str(item["retryDelay"]).rstrip("s")
                    try:
                        return float(delay_str)
                    except (ValueError, TypeError):
                        pass
    return None


def _is_model_not_found(exc: Exception, raw_msg: str) -> bool:
    """Check if 404 indicates a model/resource specific absence rather than generic routing."""
    status_code = getattr(exc, "code", None)
    if status_code != 404 and "NOT_FOUND" not in raw_msg:
        return False
    lower = raw_msg.lower()
    return any(term in lower for term in ("model", "models/", "not found", "no longer available"))


class GeminiProvider:
    """
    Provider integrating Google Gemini models via the google-genai SDK.
    Implements single-owner bounded retries, per-model circuit breakers,
    and automatic fallback (e.g. gemini-3.8-flash -> gemini-3.6-flash).
    """

    def __init__(self, config: GeminiConfig | None = None, client: Any | None = None):
        self.config = config or GeminiConfig.from_env()
        self._client = client
        self._auth_failed = False
        self._rate_limited_until: float = 0.0
        self._model_cooldowns: dict[str, float] = {}
        self._disabled_models: set[str] = set()
        self._diagnostics: deque[dict[str, Any]] = deque(maxlen=100)

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.config.is_configured:
                raise AIProviderError("Gemini provider is not configured.")
            from google import genai
            from google.genai import types

            # Explicitly configure SDK HTTP retry options with attempts=1 to disable internal SDK retries.
            # The application gateway / GeminiProvider is the sole owner of the retry policy.
            timeout_ms = int(self.config.timeout_seconds * 1000)
            http_options = types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                timeout=timeout_ms,
            )
            self._client = genai.Client(api_key=self.config.api_key, http_options=http_options)
        return self._client

    def is_in_cooldown(self) -> bool:
        return time.time() < self._rate_limited_until

    def set_cooldown(self, seconds: float) -> None:
        self._rate_limited_until = max(self._rate_limited_until, time.time() + max(1.0, seconds))

    def is_model_in_cooldown(self, model: str) -> bool:
        return time.time() < self._model_cooldowns.get(model, 0.0)

    def set_model_cooldown(self, model: str, seconds: float) -> None:
        self._model_cooldowns[model] = max(self._model_cooldowns.get(model, 0.0), time.time() + max(1.0, seconds))

    def disable_model(self, model: str) -> None:
        self._disabled_models.add(model)

    def get_diagnostics(self) -> list[dict[str, Any]]:
        return list(self._diagnostics)

    def _record_diagnostic(
        self,
        *,
        timestamp: str,
        correlation_id: str,
        requested_model: str,
        response_model: str,
        status_code: int | None,
        error_category: str,
        attempt_number: int,
        latency_ms: float,
        retry_delay_seconds: float | None,
        retry_reason: str | None,
        fallback_target: str | None,
        fallback_reason: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        outcome: str,
    ) -> None:
        rec = {
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "provider": "gemini",
            "requested_model": requested_model,
            "response_model": response_model,
            "status_code": status_code,
            "error_category": error_category,
            "attempt_number": attempt_number,
            "latency_ms": latency_ms,
            "retry_delay_seconds": retry_delay_seconds,
            "retry_reason": retry_reason,
            "fallback_target": fallback_target,
            "fallback_reason": fallback_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "outcome": outcome,
        }
        self._diagnostics.append(rec)
        logger.info(
            "Gemini attempt [%s] #%d: model=%s status=%s outcome=%s latency=%.1fms",
            correlation_id, attempt_number, requested_model, status_code, outcome, latency_ms,
        )

    def status(self) -> dict[str, Any]:
        """Returns health status without performing any live inference."""
        if not self.config.is_configured:
            return {
                "provider": "gemini",
                "status": "NOT_CONFIGURED",
                "available": False,
                "model": self.config.model,
                "reason": "GEMINI_API_KEY is not configured or GEMINI_ENABLED=false.",
            }

        if self._auth_failed:
            return {
                "provider": "gemini",
                "status": "DEGRADED",
                "available": False,
                "model": self.config.model,
                "reason": "Gemini authentication failed (invalid key or permissions).",
            }

        now = time.time()
        if self._rate_limited_until > now:
            remaining = round(self._rate_limited_until - now, 1)
            return {
                "provider": "gemini",
                "status": "RATE_LIMITED",
                "available": False,
                "model": self.config.model,
                "cooldown_remaining_seconds": remaining,
                "reason": f"Gemini is rate-limited. Cooldown for {remaining}s.",
            }

        active_cooldowns = {
            m: round(t - now, 1) for m, t in self._model_cooldowns.items() if t > now
        }

        return {
            "provider": "gemini",
            "status": "AVAILABLE",
            "available": True,
            "model": self.config.model,
            "configured_models": {
                "primary": self.config.model,
                "fallback": self.config.fallback_model,
                "preview": self.config.preview_model,
                "preview_enabled": self.config.enable_preview_models,
            },
            "model_cooldowns": active_cooldowns,
            "disabled_models": list(self._disabled_models),
            "attempt_budget": {
                "max_upstream_attempts": MAX_GEMINI_UPSTREAM_ATTEMPTS,
                "primary_retries": self.config.retries,
                "secondary_retries": 0,
            },
            "paid_apis_allowed": self.config.allow_paid_apis,
            "monthly_budget_usd": self.config.monthly_budget_usd,
            "limits": {
                "timeout_seconds": self.config.timeout_seconds,
                "retries": self.config.retries,
                "max_output_tokens": self.config.max_output_tokens,
            },
        }

    async def _execute_generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        schema: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> tuple[Any, str]:
        if not self.config.is_configured:
            raise AIProviderError("Gemini provider is not configured.")

        if self._auth_failed:
            raise AIProviderAuthError("Gemini provider authentication previously failed.")

        if self.is_in_cooldown():
            remaining = round(self._rate_limited_until - time.time(), 1)
            raise AIProviderRateLimitError(
                f"Gemini provider is in cooldown ({remaining}s remaining).", retry_after=remaining
            )

        from google.genai import errors, types

        cid = correlation_id or uuid.uuid4().hex[:12]

        if model:
            models_to_try = [model]
        else:
            candidates = [self.config.model]
            if self.config.fallback_model and self.config.fallback_model != self.config.model:
                candidates.append(self.config.fallback_model)
            if (
                self.config.enable_preview_models
                and self.config.preview_model
                and self.config.preview_model not in candidates
            ):
                candidates.append(self.config.preview_model)
            models_to_try = candidates

        config_kwargs: dict[str, Any] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }
        if system:
            config_kwargs["system_instruction"] = system

        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = schema

        gen_config = types.GenerateContentConfig(**config_kwargs)

        total_attempts = 0
        overall_start = time.time()
        last_error: Exception | None = None

        for target_model in models_to_try:
            if target_model in self._disabled_models:
                logger.info("[%s] Skipping disabled model %s", cid, target_model)
                continue

            if self.is_model_in_cooldown(target_model):
                logger.info("[%s] Skipping model %s in cooldown", cid, target_model)
                continue

            # Primary model gets at most (1 + retries) attempts; fallback gets 1 attempt
            if target_model == self.config.model:
                max_model_attempts = 1 + self.config.retries
            else:
                max_model_attempts = 1

            for model_attempt in range(1, max_model_attempts + 1):
                if total_attempts >= MAX_GEMINI_UPSTREAM_ATTEMPTS:
                    logger.warning(
                        "[%s] Gemini upstream attempt budget (%d) reached.", cid, MAX_GEMINI_UPSTREAM_ATTEMPTS
                    )
                    break

                total_attempts += 1
                attempt_num = total_attempts
                t0 = time.time()

                curr_idx = models_to_try.index(target_model)
                next_target = models_to_try[curr_idx + 1] if curr_idx + 1 < len(models_to_try) else "ollama"

                try:
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=target_model,
                            contents=prompt,
                            config=gen_config,
                        ),
                        timeout=self.config.timeout_seconds,
                    )
                    lat_ms = (time.time() - t0) * 1000
                    resp_model = getattr(response, "model_version", None) or "unknown"
                    usage = getattr(response, "usage_metadata", None)

                    self._record_diagnostic(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        correlation_id=cid,
                        requested_model=target_model,
                        response_model=resp_model,
                        status_code=200,
                        error_category="NONE",
                        attempt_number=attempt_num,
                        latency_ms=round(lat_ms, 2),
                        retry_delay_seconds=None,
                        retry_reason=None,
                        fallback_target=None,
                        fallback_reason=None,
                        prompt_tokens=getattr(usage, "prompt_token_count", None),
                        completion_tokens=getattr(usage, "candidates_token_count", None),
                        total_tokens=getattr(usage, "total_token_count", None),
                        outcome="SUCCESS",
                    )
                    return response, target_model

                except errors.APIError as exc:
                    lat_ms = (time.time() - t0) * 1000
                    last_error = exc
                    code = getattr(exc, "code", None)
                    raw_msg = str(exc)
                    safe_msg = redact_secrets(raw_msg)
                    retry_after = _parse_retry_after(exc)

                    # 1. Permanent Auth / Permission (401, 403)
                    if code in (401, 403) or "PERMISSION_DENIED" in safe_msg or "API_KEY_INVALID" in safe_msg:
                        self._auth_failed = True
                        self._record_diagnostic(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            correlation_id=cid,
                            requested_model=target_model,
                            response_model="unknown",
                            status_code=code,
                            error_category="AUTH",
                            attempt_number=attempt_num,
                            latency_ms=round(lat_ms, 2),
                            retry_delay_seconds=None,
                            retry_reason=None,
                            fallback_target="ollama",
                            fallback_reason="authentication_failed",
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            outcome="FAILURE",
                        )
                        raise AIProviderAuthError(f"Gemini authentication failed: {safe_msg}") from exc

                    # 2. Permanent Client Error / Bad Request (400)
                    if code == 400:
                        self._record_diagnostic(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            correlation_id=cid,
                            requested_model=target_model,
                            response_model="unknown",
                            status_code=400,
                            error_category="INVALID_REQUEST",
                            attempt_number=attempt_num,
                            latency_ms=round(lat_ms, 2),
                            retry_delay_seconds=None,
                            retry_reason=None,
                            fallback_target=None,
                            fallback_reason=None,
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            outcome="FAILURE",
                        )
                        raise AIProviderInvalidRequestError(f"Gemini invalid request (HTTP 400): {safe_msg}") from exc

                    # 3. Model Not Found (404)
                    if code == 404 or "NOT_FOUND" in safe_msg:
                        if _is_model_not_found(exc, safe_msg):
                            self.disable_model(target_model)
                            self._record_diagnostic(
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                correlation_id=cid,
                                requested_model=target_model,
                                response_model="unknown",
                                status_code=404,
                                error_category="NOT_FOUND",
                                attempt_number=attempt_num,
                                latency_ms=round(lat_ms, 2),
                                retry_delay_seconds=None,
                                retry_reason=None,
                                fallback_target=next_target,
                                fallback_reason="model_not_found",
                                prompt_tokens=None,
                                completion_tokens=None,
                                total_tokens=None,
                                outcome="FAILURE",
                            )
                            # Model is invalid/deprecated; stop retrying this model and fall back to next model
                            break
                        else:
                            raise AIProviderInvalidRequestError(f"Gemini resource not found: {safe_msg}") from exc

                    # 4. Rate Limit / Quota Exceeded (429)
                    if code == 429 or "RESOURCE_EXHAUSTED" in safe_msg:
                        cooldown = retry_after or 60.0
                        self.set_model_cooldown(target_model, cooldown)
                        self.set_cooldown(cooldown)
                        self._record_diagnostic(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            correlation_id=cid,
                            requested_model=target_model,
                            response_model="unknown",
                            status_code=429,
                            error_category="RATE_LIMIT",
                            attempt_number=attempt_num,
                            latency_ms=round(lat_ms, 2),
                            retry_delay_seconds=cooldown,
                            retry_reason="rate_limit_exceeded",
                            fallback_target=next_target,
                            fallback_reason="model_rate_limited",
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            outcome="FAILURE",
                        )
                        # Do not immediately retry rate-limited model; break to try fallback model
                        break

                    # 5. Transient Server Errors (503 / 5xx)
                    if code and code >= 500:
                        remaining_budget = (self.config.timeout_seconds * 2) - (time.time() - overall_start)
                        can_retry_this = (
                            target_model == self.config.model
                            and model_attempt < max_model_attempts
                            and remaining_budget > 2.0
                            and total_attempts < MAX_GEMINI_UPSTREAM_ATTEMPTS
                        )

                        if can_retry_this:
                            if retry_after is not None and retry_after > 5.0:
                                self.set_model_cooldown(target_model, retry_after)
                                self._record_diagnostic(
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    correlation_id=cid,
                                    requested_model=target_model,
                                    response_model="unknown",
                                    status_code=code,
                                    error_category="UNAVAILABLE",
                                    attempt_number=attempt_num,
                                    latency_ms=round(lat_ms, 2),
                                    retry_delay_seconds=retry_after,
                                    retry_reason="retry_after_too_large",
                                    fallback_target=next_target,
                                    fallback_reason="failing_over_due_to_long_cooldown",
                                    prompt_tokens=None,
                                    completion_tokens=None,
                                    total_tokens=None,
                                    outcome="FAILURE",
                                )
                                break

                            backoff = (
                                retry_after
                                if (retry_after and retry_after <= 5.0)
                                else (1.0 + random.uniform(0.0, 0.5))
                            )
                            self._record_diagnostic(
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                correlation_id=cid,
                                requested_model=target_model,
                                response_model="unknown",
                                status_code=code,
                                error_category="UNAVAILABLE",
                                attempt_number=attempt_num,
                                latency_ms=round(lat_ms, 2),
                                retry_delay_seconds=round(backoff, 2),
                                retry_reason="transient_server_error",
                                fallback_target=None,
                                fallback_reason=None,
                                prompt_tokens=None,
                                completion_tokens=None,
                                total_tokens=None,
                                outcome="FAILURE",
                            )
                            await asyncio.sleep(backoff)
                            continue
                        else:
                            self.set_model_cooldown(target_model, 60.0)
                            self._record_diagnostic(
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                correlation_id=cid,
                                requested_model=target_model,
                                response_model="unknown",
                                status_code=code,
                                error_category="UNAVAILABLE",
                                attempt_number=attempt_num,
                                latency_ms=round(lat_ms, 2),
                                retry_delay_seconds=None,
                                retry_reason=None,
                                fallback_target=next_target,
                                fallback_reason="model_attempts_exhausted",
                                prompt_tokens=None,
                                completion_tokens=None,
                                total_tokens=None,
                                outcome="FAILURE",
                            )
                            break

                    # Any other APIError
                    self._record_diagnostic(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        correlation_id=cid,
                        requested_model=target_model,
                        response_model="unknown",
                        status_code=code,
                        error_category="ERROR",
                        attempt_number=attempt_num,
                        latency_ms=round(lat_ms, 2),
                        retry_delay_seconds=None,
                        retry_reason=None,
                        fallback_target=next_target,
                        fallback_reason="api_error",
                        prompt_tokens=None,
                        completion_tokens=None,
                        total_tokens=None,
                        outcome="FAILURE",
                    )
                    break

                except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
                    lat_ms = (time.time() - t0) * 1000
                    last_error = exc
                    remaining_budget = (self.config.timeout_seconds * 2) - (time.time() - overall_start)
                    can_retry_this = (
                        target_model == self.config.model
                        and model_attempt < max_model_attempts
                        and remaining_budget > 2.0
                        and total_attempts < MAX_GEMINI_UPSTREAM_ATTEMPTS
                    )

                    if can_retry_this:
                        backoff = 1.0 + random.uniform(0.0, 0.5)
                        self._record_diagnostic(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            correlation_id=cid,
                            requested_model=target_model,
                            response_model="unknown",
                            status_code=504,
                            error_category="TIMEOUT",
                            attempt_number=attempt_num,
                            latency_ms=round(lat_ms, 2),
                            retry_delay_seconds=round(backoff, 2),
                            retry_reason="timeout_retry",
                            fallback_target=None,
                            fallback_reason=None,
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            outcome="FAILURE",
                        )
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        self.set_model_cooldown(target_model, 60.0)
                        self._record_diagnostic(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            correlation_id=cid,
                            requested_model=target_model,
                            response_model="unknown",
                            status_code=504,
                            error_category="TIMEOUT",
                            attempt_number=attempt_num,
                            latency_ms=round(lat_ms, 2),
                            retry_delay_seconds=None,
                            retry_reason=None,
                            fallback_target=next_target,
                            fallback_reason="timeout_attempts_exhausted",
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            outcome="FAILURE",
                        )
                        break

                except Exception as exc:
                    if isinstance(exc, (AIProviderError,)):
                        raise
                    lat_ms = (time.time() - t0) * 1000
                    last_error = exc
                    self._record_diagnostic(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        correlation_id=cid,
                        requested_model=target_model,
                        response_model="unknown",
                        status_code=None,
                        error_category="UNEXPECTED",
                        attempt_number=attempt_num,
                        latency_ms=round(lat_ms, 2),
                        retry_delay_seconds=None,
                        retry_reason=None,
                        fallback_target=next_target,
                        fallback_reason="unexpected_exception",
                        prompt_tokens=None,
                        completion_tokens=None,
                        total_tokens=None,
                        outcome="FAILURE",
                    )
                    break

        if self._auth_failed:
            raise AIProviderAuthError("Gemini authentication failed.")
        if isinstance(last_error, asyncio.TimeoutError):
            raise AIProviderTimeoutError(
                f"Gemini request timed out after {self.config.timeout_seconds}s."
            ) from last_error
        if getattr(last_error, "code", None) == 429:
            raise AIProviderRateLimitError("Gemini rate limit exceeded.", retry_after=60.0) from last_error
        raise AIProviderUnavailableError(
            f"All configured Gemini models failed. Last error: {redact_secrets(str(last_error))}"
        )

    async def generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> str:
        response, _ = await self._execute_generate(
            prompt, system=system, model=model, correlation_id=correlation_id
        )
        text = response.text if hasattr(response, "text") else None
        if not text or not text.strip():
            raise AIProviderError("Gemini returned an empty response.")
        return text

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str = "",
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response, used_model = await self._execute_generate(
            prompt, system=system, model=model, schema=schema, correlation_id=correlation_id
        )
        text = response.text if hasattr(response, "text") else None
        if not text or not text.strip():
            raise AIProviderError("Gemini returned an empty structured response.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise AIProviderError("Gemini returned invalid JSON for a structured response.") from error
        if not isinstance(data, dict):
            raise AIProviderError("Gemini structured response must be a JSON object.")

        usage_meta = getattr(response, "usage_metadata", None)
        resp_model_version = getattr(response, "model_version", None) or "unknown"
        metadata = {
            "model": used_model,
            "response_model_version": resp_model_version,
            "provider": "gemini",
            "prompt_tokens": getattr(usage_meta, "prompt_token_count", None),
            "completion_tokens": getattr(usage_meta, "candidates_token_count", None),
            "total_tokens": getattr(usage_meta, "total_token_count", None),
            "correlation_id": correlation_id,
        }
        return data, metadata
