"""Unit tests for Multi-Provider AI Gateway failover: Groq -> Gemini -> Local Ollama."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services.ai.config import GatewayConfig
from services.ai.errors import (
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderUnavailableError,
)
from services.ai.gateway import AIGateway
from services.ai.groq_provider import GroqProvider
from services.ai.gemini_provider import GeminiProvider


def test_groq_provider_availability():
    provider_no_key = GroqProvider(api_key="")
    assert not provider_no_key.is_available()

    provider_with_key = GroqProvider(api_key="gsk_12345678901234567890")
    assert provider_with_key.is_available()
    st = provider_with_key.status()
    assert st["provider"] == "groq"
    assert st["available"] is True
    assert st["model"] == "qwen/qwen3.8-27b"


def test_groq_provider_generate_success():
    async def _run():
        provider = GroqProvider(api_key="gsk_test_key_123456789012345")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Phân tích đầu tư thành công."}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await provider.generate("Hãy phân tích VNM")
            assert result == "Phân tích đầu tư thành công."

    asyncio.run(_run())


def test_groq_provider_rate_limit_error():
    async def _run():
        provider = GroqProvider(api_key="gsk_test_key_123456789012345")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit reached"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(AIProviderRateLimitError):
                await provider.generate("Hãy phân tích VNM")

    asyncio.run(_run())


def test_gateway_failover_groq_to_gemini_to_ollama():
    async def _run():
        # Mock providers
        mock_groq = MagicMock(spec=GroqProvider)
        mock_groq.is_available.return_value = True
        mock_groq.generate = AsyncMock(side_effect=AIProviderRateLimitError("Groq 429 Quota Exceeded"))

        mock_gemini = MagicMock(spec=GeminiProvider)
        mock_gemini.is_available.return_value = True
        mock_gemini.generate = AsyncMock(return_value="Gemini response text")

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True}
        mock_ollama.generate = AsyncMock(return_value="Ollama response text")

        config = GatewayConfig(provider_priority=("groq", "gemini", "ollama"))
        gateway = AIGateway(
            config=config,
            groq_provider=mock_groq,
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )

        # Call generate: Groq fails -> Gemini succeeds
        res = await gateway.generate("Phân tích HPG")
        assert res == "Gemini response text"
        assert gateway._last_active_provider == "gemini"

    asyncio.run(_run())


def test_gateway_failover_gemini_to_ollama():
    async def _run():
        mock_groq = MagicMock(spec=GroqProvider)
        mock_groq.is_available.return_value = False  # No key configured yet

        mock_gemini = MagicMock(spec=GeminiProvider)
        mock_gemini.is_available.return_value = True
        mock_gemini.generate = AsyncMock(side_effect=AIProviderRateLimitError("Gemini 429 Quota Exceeded"))

        mock_ollama = MagicMock()
        mock_ollama.status.return_value = {"status": "HEALTHY", "available": True}
        mock_ollama.generate = AsyncMock(return_value="Ollama Qwen 9B response")

        config = GatewayConfig(provider_priority=("groq", "gemini", "ollama"))
        gateway = AIGateway(
            config=config,
            groq_provider=mock_groq,
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )

        res = await gateway.generate("Phân tích FPT")
        assert res == "Ollama Qwen 9B response"
        assert gateway._last_active_provider == "ollama"

    asyncio.run(_run())


def test_gateway_status_reporting():
    mock_groq = MagicMock(spec=GroqProvider)
    mock_groq.is_available.return_value = True
    mock_groq.status.return_value = {"provider": "groq", "available": True, "model": "llama-3.3-70b-versatile"}

    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_gemini.is_available.return_value = True
    mock_gemini.status.return_value = {"provider": "gemini", "available": True, "model": "gemini-1.5-flash"}

    mock_ollama = MagicMock()
    mock_ollama.status.return_value = {"status": "HEALTHY", "available": True, "models": ["qwen3.5:9b-q4_K_M"]}

    config = GatewayConfig(provider_priority=("groq", "gemini", "ollama"))
    gateway = AIGateway(
        config=config,
        groq_provider=mock_groq,
        gemini_provider=mock_gemini,
        ollama_provider=mock_ollama,
    )

    st = gateway.status()
    assert st["active_provider"] == "groq"
    assert st["provider_priority"] == ["groq", "gemini", "ollama"]
    assert st["fallback_enabled"] is True
    assert st["available"] is True
    assert st["status"] == "HEALTHY"
    assert st["configured_models"]["primary"] == "llama-3.3-70b-versatile"
    assert st["groq"]["model"] == "llama-3.3-70b-versatile"
    assert st["gemini"]["model"] == "gemini-1.5-flash"


def test_gateway_status_cloud_groq_active_when_ollama_disabled(monkeypatch):
    monkeypatch.setenv("CLOUD_MODE", "true")
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    mock_groq = MagicMock(spec=GroqProvider)
    mock_groq.is_available.return_value = True
    mock_groq.status.return_value = {
        "provider": "groq",
        "available": True,
        "model": "qwen/qwen3.8-27b",
        "has_api_key": True,
    }
    mock_gemini = MagicMock(spec=GeminiProvider)
    mock_gemini.is_available.return_value = False
    mock_gemini.status.return_value = {
        "provider": "gemini",
        "available": False,
        "model": "gemini-1.5-flash",
        "has_api_key": False,
    }

    gateway = AIGateway(
        config=GatewayConfig(provider_priority=("groq", "gemini", "ollama")),
        groq_provider=mock_groq,
        gemini_provider=mock_gemini,
    )
    st = gateway.status()
    assert st["status"] == "HEALTHY"
    assert st["available"] is True
    assert st["provider"] == "groq"
    assert st["active_provider"] == "groq"
    assert st["configured_models"]["primary"] == "qwen/qwen3.8-27b"
    assert st["reason"] is None


def test_groq_provider_preserves_qwen3_and_remaps_retired_aliases():
    async def _run():
        captured_payloads = []

        async def _fake_post(url, headers=None, json=None, **kwargs):
            captured_payloads.append(json)
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": '{"answer": "ok", "claims": [], "uncertainty": []}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            }
            return resp

        with patch("httpx.AsyncClient.post", side_effect=_fake_post):
            provider = GroqProvider(api_key="unit-test-groq-placeholder", model="qwen/qwen3.8-27b")
            data, _ = await provider.generate_structured(
                prompt="Bằng chứng (JSON): {}",
                schema={"type": "object", "properties": {"answer": {"type": "string"}}},
                model="qwen3.5:9b-q4_K_M",
            )
            assert data["answer"] == "ok"
            assert captured_payloads[0]["model"] == "qwen/qwen3.8-27b"
            assert '"properties"' in captured_payloads[0]["messages"][-1]["content"]

            retired = GroqProvider(api_key="unit-test-groq-placeholder", model="llama-3.3-70b-versatile")
            assert retired.status()["model"] == "qwen/qwen3.8-27b"
            await retired.generate("Phân tích FPT", model="llama-3.3-70b-versatile")
            assert captured_payloads[1]["model"] == "qwen/qwen3.8-27b"

    asyncio.run(_run())


def test_gemini_provider_remaps_retired_aliases_and_includes_schema():
    async def _run():
        captured_calls = []

        async def _fake_post(url, json=None, **kwargs):
            captured_calls.append((url, json))
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": '{"answer": "ok", "claims": [], "uncertainty": []}'}]}}],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 9, "totalTokenCount": 21},
            }
            return resp

        with patch("httpx.AsyncClient.post", side_effect=_fake_post):
            provider = GeminiProvider(api_key="unit-test-gemini-placeholder", model="gemini-1.5-flash")
            assert provider.status()["model"] == "gemini-flash-lite-latest"

            data, meta = await provider.generate_structured(
                prompt="Bằng chứng (JSON): {}",
                schema={"type": "object", "properties": {"text": {"type": "string"}}},
                model="gemini-2.0-flash",
            )
            assert data["answer"] == "ok"
            assert meta["model"] == "gemini-flash-lite-latest"
            url, payload = captured_calls[0]
            assert "/models/gemini-flash-lite-latest:generateContent" in url
            assert payload["generationConfig"]["responseMimeType"] == "application/json"
            assert '"properties"' in payload["contents"][0]["parts"][0]["text"]

    asyncio.run(_run())


def test_groq_six_key_ring_rotation_on_rate_limit_and_12s_timeout(monkeypatch):
    import httpx
    from services.ai.config import load_groq_api_keys

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEYS", "unit_dummy_groq_alpha_key_001,unit_dummy_groq_alpha_key_002")
    monkeypatch.setenv("GROQ_API_KEY_1", "unit_dummy_groq_alpha_key_001")  # duplicate of CSV entry
    monkeypatch.setenv("GROQ_API_KEY_3", "unit_dummy_groq_alpha_key_003")
    monkeypatch.setenv("GROQ_API_KEY_4", "unit_dummy_groq_alpha_key_004")
    monkeypatch.setenv("GROQ_API_KEY_5", "unit_dummy_groq_alpha_key_005")
    monkeypatch.setenv("GROQ_API_KEY_6", "unit_dummy_groq_alpha_key_006")

    keys = load_groq_api_keys()
    assert len(keys) == 6
    cfg = GatewayConfig.from_env()
    assert cfg.provider_priority[0] == "groq"

    async def _run():
        called_headers: list[str] = []

        async def _fake_post(url, headers=None, json=None, **kwargs):
            auth = (headers or {}).get("Authorization", "")
            called_headers.append(auth)
            attempt = len(called_headers)
            if attempt in (1, 2):
                resp = MagicMock()
                resp.status_code = 429
                resp.text = "Too Many Requests"
                return resp
            if attempt in (3, 4, 5):
                raise httpx.ReadTimeout("Simulated >12s Groq stall")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": "<think>internal step</think>Key slot 6 ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
            }
            return resp

        with patch("httpx.AsyncClient.post", side_effect=_fake_post):
            provider = GroqProvider()
            assert provider.timeout_seconds == 12.0
            assert provider.status()["key_count"] == 6
            out = await provider.generate("Phân tích FPT")
            assert out == "Key slot 6 ok"
            assert len(called_headers) == 6
            assert len(set(called_headers)) == 6

    asyncio.run(_run())

