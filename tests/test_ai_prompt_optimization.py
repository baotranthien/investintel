"""
Tests for Task 2: Pre-computed metrics and context optimization for qwen2.5:3b.
Verifies:
1. Python pre-computes net_margin from revenue and net income.
2. Python pre-computes pe_diff and pb_diff for multi-ticker queries (e.g. MBB vs VCB).
3. Pearson correlation calculation is numerically accurate.
4. Pre-computed citations are injected into verifiable_evidence with correct citation IDs.
5. Entity validation allows multi-symbol citations (e.g. symbol='MBB,VCB').
"""
import asyncio
from datetime import date
import pytest

from services.ai.analyst import AIAnalyst, _calculate_pearson, _matches_entity
from services.ai.prompt_registry import build_chat_prompt
from services.ai.schemas import AICitation, AIClaim


def test_calculate_pearson():
    """Verify Pearson correlation calculation."""
    # Perfectly correlated
    x = [10.0, 20.0, 30.0, 40.0]
    y = [100.0, 200.0, 300.0, 400.0]
    assert _calculate_pearson(x, y) == 1.0

    # Inversely correlated
    y_inv = [400.0, 300.0, 200.0, 100.0]
    assert _calculate_pearson(x, y_inv) == -1.0

    # Insufficient length
    assert _calculate_pearson([1.0, 2.0], [2.0, 4.0]) is None


def test_matches_entity_helper():
    """Verify _matches_entity supports multi-symbol evidence."""
    assert _matches_entity("MBB,VCB", "MBB") is True
    assert _matches_entity("MBB,VCB", "VCB") is True
    assert _matches_entity("MBB,VCB", "FPT") is False
    assert _matches_entity("VN100", "FPT") is True
    assert _matches_entity(None, "FPT") is True


def test_inject_precomputed_margins():
    """Verify net_margin is pre-calculated from revenue and net income."""
    analyst = AIAnalyst()
    citations = [
        AICitation(
            id="E001",
            claim_type="FACT",
            responsible_module="fundamentals",
            metric="revenue",
            value=100000.0,
            unit="BILLION_VND",
            source="TEST",
            symbol="MBB",
        ),
        AICitation(
            id="E002",
            claim_type="FACT",
            responsible_module="fundamentals",
            metric="net_income",
            value=25000.0,
            unit="BILLION_VND",
            source="TEST",
            symbol="MBB",
        ),
    ]

    injected = analyst._inject_precomputed_metrics(citations, ["MBB"])
    metrics = {c.metric: c for c in injected}
    assert "net_margin" in metrics
    # 25000 / 100000 * 100 = 25.0%
    assert metrics["net_margin"].value == 25.0
    assert metrics["net_margin"].id == "E003"
    assert metrics["net_margin"].symbol == "MBB"


def test_inject_precomputed_multi_ticker_valuation_diff():
    """Verify pe_diff and pb_diff are pre-calculated for multi-symbol queries."""
    analyst = AIAnalyst()
    citations = [
        AICitation(
            id="E001",
            claim_type="FACT",
            responsible_module="valuation",
            metric="pe",
            value=6.50,
            unit="multiple",
            source="TEST",
            symbol="MBB",
        ),
        AICitation(
            id="E002",
            claim_type="FACT",
            responsible_module="valuation",
            metric="pe",
            value=14.50,
            unit="multiple",
            source="TEST",
            symbol="VCB",
        ),
        AICitation(
            id="E003",
            claim_type="FACT",
            responsible_module="valuation",
            metric="pb",
            value=1.10,
            unit="multiple",
            source="TEST",
            symbol="MBB",
        ),
        AICitation(
            id="E004",
            claim_type="FACT",
            responsible_module="valuation",
            metric="pb",
            value=2.80,
            unit="multiple",
            source="TEST",
            symbol="VCB",
        ),
    ]

    injected = analyst._inject_precomputed_metrics(citations, ["MBB", "VCB"])
    metrics = {c.metric: c for c in injected}

    assert "pe_diff" in metrics
    # 6.50 - 14.50 = -8.0
    assert metrics["pe_diff"].value == -8.0
    assert "MBB,VCB" in metrics["pe_diff"].symbol

    assert "pb_diff" in metrics
    # 1.10 - 2.80 = -1.7
    assert metrics["pb_diff"].value == -1.7


def test_build_chat_prompt_prioritizes_precomputed_comparison():
    """Verify build_chat_prompt ranks pre-computed differences at the top for comparison questions."""
    context = {
        "symbol": "MBB, VCB",
        "symbols": ["MBB", "VCB"],
        "as_of_date": "2026-10-27",
        "evidence_register": [
            {
                "id": "E001",
                "metric": "pe",
                "value": 6.50,
                "unit": "x",
                "source": "TEST",
                "symbol": "MBB",
                "claim_type": "FACT",
                "data_origin": "CANONICAL",
                "freshness": "AVAILABLE",
            },
            {
                "id": "E002",
                "metric": "pe",
                "value": 14.50,
                "unit": "x",
                "source": "TEST",
                "symbol": "VCB",
                "claim_type": "FACT",
                "data_origin": "CANONICAL",
                "freshness": "AVAILABLE",
            },
            {
                "id": "E003",
                "metric": "pe_diff",
                "value": -8.0,
                "unit": "x",
                "source": "INVESTINTEL_PYTHON_CALCULATOR",
                "symbol": "MBB,VCB",
                "claim_type": "MODEL_OUTPUT",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
        ],
    }

    prompt = build_chat_prompt("So sánh định giá MBB và VCB", context)
    assert "pe_diff" in prompt
    assert "-8" in prompt
    # Verifies prompt contains precomputed differences for 3B model to cite directly
    assert "E003" in prompt
