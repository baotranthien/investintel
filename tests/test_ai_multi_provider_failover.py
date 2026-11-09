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
    assert st["groq"]["model"] == "llama-3.3-70b-versatile"
    assert st["gemini"]["model"] == "gemini-1.5-flash"
