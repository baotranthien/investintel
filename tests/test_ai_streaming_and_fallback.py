"""
Unit and integration tests for AI Analyst Streaming (SSE) and Smart Fallback (Task 1).
Verifies:
1. answer_question_stream yields status events (fetching_data, llm_reasoning, validating, result, [DONE]).
2. Smart Fallback produces status='PARTIAL_DATA_ONLY' with structured_data_summary and metadata_flags
   when 0 substantive claims survive validation but verifiable data exists in DB.
3. Structured summary contains Python-computed metrics (net_profit_margin_pct, comparisons).
4. FastAPI /api/v1/ai/chat/stream returns text/event-stream content.
"""
import asyncio
from datetime import date
import json
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.ai.analyst import AIAnalyst
from services.ai.schemas import AIAnswerDraft, AIClaim, AICitation
from services.ai.tools import AITools


class MockDraftProvider:
    def __init__(self, draft: dict, delay: float = 0.0):
        self.draft = draft
        self.delay = delay
        self.called = False

    async def generate_structured(self, prompt, **kwargs):
        self.called = True
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return self.draft, {"model": "mock-qwen", "eval_count": 25}


def _sample_context(symbol="VCB"):
    return {
        "symbol": symbol,
        "symbols": [symbol],
        "as_of_date": "2026-10-19",
        "decision_state": "AVAILABLE",
        "tools": [
            {"name": "fundamentals", "status": "AVAILABLE", "data": {}},
            {"name": "valuation", "status": "AVAILABLE", "data": {}},
        ],
        "evidence": [
            {
                "claim_type": "FACT",
                "responsible_module": "valuation",
                "symbol": symbol,
                "metric": "pe",
                "value": 11.28,
                "unit": "multiple",
                "source": "LOTUSMARKET+VNDIRECT+VIETCAP",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
                "observation_date": "2026-10-19",
                "is_estimate": True,
            },
            {
                "claim_type": "FACT",
                "responsible_module": "valuation",
                "symbol": symbol,
                "metric": "pb",
                "value": 1.89,
                "unit": "multiple",
                "source": "LOTUSMARKET+VNDIRECT+VIETCAP",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
                "observation_date": "2026-10-19",
                "is_estimate": False,
            },
            {
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "symbol": symbol,
                "metric": "revenue",
                "value": 84873.0,
                "unit": "BILLION_VND",
                "source": "VIETCAP_IQ",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
                "observation_date": "2026-06-30",
                "is_estimate": False,
            },
            {
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "symbol": symbol,
                "metric": "net_income",
                "value": 41671.0,
                "unit": "BILLION_VND",
                "source": "VIETCAP_IQ",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
                "observation_date": "2026-06-30",
                "is_estimate": False,
            },
        ],
    }


def test_streaming_event_sequence(monkeypatch):
    """Verify that answer_question_stream emits the complete sequence of SSE events."""
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _sample_context("VCB"))

    valid_draft = {
        "answer": "VCB có P/E ổn định 11.28x [Evidence: E001].",
        "claims": [
            {
                "claim_type": "FACT",
                "text": "VCB ghi nhận tỷ số P/E đạt 11.28x.",
                "citation_ids": ["E001"],
            }
        ],
        "uncertainty": [],
    }
    mock_provider = MockDraftProvider(valid_draft)
    analyst = AIAnalyst(provider=mock_provider)

    async def _run():
        events = []
        async for sse_chunk in analyst.answer_question_stream(
            "Định giá cổ phiếu VCB",
            session=object(),
            symbol="VCB",
            as_of=date(2026, 10, 19),
        ):
            events.append(sse_chunk)
        return events

    events = asyncio.run(_run())

    # Must contain fetching_data, llm_reasoning, validating, result, [DONE]
    text_stream = "".join(events)
    assert "fetching_data" in text_stream
    assert "llm_reasoning" in text_stream
    assert "validating" in text_stream
    assert "result" in text_stream
    assert "[DONE]" in text_stream

    # Parse the result event
    result_event = next(e for e in events if '"type": "result"' in e)
    parsed = json.loads(result_event.replace("data: ", "").strip())
    assert parsed["type"] == "result"
    assert parsed["data"]["symbol"] == "VCB"
    assert parsed["data"]["status"] == "AVAILABLE"
    assert parsed["data"]["structured_data_summary"] is not None
    assert parsed["data"]["metadata_flags"] is not None
    assert parsed["data"]["metadata_flags"]["eps_is_estimate"] is True


def test_smart_fallback_when_llm_hallucinates(monkeypatch):
    """
    When LLM returns claims with ungrounded numbers or invalid citations,
    deterministic validation filters them out.
    System must fall back to PARTIAL_DATA_ONLY instead of failing with refusal.
    """
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: _sample_context("VCB"))

    hallucinated_draft = {
        "answer": "VCB có doanh thu 999,999 tỷ và lợi nhuận 888,888 tỷ [Evidence: E001].",
        "claims": [
            {
                "claim_type": "FACT",
                "text": "VCB có doanh thu đạt 999999 tỷ VND.",
                "citation_ids": ["E001"],
            }
        ],
        "uncertainty": [],
    }
    mock_provider = MockDraftProvider(hallucinated_draft)
    analyst = AIAnalyst(provider=mock_provider)

    res = asyncio.run(analyst.answer_question(
        "Định giá cổ phiếu VCB",
        session=object(),
        symbol="VCB",
        as_of=date(2026, 10, 19),
    ))

    # Must be PARTIAL_DATA_ONLY
    assert res["status"] == "PARTIAL_DATA_ONLY"
    assert "structured_data_summary" in res and res["structured_data_summary"] is not None
    assert "metadata_flags" in res and res["metadata_flags"] is not None
    assert res["metadata_flags"]["data_origin"] == "CANONICAL_DATABASE"
    assert res["metadata_flags"]["eps_is_estimate"] is True

    # Must include fallback factual claims
    assert len(res["claims"]) > 0
    fact_claims = [c for c in res["claims"] if c["claim_type"] == "FACT"]
    assert len(fact_claims) > 0

    # Summary table must have VCB metrics and Python-computed indicators
    symbols = res["structured_data_summary"]["symbols"]
    assert "VCB" in symbols
    vcb_calc = symbols["VCB"]["calculated_indicators"]
    # 41671 / 84873 * 100 = 49.1%
    assert vcb_calc.get("net_profit_margin_pct") == 49.1


def test_fastapi_chat_stream_endpoint():
    """Verify HTTP POST /api/v1/ai/chat/stream responds with text/event-stream."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/chat/stream",
        json={"question": "Chào bạn, bot có thể làm gì?", "tool_names": ["asset"]},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    content = response.text
    assert "fetching_data" in content
    assert '"type": "result"' in content
    assert "[DONE]" in content
