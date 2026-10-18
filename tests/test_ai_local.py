import asyncio
import json
from datetime import date
import os
import sys

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/api"))

from database.connection import get_db
from routers.ai import router as ai_router
from services.ai.config import OllamaConfig
from services.ai.analyst import AIAnalyst
from services.ai.providers import AIProviderError, OllamaProvider
from services.ai.router import AIRouter
from services.ai.tools import AITools


class FakeResponse:
    status_code = 200
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "qwen2.5:0.5b",
            "response": '{"answer":"No evidence supplied."}',
            "total_duration": 100,
            "load_duration": 10,
            "prompt_eval_count": 4,
            "eval_count": 5,
        }


class FakeAsyncClient:
    def __init__(self, timeout, failures=0):
        self.timeout = timeout
        self.failures = failures

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        if self.failures:
            self.failures -= 1
            raise httpx.ConnectError("connection reset")
        return FakeResponse()


class FakeAnalystProvider:
    def __init__(self, draft):
        self.draft = draft
        self.called = False

    async def generate_structured(self, **kwargs):
        self.called = True
        return self.draft, {"model": "local-test", "eval_count": 8}


def _supported_context():
    return {
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


def test_ollama_config_rejects_remote_endpoints():
    with pytest.raises(ValueError, match="loopback"):
        OllamaConfig(base_url="https://remote.example")


def test_ollama_config_normalizes_localhost_to_ipv4(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    assert OllamaConfig.from_env().base_url == "http://127.0.0.1:11434"


def test_ai_router_uses_configured_models():
    config = OllamaConfig(fast_model="fast-local", primary_model="primary-local", reasoning_model="reason-local")
    router = AIRouter(config)
    assert router.route_task("NEWS_CLASSIFICATION", "LOW") == "fast-local"
    assert router.route_task("DEEP_RESEARCH", "HIGH") == "reason-local"
    assert router.route_task("USER_CHAT", "MEDIUM") == "primary-local"


def test_ollama_structured_response_preserves_usage(monkeypatch):
    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", FakeAsyncClient)
    provider = OllamaProvider(OllamaConfig(retries=0))
    result, metadata = asyncio.run(provider.generate_structured(
        "Return JSON",
        {"type": "object", "properties": {"answer": {"type": "string"}}},
    ))
    assert result == {"answer": "No evidence supplied."}
    assert metadata["model"] == "qwen2.5:0.5b"
    assert metadata["eval_count"] == 5


def test_ollama_retries_transient_connection_failure(monkeypatch):
    clients = []

    def client_factory(timeout):
        client = FakeAsyncClient(timeout, failures=1 if not clients else 0)
        clients.append(client)
        return client

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", client_factory)
    provider = OllamaProvider(OllamaConfig(retries=1))
    result = asyncio.run(provider.generate("Hello"))
    assert result == '{"answer":"No evidence supplied."}'
    assert len(clients) == 2


def test_ollama_model_not_found_is_not_returned_as_answer(monkeypatch):
    class MissingModelResponse(FakeResponse):
        status_code = 404
        text = "model not found"

        def raise_for_status(self):
            request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
            response = httpx.Response(404, request=request, text=self.text)
            raise httpx.HTTPStatusError(self.text, request=request, response=response)

    class MissingModelClient(FakeAsyncClient):
        async def post(self, url, json):
            return MissingModelResponse()

    monkeypatch.setattr("services.ai.providers.httpx.AsyncClient", MissingModelClient)
    provider = OllamaProvider(OllamaConfig(retries=1))
    with pytest.raises(AIProviderError, match="unavailable"):
        asyncio.run(provider.generate("Hello"))


def test_ollama_status_marks_installed_but_unloaded_model_degraded(monkeypatch):
    class SyncResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class SyncClient:
        def __init__(self, timeout, trust_env):
            assert trust_env is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            if url.endswith("/api/version"):
                return SyncResponse({"version": "0.35.0"})
            if url.endswith("/api/tags"):
                return SyncResponse({"models": [{"name": "qwen2.5:0.5b"}]})
            return SyncResponse({"models": []})

    monkeypatch.setattr("services.ai.providers.httpx.Client", SyncClient)
    monkeypatch.setattr("services.ai.providers.subprocess.run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    status = OllamaProvider().status()
    assert status["available"] is True
    assert status["configured_model_installed"] is True
    assert status["configured_model_loaded"] is False
    assert status["status"] == "DEGRADED"


def test_document_retrieval_tool_reports_local_status_without_fabricating_evidence(db_session):
    result = AITools.get_context(
        "UNREGISTERED_AI_FIXTURE",
        date.today(),
        tool_names=["document_retrieval"],
        session=db_session,
    )
    assert result["tools"][0]["name"] == "document_retrieval"
    assert result["tools"][0]["status"] == "INSUFFICIENT_DATA"
    assert result["tools"][0]["data"]["status"] == "INSUFFICIENT_DATA"
    assert result["tools"][0]["data"]["documents"] == []
    assert "embedding_provider" in result["tools"][0]["data"]
    assert "No local document index" in result["tools"][0]["data"]["note"]


def test_analyst_skips_model_when_evidence_is_missing(monkeypatch):
    provider = FakeAnalystProvider({})
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: {
        "symbol": "UNKNOWN", "decision_state": "INSUFFICIENT_DATA", "tools": [], "evidence": [],
    })
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("Why this asset?", session=object(), symbol="UNKNOWN"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert provider.called is False
    assert result["citations"] == []


def test_analyst_does_not_infer_unsupported_horizon(monkeypatch):
    provider = FakeAnalystProvider({})
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _supported_context())
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is the investment horizon?", session=object(), symbol="FPT"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "horizon" in result["uncertainty"][0]
    assert provider.called is False


def test_analyst_returns_only_cited_evidence_and_usage(monkeypatch):
    provider = FakeAnalystProvider({
        "answer": "Canonical filings report EPS of 12.5.",
        "claims": [{"claim_type": "FACT", "text": "EPS is 12.5.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _supported_context())
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is EPS?", session=object(), symbol="FPT"))

    assert result["status"] == "AVAILABLE"
    assert "[Evidence: E001]" in result["answer"]
    assert result["claims"][0]["citation_ids"] == ["E001"]
    assert result["citations"][0]["source"] == "CANONICAL_FINANCIALS"
    assert result["usage"]["eval_count"] == 8


def test_analyst_suppresses_unsupported_numeric_claim(monkeypatch):
    provider = FakeAnalystProvider({
        "answer": "EPS is 99.0.",
        "claims": [{"claim_type": "FACT", "text": "EPS is 99.0.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _supported_context())
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is EPS?", session=object(), symbol="FPT"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "99.0" not in result["answer"]
    assert "numeric claim" in result["uncertainty"][0]


def test_analyst_does_not_use_unrelated_evidence_number(monkeypatch):
    provider = FakeAnalystProvider({
        "answer": "EPS is 99.",
        "claims": [{"claim_type": "FACT", "text": "EPS is 99.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    context = _supported_context()
    context["evidence"].append({
        "claim_type": "MODEL_OUTPUT",
        "responsible_module": "risk",
        "metric": "risk_score",
        "value": 99,
        "source": "RiskEngine",
        "data_origin": "LINEAGED_INGESTION",
        "freshness": "AVAILABLE",
    })
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is EPS?", session=object(), symbol="FPT"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "cited evidence IDs" in result["uncertainty"][0]


def test_analyst_does_not_display_uncited_free_form_model_summary(monkeypatch):
    provider = FakeAnalystProvider({
        "answer": "A made-up investment outlook.",
        "claims": [{"claim_type": "FACT", "text": "EPS is 12.5.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _supported_context())
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is EPS?", session=object(), symbol="FPT"))

    assert result["answer"] == "EPS is 12.5. [Evidence: E001]"
    assert "made-up" not in result["answer"]


def test_analyst_rejects_stale_citation_for_factual_claim(monkeypatch):
    provider = FakeAnalystProvider({
        "answer": "EPS is 12.5.",
        "claims": [{"claim_type": "FACT", "text": "EPS is 12.5.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    context = _supported_context()
    context["evidence"][0]["freshness"] = "STALE"
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    analyst = AIAnalyst(provider=provider)

    result = asyncio.run(analyst.answer_question("What is EPS?", session=object(), symbol="FPT"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "stale" in result["uncertainty"][0]


def test_chat_api_returns_insufficient_data_without_calling_ollama(db_session):
    app = FastAPI()
    app.include_router(ai_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.post("/api/v1/ai/chat", json={
            "question": "Why is this asset notable?",
            "symbol": "UNKNOWN_AI",
            "tool_names": ["asset", "evidence"],
        })
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["model"] is None
    assert body["claims"][0]["claim_type"] == "UNCERTAINTY"


def test_ai_eval_separates_guardrail_verdict_from_runtime_health(db_session):
    from services.ai.evaluation import AIEvaluationFramework

    result = AIEvaluationFramework(session=db_session).run_all()

    assert result["verdict"] == "PASS"
    assert result["runtime"]["status"] in {"HEALTHY", "DEGRADED", "UNAVAILABLE"}
    assert "does not imply" in result["runtime_note"]