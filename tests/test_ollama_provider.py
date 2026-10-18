"""Deterministic test suite for Local Ollama Provider and AIGateway.

Covers:
1. Ollama configuration and environment variable parsing.
2. OllamaProvider status detection (HEALTHY, DEGRADED, MODEL_NOT_FOUND, UNAVAILABLE).
3. OllamaProvider generate and generate_structured (success, retries, 404 missing model, timeouts).
4. AIGateway cloud environment isolation (LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD).
5. Real local inference execution against verified installed model.
"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.ai.config import GatewayConfig, OllamaConfig
from services.ai.errors import (
    AIProviderError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from services.ai.gateway import AIGateway
from services.ai.providers import OllamaProvider


# ---------------------------------------------------------------------------
# 1. Ollama Configuration Tests
# ---------------------------------------------------------------------------


def test_ollama_config_defaults():
    config = OllamaConfig()
    assert config.base_url == "http://127.0.0.1:11434"
    assert config.primary_model == "qwen2.5:0.5b"
    assert config.timeout_seconds == 75.0
    assert config.retries == 1


def test_ollama_config_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model:latest")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("OLLAMA_RETRIES", "2")

    cfg = OllamaConfig.from_env()
    assert cfg.base_url == "http://127.0.0.1:11434"
    assert cfg.primary_model == "custom-model:latest"
    assert cfg.timeout_seconds == 45.0
    assert cfg.retries == 2


def test_ollama_config_blocks_external_url():
    with pytest.raises(ValueError, match="loopback"):
        OllamaConfig(base_url="https://external-service.ai:11434")


# ---------------------------------------------------------------------------
# 2. Ollama Provider Status Detection
# ---------------------------------------------------------------------------


class MockSyncResponse:
    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://127.0.0.1:11434")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("Error", request=request, response=response)

    def json(self):
        return self._data


def test_ollama_status_unavailable_when_server_down(monkeypatch):
    class FailingSyncClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr("services.ai.providers.httpx.Client", FailingSyncClient)
    provider = OllamaProvider()
    st = provider.status()
    assert st["status"] == "UNAVAILABLE"
    assert st["available"] is False
    assert "not responding" in st["reason"]


def test_ollama_status_model_not_found(monkeypatch):
    class TagsWithoutConfiguredModelClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            if url.endswith("/api/version"):
                return MockSyncResponse({"version": "0.3.14"})
            if url.endswith("/api/tags"):
                return MockSyncResponse({"models": [{"name": "llama3:latest"}]})
            return MockSyncResponse({"models": []})

    monkeypatch.setattr("services.ai.providers.httpx.Client", TagsWithoutConfiguredModelClient)
    monkeypatch.setattr("services.ai.providers.subprocess.run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))

    provider = OllamaProvider(OllamaConfig(primary_model="qwen2.5:0.5b"))
    st = provider.status()
    assert st["status"] == "MODEL_NOT_FOUND"
    assert st["available"] is False
    assert st["configured_model_installed"] is False
    assert "not installed" in st["reason"]


def test_ollama_status_healthy_when_loaded(monkeypatch):
    class FullyLoadedClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            if url.endswith("/api/version"):
                return MockSyncResponse({"version": "0.3.14"})
            if url.endswith("/api/tags"):
                return MockSyncResponse({"models": [{"name": "qwen2.5:0.5b"}]})
            if url.endswith("/api/ps"):
                return MockSyncResponse({"models": [{"name": "qwen2.5:0.5b"}]})
            return MockSyncResponse({})

    monkeypatch.setattr("services.ai.providers.httpx.Client", FullyLoadedClient)
    monkeypatch.setattr("services.ai.providers.subprocess.run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))

    provider = OllamaProvider(OllamaConfig(primary_model="qwen2.5:0.5b"))
    st = provider.status()
    assert st["status"] == "HEALTHY"
    assert st["available"] is True
    assert st["configured_model_installed"] is True
    assert st["configured_model_loaded"] is True


# ---------------------------------------------------------------------------
# 3. Ollama Provider Generate & Generate Structured Tests
# ---------------------------------------------------------------------------


class FakeAsyncOllamaResponse:
    def __init__(self, status_code: int = 200, response_text: str = "Test response"):
        self.status_code = status_code
        self._text = response_text

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
            response = httpx.Response(self.status_code, request=request, text=self._text)
            raise httpx.HTTPStatusError("HTTP Error", request=request, response=response)

    def json(self):
        return {
            "model": "qwen2.5:0.5b",
            "response": self._text,
            "total_duration": 1200000,
            "prompt_eval_count": 10,
            "eval_count": 25,
        }


def test_ollama_generate_success(monkeypatch):
    class AsyncGenerateClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            return FakeAsyncOllamaResponse(200, "VNDirect valuation is positive.")

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", AsyncGenerateClient)
    provider = OllamaProvider(OllamaConfig(retries=0))
    result = asyncio.run(provider.generate("Analyze VND"))
    assert result == "VNDirect valuation is positive."


def test_ollama_generate_timeout_error(monkeypatch):
    class AsyncTimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            raise httpx.TimeoutException("Read timed out")

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", AsyncTimeoutClient)
    provider = OllamaProvider(OllamaConfig(retries=0))
    with pytest.raises(AIProviderTimeoutError, match="timed out"):
        asyncio.run(provider.generate("Analyze VND"))


def test_ollama_generate_missing_model_404(monkeypatch):
    class Async404Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            return FakeAsyncOllamaResponse(404, "model 'nonexistent' not found")

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", Async404Client)
    provider = OllamaProvider(OllamaConfig(retries=0))
    with pytest.raises(AIProviderError, match="unavailable"):
        asyncio.run(provider.generate("Analyze VND"))


def test_ollama_generate_structured_success(monkeypatch):
    json_payload = '{"recommendation": "BUY", "target_price": 120000}'

    class AsyncStructuredClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json):
            assert "format" in json
            return FakeAsyncOllamaResponse(200, json_payload)

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", AsyncStructuredClient)
    provider = OllamaProvider(OllamaConfig(retries=0))
    data, meta = asyncio.run(
        provider.generate_structured(
            "Analyze FPT",
            schema={"type": "object", "properties": {"recommendation": {"type": "string"}}},
        )
    )
    assert data["recommendation"] == "BUY"
    assert data["target_price"] == 120000
    assert meta["model"] == "qwen2.5:0.5b"


# ---------------------------------------------------------------------------
# 4. AIGateway Cloud Isolation Tests
# ---------------------------------------------------------------------------


def test_gateway_cloud_isolation_status():
    gateway = AIGateway()
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "OLLAMA_ENABLED": "false"}):
        st = gateway.status()
        assert st["status"] == "LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD"
        assert st["available"] is False
        assert st["provider"] == "ollama"
        assert "not accessible from the cloud environment" in st["reason"]


def test_gateway_cloud_isolation_generate_raises():
    gateway = AIGateway()
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "OLLAMA_ENABLED": "false"}):
        with pytest.raises(AIProviderUnavailableError, match="LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD"):
            asyncio.run(gateway.generate("Test prompt"))


def test_gateway_cloud_isolation_structured_raises():
    gateway = AIGateway()
    with patch.dict(os.environ, {"CLOUD_MODE": "true", "OLLAMA_ENABLED": "false"}):
        with pytest.raises(AIProviderUnavailableError, match="LOCAL_MODEL_NOT_AVAILABLE_IN_CLOUD"):
            asyncio.run(gateway.generate_structured("Test prompt", schema={}))


def test_gateway_rejects_non_ollama_provider():
    gateway = AIGateway()
    with pytest.raises(ValueError, match="Only local Ollama is supported"):
        gateway.get_provider("gemini")

    with pytest.raises(ValueError, match="Only local Ollama is supported"):
        gateway.get_provider("openai")


# ---------------------------------------------------------------------------
# 5. Live Local Inference Test (against real running Ollama daemon)
# ---------------------------------------------------------------------------


def test_live_local_ollama_inference():
    """Verifies actual local inference using the running Ollama server and installed qwen2.5:0.5b."""
    # Check if Ollama server is running locally
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code != 200:
                pytest.skip("Local Ollama daemon not reachable")
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            if not any("qwen2.5:0.5b" in m for m in models):
                pytest.skip("qwen2.5:0.5b not installed in local Ollama")
    except Exception:
        pytest.skip("Local Ollama daemon not running on port 11434")

    # Perform real inference
    provider = OllamaProvider(OllamaConfig(primary_model="qwen2.5:0.5b", timeout_seconds=15.0))
    st = provider.status()
    assert st["status"] in ("HEALTHY", "DEGRADED")
    assert st["available"] is True

    result = asyncio.run(provider.generate("Tra loi ngan gon trong 1 cau: Co phieu FPT la gi?"))
    assert isinstance(result, str)
    assert len(result.strip()) > 0
