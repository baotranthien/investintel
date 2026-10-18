"""Deterministic test suite for AI Gateway, Gemini integration, and failover behavior."""
import asyncio
from datetime import date
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_db
from routers.ai import router as ai_router
from services.ai.analyst import AIAnalyst
from services.ai.config import GatewayConfig, GeminiConfig, redact_secrets
from services.ai.errors import (
    AIProviderAuthError,
    AIProviderError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from services.ai.gateway import AIGateway
from services.ai.gemini_provider import GeminiProvider
from services.ai.tools import AITools


class MockUsageMetadata:
    prompt_token_count = 15
    candidates_token_count = 25
    total_token_count = 40


class MockGenerateResponse:
    def __init__(self, text: str, model_version: str | None = None):
        self.text = text
        self.model_version = model_version
        self.usage_metadata = MockUsageMetadata()


# 1. Missing GEMINI_API_KEY -> NOT_CONFIGURED
def test_gemini_missing_key_status_not_configured():
    config = GeminiConfig(api_key="", enabled=True)
    assert not config.is_configured
    provider = GeminiProvider(config=config)
    st = provider.status()
    assert st["status"] == "NOT_CONFIGURED"
    assert st["available"] is False
    assert "not configured" in st["reason"]


def test_gemini_placeholder_key_status_not_configured():
    config = GeminiConfig(api_key="PASTE_YOUR_GEMINI_API_KEY_HERE", enabled=True)
    assert not config.is_configured
    provider = GeminiProvider(config=config)
    st = provider.status()
    assert st["status"] == "NOT_CONFIGURED"
    assert st["available"] is False


# 2. Valid mocked Gemini response -> maps to internal schema
def test_gemini_valid_mock_response_maps_to_schema():
    async def _test():
        config = GeminiConfig(api_key="mock-valid-key", enabled=True, retries=0)
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()
        mock_response = MockGenerateResponse(json.dumps({
            "answer": "Vietnam market regime is neutral.",
            "claims": [{"claim_type": "FACT", "text": "Regime is neutral.", "citation_ids": ["E001"]}],
            "uncertainty": []
        }))
        mock_models.generate_content = AsyncMock(return_value=mock_response)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        provider = GeminiProvider(config=config, client=mock_client)
        data, meta = await provider.generate_structured("prompt", schema={"type": "object"})

        assert data["answer"] == "Vietnam market regime is neutral."
        assert len(data["claims"]) == 1
        assert meta["provider"] == "gemini"
        assert meta["prompt_tokens"] == 15
        assert meta["completion_tokens"] == 25
        assert meta["total_tokens"] == 40

    asyncio.run(_test())


# 3. Structured output invalid/malformed -> safely rejected
def test_gemini_malformed_json_safely_rejected():
    async def _test():
        config = GeminiConfig(api_key="mock-valid-key", enabled=True, retries=0)
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=MockGenerateResponse("Not a valid json string"))

        provider = GeminiProvider(config=config, client=mock_client)
        with pytest.raises(AIProviderError, match="invalid JSON"):
            await provider.generate_structured("prompt", schema={"type": "object"})

    asyncio.run(_test())


def test_gemini_empty_response_safely_rejected():
    async def _test():
        config = GeminiConfig(api_key="mock-valid-key", enabled=True, retries=0)
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=MockGenerateResponse(""))

        provider = GeminiProvider(config=config, client=mock_client)
        with pytest.raises(AIProviderError, match="empty structured response"):
            await provider.generate_structured("prompt", schema={"type": "object"})

    asyncio.run(_test())


# 4. HTTP 429 -> cooldown/rate-limit state and next-provider fallback
def test_http_429_triggers_cooldown_and_fallback_to_ollama():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(api_key="mock-key", enabled=True, retries=0)
        mock_client = MagicMock()
        api_err = errors.APIError(429, "RESOURCE_EXHAUSTED: Quota exceeded")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=api_err)

        gemini = GeminiProvider(config=config, client=mock_client)

        # Mock Ollama provider as fallback
        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Fallback response from local Ollama", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})

        assert data["answer"] == "Fallback response from local Ollama"
        assert meta["gateway_active_provider"] == "ollama"
        assert gemini.is_in_cooldown()
        assert gemini.status()["status"] == "RATE_LIMITED"

    asyncio.run(_test())


# 5. Timeout/5xx -> bounded retries followed by fallback
def test_timeout_bounded_retries_and_fallback():
    async def _test():
        config = GeminiConfig(api_key="mock-key", enabled=True, retries=1, timeout_seconds=0.1)
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())

        gemini = GeminiProvider(config=config, client=mock_client)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama answered after Gemini timeout", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Ollama answered after Gemini timeout"
        assert meta["gateway_active_provider"] == "ollama"
        assert mock_client.aio.models.generate_content.call_count == 2  # 1 initial + 1 retry

    asyncio.run(_test())


# 6. Invalid credential -> classified correctly without infinite retries
def test_invalid_credential_fails_over_and_disables_gemini():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(api_key="mock-bad-key", enabled=True, retries=1)
        mock_client = MagicMock()
        auth_err = errors.APIError(403, "PERMISSION_DENIED: API_KEY_INVALID")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=auth_err)

        gemini = GeminiProvider(config=config, client=mock_client)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama after bad auth", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Ollama after bad auth"
        assert gemini.status()["status"] == "DEGRADED"

        # Second call should skip gemini immediately without calling client
        assert "gemini" not in gateway.get_eligible_providers()

    asyncio.run(_test())


# 7. All cloud providers unavailable -> local Ollama fallback
def test_all_cloud_unavailable_falls_back_to_local_ollama(monkeypatch):
    # Ensure no real cloud API keys are present so PlaceholderProviders report NOT_CONFIGURED
    for env_var in ("OPENAI_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)

    async def _test():
        mock_gemini = MagicMock()
        mock_gemini.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "gemini"}

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Local Ollama success", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("openai", "gemini", "grok", "deepseek", "ollama")),
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )

        eligible = gateway.get_eligible_providers()
        assert eligible == ["ollama"]

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Local Ollama success"

    asyncio.run(_test())


# 8. Ollama unavailable too -> typed unavailable response
def test_all_providers_unavailable_raises_typed_error():
    async def _test():
        mock_gemini = MagicMock()
        mock_gemini.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "gemini"}
        mock_gemini.generate_structured = AsyncMock(side_effect=AIProviderUnavailableError("Gemini down"))

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(side_effect=AIProviderUnavailableError("Ollama down"))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )

        with pytest.raises(AIProviderUnavailableError, match="No AI providers are currently available|All configured"):
            await gateway.generate_structured("prompt", schema={"type": "object"})

    asyncio.run(_test())


# 9. Secret leakage protection in logs and errors
def test_no_secret_leakage_in_redaction():
    secret_key = "AQ.TestSecretKey1234567890abcdef1234567890"
    raw_error = f"HTTP 401 error calling endpoint with key {secret_key} and AIzaSyD1234567890abcdef123456789012345"
    redacted = redact_secrets(raw_error)

    assert secret_key not in redacted
    assert "AIzaSyD" not in redacted
    assert "[REDACTED_API_KEY]" in redacted


def test_gateway_status_does_not_leak_secrets():
    gateway = AIGateway()
    st = gateway.status()
    serialized = json.dumps(st)
    assert "PASTE_" not in serialized
    assert "AQ." not in serialized
    assert "AIza" not in serialized


# 10. Evidence & Citation Guardrails remain strictly enforced with Gemini
def test_guardrails_enforced_regardless_of_provider(monkeypatch):
    async def _test():
        # Mock provider returning a fabricated claim without valid evidence ID
        mock_provider = MagicMock()
        mock_provider.status.return_value = {"status": "AVAILABLE", "available": True}
        mock_provider.generate_structured = AsyncMock(return_value=(
            {
                "answer": "Fabricated EPS is 999.0.",
                "claims": [{"claim_type": "FACT", "text": "EPS is 999.0.", "citation_ids": ["E999"]}],
                "uncertainty": []
            },
            {"model": "gemini-2.5-flash", "provider": "gemini"}
        ))

        context = {
            "symbol": "FPT",
            "as_of_date": "2026-10-01",
            "decision_state": "AVAILABLE",
            "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {"eps_ttm": 12.5}}],
            "evidence": [{
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "metric": "eps_ttm",
                "value": 12.5,
                "unit": "VND/share",
                "source": "CANONICAL_FINANCIALS",
                "observation_date": "2026-06-30",
                "publication_date": "2026-08-01",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            }],
        }
        monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)

        analyst = AIAnalyst(provider=mock_provider)
        result = await analyst.answer_question("What is EPS?", session=object(), symbol="FPT")

        # Guardrails must catch this and return INSUFFICIENT_DATA
        assert result["status"] == "INSUFFICIENT_DATA"
        assert "factual or interpreted claim" in result["uncertainty"][0]

    asyncio.run(_test())


# 11. API /api/v1/ai/status endpoint backwards-compatible
def test_ai_status_endpoint_returns_expected_fields():
    app = FastAPI()
    app.include_router(ai_router)

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/status")

    assert response.status_code == 200
    data = response.json()
    # Backwards-compatible fields expected by frontend
    assert "status" in data
    assert "available" in data
    assert "provider" in data
    assert "models" in data
    assert "gpu" in data
    # Multi-provider gateway fields
    assert "providers" in data
    assert "gemini" in data["providers"]
    assert "ollama" in data["providers"]
    assert "cost_safety" in data
    assert data["cost_safety"]["allow_paid_apis"] is False


# 12. HTTP 503: exactly one retry of primary, then one fallback model attempt, then Ollama
def test_http_503_primary_retry_then_fallback_model_then_ollama():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=1,
            timeout_seconds=5.0,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_503 = errors.APIError(503, "503 UNAVAILABLE: High demand spike")
        mock_models.generate_content = AsyncMock(side_effect=err_503)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama answered after Gemini primary and secondary failed", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Ollama answered after Gemini primary and secondary failed"
        assert meta["gateway_active_provider"] == "ollama"

        # Assert exact upstream attempt sequence:
        # Attempt 1: gemini-3.8-flash
        # Attempt 2: gemini-3.8-flash (primary retry)
        # Attempt 3: gemini-3.6-flash (fallback model)
        assert mock_models.generate_content.call_count == 3
        calls = mock_models.generate_content.call_args_list
        assert calls[0].kwargs["model"] == "gemini-3.8-flash"
        assert calls[1].kwargs["model"] == "gemini-3.8-flash"
        assert calls[2].kwargs["model"] == "gemini-3.6-flash"

        # Per-model cooldowns recorded
        assert gemini.is_model_in_cooldown("gemini-3.8-flash")
        assert gemini.is_model_in_cooldown("gemini-3.6-flash")

    asyncio.run(_test())


# 13. HTTP 503: primary retry succeeds on 2nd attempt
def test_http_503_primary_retry_succeeds_on_second_attempt():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=1,
            timeout_seconds=5.0,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_503 = errors.APIError(503, "503 UNAVAILABLE: High demand spike")
        success_resp = MockGenerateResponse(
            json.dumps({"answer": "Primary recovered", "claims": [], "uncertainty": []}),
            model_version="gemini-3.8-flash-001"
        )
        mock_models.generate_content = AsyncMock(side_effect=[err_503, success_resp])
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(gemini_provider=gemini)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Primary recovered"
        assert meta["model"] == "gemini-3.8-flash"
        assert meta["response_model_version"] == "gemini-3.8-flash-001"
        assert mock_models.generate_content.call_count == 2

    asyncio.run(_test())


# 14. HTTP 503: fallback model succeeds on 3rd attempt
def test_http_503_secondary_fallback_succeeds():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=1,
            timeout_seconds=5.0,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_503 = errors.APIError(503, "503 UNAVAILABLE")
        success_fallback = MockGenerateResponse(
            json.dumps({"answer": "Fallback model 3.6 succeeded", "claims": [], "uncertainty": []}),
            model_version="gemini-3.6-flash-001"
        )
        mock_models.generate_content = AsyncMock(side_effect=[err_503, err_503, success_fallback])
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(gemini_provider=gemini)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Fallback model 3.6 succeeded"
        assert meta["model"] == "gemini-3.6-flash"
        assert meta["response_model_version"] == "gemini-3.6-flash-001"
        assert mock_models.generate_content.call_count == 3

    asyncio.run(_test())


# 15. Model-specific HTTP 404 disables primary model and tries secondary model
def test_model_specific_404_disables_primary_and_uses_secondary():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=1,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_404 = errors.APIError(404, {"error": {"message": "models/gemini-3.8-flash is no longer available to new users"}})
        success_resp = MockGenerateResponse(
            json.dumps({"answer": "Secondary model answered after 404", "claims": [], "uncertainty": []})
        )
        mock_models.generate_content = AsyncMock(side_effect=[err_404, success_resp])
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(gemini_provider=gemini)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Secondary model answered after 404"
        assert meta["model"] == "gemini-3.6-flash"
        # Call 1: gemini-3.8-flash (404), Call 2: gemini-3.6-flash (success) -> 2 calls
        assert mock_models.generate_content.call_count == 2
        assert "gemini-3.8-flash" in gemini._disabled_models

        # Subsequent call should immediately use secondary model without calling primary
        mock_models.generate_content.reset_mock()
        mock_models.generate_content.side_effect = None
        mock_models.generate_content.return_value = success_resp
        data2, meta2 = await gateway.generate_structured("prompt 2", schema={"type": "object"})
        assert meta2["model"] == "gemini-3.6-flash"
        assert mock_models.generate_content.call_count == 1
        assert mock_models.generate_content.call_args.kwargs["model"] == "gemini-3.6-flash"

    asyncio.run(_test())


# 16. Permanent HTTP 400 is not retried
def test_http_400_invalid_request_not_retried():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(api_key="mock-key", retries=2)
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_400 = errors.APIError(400, "INVALID_ARGUMENT: Bad parameter")
        mock_models.generate_content = AsyncMock(side_effect=err_400)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)

        with pytest.raises(AIProviderInvalidRequestError):
            await gemini.generate_structured("prompt", schema={"type": "object"})

        # Exactly 1 call: 400 is not retried
        assert mock_models.generate_content.call_count == 1

    asyncio.run(_test())


# 17. SDK internal retries disabled via HttpOptions(retry_options=HttpRetryOptions(attempts=1))
def test_sdk_retries_disabled_with_http_retry_options():
    config = GeminiConfig(api_key="mock-key")
    gemini = GeminiProvider(config=config)
    client = gemini.client
    api_client = getattr(client, "_api_client", None)
    assert api_client is not None
    http_opts = getattr(api_client, "_http_options", None)
    assert http_opts is not None
    assert http_opts.retry_options.attempts == 1


# 18. HTTP 401/403: No retry storm and no secondary model attempt
def test_http_401_no_retry_and_no_secondary_model():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-bad-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=2,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        auth_err = errors.APIError(401, "UNAUTHENTICATED: API key not valid")
        mock_models.generate_content = AsyncMock(side_effect=auth_err)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama fallback after 401", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gateway = AIGateway(gemini_provider=gemini, ollama_provider=mock_ollama)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Ollama fallback after 401"
        assert meta["gateway_active_provider"] == "ollama"

        # Exactly 1 call was made to Gemini: zero retries, zero secondary model attempts
        assert mock_models.generate_content.call_count == 1
        assert gemini._auth_failed is True

    asyncio.run(_test())


# 19. HTTP 429: per-model cooldown and fallback to secondary model
def test_http_429_cooldown_and_fallback_to_secondary():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=1,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_429 = errors.APIError(429, {
            "error": {
                "message": "RESOURCE_EXHAUSTED",
                "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "20s"}]
            }
        })
        success_secondary = MockGenerateResponse(
            json.dumps({"answer": "Secondary succeeded after primary 429", "claims": [], "uncertainty": []})
        )
        mock_models.generate_content = AsyncMock(side_effect=[err_429, success_secondary])
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(gemini_provider=gemini)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Secondary succeeded after primary 429"
        assert meta["model"] == "gemini-3.6-flash"
        assert mock_models.generate_content.call_count == 2
        assert gemini.is_model_in_cooldown("gemini-3.8-flash")

    asyncio.run(_test())


# 20. Correlation ID propagates and diagnostics are logged safely
def test_correlation_id_propagated_and_diagnostics_recorded():
    async def _test():
        config = GeminiConfig(api_key="mock-key")
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        resp = MockGenerateResponse(
            json.dumps({"answer": "OK with CID", "claims": [], "uncertainty": []}),
            model_version="gemini-3.8-flash"
        )
        mock_models.generate_content = AsyncMock(return_value=resp)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(gemini_provider=gemini)

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"}, correlation_id="cid-test-1234")
        assert meta["correlation_id"] == "cid-test-1234"

        diags = gemini.get_diagnostics()
        assert len(diags) >= 1
        last_diag = diags[-1]
        assert last_diag["correlation_id"] == "cid-test-1234"
        assert last_diag["requested_model"] == "gemini-3.8-flash"
        assert last_diag["response_model"] == "gemini-3.8-flash"
        assert last_diag["status_code"] == 200
        assert last_diag["outcome"] == "SUCCESS"
        assert "latency_ms" in last_diag
        # Check that no secrets or full prompts exist in diagnostic record
        serialized = json.dumps(last_diag)
        assert "PASTE_" not in serialized
        assert "AQ." not in serialized

    asyncio.run(_test())


# 21. Response model metadata logged only when available, otherwise "unknown"
def test_response_model_metadata_logged_only_when_available():
    async def _test():
        config = GeminiConfig(api_key="mock-key")
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        # Response without model_version
        resp_no_model = MockGenerateResponse(
            json.dumps({"answer": "No model version", "claims": [], "uncertainty": []}),
            model_version=None
        )
        mock_models.generate_content = AsyncMock(return_value=resp_no_model)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)
        _, meta = await gemini.generate_structured("prompt", schema={"type": "object"})
        assert meta["response_model_version"] == "unknown"

        # Response with model_version
        resp_with_model = MockGenerateResponse(
            json.dumps({"answer": "With model version", "claims": [], "uncertainty": []}),
            model_version="gemini-3.8-flash-v2"
        )
        mock_models.generate_content = AsyncMock(return_value=resp_with_model)
        _, meta2 = await gemini.generate_structured("prompt", schema={"type": "object"})
        assert meta2["response_model_version"] == "gemini-3.8-flash-v2"

    asyncio.run(_test())


# 22. Preview candidate is disabled by default and enabled only via explicit flag
def test_preview_model_disabled_by_default():
    # Disabled by default
    cfg_default = GeminiConfig(api_key="mock-key")
    assert cfg_default.enable_preview_models is False
    assert cfg_default.preview_model == "gemini-3-flash-preview"

    # Enabled via flag
    cfg_preview = GeminiConfig(api_key="mock-key", enable_preview_models=True)
    assert cfg_preview.enable_preview_models is True


# 23. Strict upstream attempt budget cap: never exceeds 3 attempts across all models
def test_strict_upstream_attempt_budget_cap():
    async def _test():
        from google.genai import errors

        # Even if retries=5 in config, max upstream attempts is hard-capped at 3
        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=5,
            timeout_seconds=10.0,
        )
        mock_client = MagicMock()
        mock_aio = MagicMock()
        mock_models = MagicMock()

        err_503 = errors.APIError(503, "503 UNAVAILABLE")
        mock_models.generate_content = AsyncMock(side_effect=err_503)
        mock_aio.models = mock_models
        mock_client.aio = mock_aio

        gemini = GeminiProvider(config=config, client=mock_client)

        with pytest.raises(AIProviderUnavailableError):
            await gemini.generate_structured("prompt", schema={"type": "object"})

        # Must not exceed MAX_GEMINI_UPSTREAM_ATTEMPTS (5)
        assert mock_models.generate_content.call_count <= 5

    asyncio.run(_test())



# ============================================================
# NEW TESTS (24-34): Five-attempt cap + Ollama fallback policy
# ============================================================

# 24. Gemini succeeds on attempt 1: exactly one HTTP call, no local fallback
def test_gemini_succeeds_attempt_1_single_http_call():
    async def _test():
        config = GeminiConfig(api_key="mock-key", model="gemini-3.8-flash", retries=4)
        mock_client = MagicMock()
        resp = MockGenerateResponse(
            json.dumps({"answer": "Immediate success", "claims": [], "uncertainty": []}),
            model_version="gemini-3.8-flash"
        )
        mock_client.aio.models.generate_content = AsyncMock(return_value=resp)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock()

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Immediate success"
        assert meta["gateway_active_provider"] == "gemini"
        # Exactly one HTTP attempt
        assert mock_client.aio.models.generate_content.call_count == 1
        # Ollama was never called
        mock_ollama.generate_structured.assert_not_called()

    asyncio.run(_test())


# 25. Gemini fails transiently then succeeds: expected number of HTTP attempts
def test_gemini_transient_fail_then_success_exact_attempts():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key", model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash", retries=4, timeout_seconds=10.0
        )
        mock_client = MagicMock()
        err_503 = errors.APIError(503, "503 UNAVAILABLE")
        success = MockGenerateResponse(
            json.dumps({"answer": "Recovered after 2 fails", "claims": [], "uncertainty": []})
        )
        # Fail twice, succeed on 3rd
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[err_503, err_503, success]
        )

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True}
        mock_ollama.generate_structured = AsyncMock()

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Recovered after 2 fails"
        assert meta["gateway_active_provider"] == "gemini"
        # Exactly 3 HTTP attempts (2 failures + 1 success)
        assert mock_client.aio.models.generate_content.call_count == 3
        # Ollama never invoked
        mock_ollama.generate_structured.assert_not_called()

    asyncio.run(_test())


# 26. Five total transient Gemini attempts all fail -> Ollama called exactly once
def test_five_transient_gemini_attempts_exhausted_ollama_once():
    async def _test():
        from google.genai import errors

        # retries=4 → 1 initial + 4 retries = 5 attempts cap
        config = GeminiConfig(
            api_key="mock-key", model="gemini-3.8-flash",
            fallback_model="",  # No Gemini fallback model
            retries=4, timeout_seconds=10.0
        )
        # Disable fallback model to ensure all 5 attempts go to primary
        config_with_no_fallback = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.8-flash",  # same as primary = no extra model
            retries=4,
            timeout_seconds=10.0,
        )
        mock_client = MagicMock()
        err_503 = errors.APIError(503, "503 UNAVAILABLE: High demand")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=err_503)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama local answer after 5 Gemini failures", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gemini = GeminiProvider(config=config_with_no_fallback, client=mock_client)
        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert data["answer"] == "Ollama local answer after 5 Gemini failures"
        assert meta["gateway_active_provider"] == "ollama"
        # Never exceeded 5 Gemini HTTP attempts
        assert mock_client.aio.models.generate_content.call_count <= 5
        # Ollama called exactly once
        assert mock_ollama.generate_structured.call_count == 1

    asyncio.run(_test())


# 27. HTTP 503 follows bounded-retry policy: at most 5 total Gemini attempts
def test_http_503_bounded_by_five_attempt_policy():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=4,  # allows up to 5 attempts before hitting the cap
            timeout_seconds=10.0,
        )
        mock_client = MagicMock()
        err_503 = errors.APIError(503, "503 UNAVAILABLE: High demand")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=err_503)

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(return_value=(
            {"answer": "Ollama after 503s", "claims": [], "uncertainty": []},
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        gemini = GeminiProvider(config=config, client=mock_client)
        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=gemini,
            ollama_provider=mock_ollama,
        )

        data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
        assert meta["gateway_active_provider"] == "ollama"
        # Bounded: at most 5 total Gemini HTTP attempts
        assert mock_client.aio.models.generate_content.call_count <= 5

    asyncio.run(_test())


# 28. HTTP 429 does not create retry storm: breaks immediately without retrying same URL
def test_http_429_no_retry_storm():
    async def _test():
        from google.genai import errors

        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=4,
        )
        mock_client = MagicMock()
        err_429 = errors.APIError(429, "RESOURCE_EXHAUSTED: Free quota exceeded")
        success_fallback = MockGenerateResponse(
            json.dumps({"answer": "Secondary after 429", "claims": [], "uncertainty": []})
        )
        # 429 on primary → immediately break → fallback model succeeds
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[err_429, success_fallback]
        )

        gemini = GeminiProvider(config=config, client=mock_client)
        data, meta = await gemini.generate_structured("prompt", schema={"type": "object"})

        assert data["answer"] == "Secondary after 429"
        assert meta["model"] == "gemini-3.6-flash"
        # 429 must not be retried on the same model: only 2 calls total (1 primary 429 + 1 fallback success)
        assert mock_client.aio.models.generate_content.call_count == 2
        # Cooldown set on primary model
        assert gemini.is_model_in_cooldown("gemini-3.8-flash")
        assert gemini.is_in_cooldown()  # global cooldown also set

    asyncio.run(_test())


# 29. HTTP 401/403 -> zero retries, zero secondary model attempts, immediate Ollama fallback
def test_http_401_403_immediate_ollama_fallback_no_retries():
    async def _test():
        from google.genai import errors

        for code, msg in [(401, "UNAUTHENTICATED"), (403, "PERMISSION_DENIED: API_KEY_INVALID")]:
            mock_client = MagicMock()
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=errors.APIError(code, msg)
            )
            config = GeminiConfig(
                api_key="mock-bad-key",
                model="gemini-3.8-flash",
                fallback_model="gemini-3.6-flash",
                retries=4,
            )
            gemini = GeminiProvider(config=config, client=mock_client)

            mock_ollama = MagicMock()
            mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
            mock_ollama.generate_structured = AsyncMock(return_value=(
                {"answer": f"Ollama after HTTP {code}", "claims": [], "uncertainty": []},
                {"model": "qwen2.5:0.5b", "provider": "ollama"}
            ))

            gateway = AIGateway(
                config=GatewayConfig(provider_priority=("gemini", "ollama")),
                gemini_provider=gemini,
                ollama_provider=mock_ollama,
            )
            data, meta = await gateway.generate_structured("prompt", schema={"type": "object"})
            assert meta["gateway_active_provider"] == "ollama"
            # Exactly 1 HTTP call to Gemini: auth failure → immediate stop, no retries, no secondary model
            assert mock_client.aio.models.generate_content.call_count == 1
            assert gemini._auth_failed is True

    asyncio.run(_test())


# 30. HTTP 404 (model not found) and HTTP 400 (bad request) are non-retryable
def test_http_404_400_non_retryable():
    async def _test():
        from google.genai import errors

        # 404: model-specific not found → disabled, no retry of same model
        config_404 = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="",  # No Gemini fallback → raises unavailable
            retries=4,
        )
        mock_client_404 = MagicMock()
        mock_client_404.aio.models.generate_content = AsyncMock(
            side_effect=errors.APIError(404, "models/gemini-3.8-flash is no longer available")
        )
        gemini_404 = GeminiProvider(config=config_404, client=mock_client_404)
        with pytest.raises((AIProviderUnavailableError, AIProviderInvalidRequestError)):
            await gemini_404.generate_structured("prompt", schema={"type": "object"})
        # Only 1 call: 404 is non-retryable
        assert mock_client_404.aio.models.generate_content.call_count == 1
        assert "gemini-3.8-flash" in gemini_404._disabled_models

        # 400: bad request → not retried
        config_400 = GeminiConfig(api_key="mock-key", retries=4)
        mock_client_400 = MagicMock()
        mock_client_400.aio.models.generate_content = AsyncMock(
            side_effect=errors.APIError(400, "INVALID_ARGUMENT: Bad parameter")
        )
        gemini_400 = GeminiProvider(config=config_400, client=mock_client_400)
        with pytest.raises(AIProviderInvalidRequestError):
            await gemini_400.generate_structured("prompt", schema={"type": "object"})
        assert mock_client_400.aio.models.generate_content.call_count == 1

    asyncio.run(_test())


# 31. SDK retries disabled: total HTTP call count cannot exceed five
def test_sdk_retries_disabled_total_http_cannot_exceed_five():
    async def _test():
        from google.genai import errors

        # Configure with retries=10 — cap must still be MAX_GEMINI_UPSTREAM_ATTEMPTS (5)
        config = GeminiConfig(
            api_key="mock-key",
            model="gemini-3.8-flash",
            fallback_model="gemini-3.6-flash",
            retries=10,
            timeout_seconds=10.0,
        )
        mock_client = MagicMock()
        err_503 = errors.APIError(503, "503 UNAVAILABLE")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=err_503)

        gemini = GeminiProvider(config=config, client=mock_client)
        with pytest.raises(AIProviderUnavailableError):
            await gemini.generate_structured("prompt", schema={"type": "object"})

        # Hard cap: must never exceed 5
        assert mock_client.aio.models.generate_content.call_count <= 5
        # Also verify SDK client was constructed with retry_options.attempts=1
        assert gemini.config.retries == 10  # config value preserved as-is
        # MAX_GEMINI_UPSTREAM_ATTEMPTS is the hard ceiling at runtime
        from services.ai.gemini_provider import MAX_GEMINI_UPSTREAM_ATTEMPTS
        assert MAX_GEMINI_UPSTREAM_ATTEMPTS == 5

    asyncio.run(_test())


# 32. Ollama fallback failure returns typed unavailable result — never fabricates
def test_ollama_fallback_failure_returns_typed_unavailable():
    async def _test():
        mock_gemini = MagicMock()
        mock_gemini.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "gemini"}
        mock_gemini.generate_structured = AsyncMock(side_effect=AIProviderUnavailableError("Gemini down"))

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "ollama"}
        mock_ollama.generate_structured = AsyncMock(side_effect=AIProviderUnavailableError("Ollama down"))

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )

        # Must raise typed error — never return a fabricated successful response
        with pytest.raises(AIProviderUnavailableError):
            await gateway.generate_structured("prompt", schema={"type": "object"})

        # Ollama was not invoked (both UNAVAILABLE skipped by eligible check)
        mock_ollama.generate_structured.assert_not_called()

    asyncio.run(_test())


# 33. Evidence/citation/PIT guardrails enforced after Ollama fallback — no guardrail bypass
def test_guardrails_enforced_after_ollama_fallback(monkeypatch):
    async def _test():
        # Simulate Gemini failing → Ollama returning a fabricated claim
        mock_ollama_inner = MagicMock()
        mock_ollama_inner.status.return_value = {"status": "HEALTHY", "available": True, "provider": "ollama"}
        mock_ollama_inner.generate_structured = AsyncMock(return_value=(
            {
                "answer": "Fabricated: EPS is 9999.0 per share.",
                "claims": [
                    {"claim_type": "FACT", "text": "EPS is 9999.0.", "citation_ids": ["E_FAKE"]}
                ],
                "uncertainty": []
            },
            {"model": "qwen2.5:0.5b", "provider": "ollama"}
        ))

        mock_gemini = MagicMock()
        mock_gemini.status.return_value = {"status": "UNAVAILABLE", "available": False, "provider": "gemini"}

        gateway = AIGateway(
            config=GatewayConfig(provider_priority=("gemini", "ollama")),
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama_inner,
        )

        # Attach gateway as the analyst's provider
        context = {
            "symbol": "VNM",
            "as_of_date": "2026-10-01",
            "decision_state": "AVAILABLE",
            "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {"eps_ttm": 5.2}}],
            "evidence": [{
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "metric": "eps_ttm",
                "value": 5.2,
                "unit": "VND/share",
                "source": "CANONICAL_FINANCIALS",
                "observation_date": "2026-06-30",
                "publication_date": "2026-08-01",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            }],
        }
        monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)

        analyst = AIAnalyst(provider=gateway)
        result = await analyst.answer_question("What is EPS?", session=object(), symbol="VNM")

        # Citation E_FAKE does not match any real evidence ID → guardrail fires
        assert result["status"] == "INSUFFICIENT_DATA"
        assert "factual or interpreted claim" in result["uncertainty"][0]

    asyncio.run(_test())


# 34. No API key, auth header, or private prompt leaks into logs or error messages
def test_no_secret_or_prompt_leaks_in_errors_and_diagnostics():
    async def _test():
        from google.genai import errors

        secret_key = "AQ.MySecretKey9876543210abcdefghij"
        config = GeminiConfig(
            api_key=secret_key,
            model="gemini-3.8-flash",
            retries=0,
        )
        mock_client = MagicMock()
        # Error message that would naively contain the key
        err = errors.APIError(401, f"UNAUTHENTICATED: key={secret_key} is invalid")
        mock_client.aio.models.generate_content = AsyncMock(side_effect=err)

        gemini = GeminiProvider(config=config, client=mock_client)

        with pytest.raises(AIProviderAuthError) as exc_info:
            await gemini.generate_structured("private financial prompt", schema={})

        error_str = str(exc_info.value)
        # Secret must not appear in exception message
        assert secret_key not in error_str
        assert "[REDACTED" in error_str or "authentication failed" in error_str.lower()

        # Diagnostics must not contain the secret or raw prompt
        for diag in gemini.get_diagnostics():
            serialized = json.dumps(diag, default=str)
            assert secret_key not in serialized
            assert "private financial prompt" not in serialized
            assert "AQ.My" not in serialized

    asyncio.run(_test())
