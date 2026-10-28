"""
Targeted regression tests for AI Analyst repairs (Priorities 1 - 5).
Ensures deterministic enforcement of:
- Multi-ticker extraction and acronym disambiguation (Q03, Q09, Q12, Q13, Q14, Q15, Q17, Q20)
- Metric-aware and entity-aware validation (Q01, Q06, Q07, Q08, Q10, Q12, Q13)
- Preservation of supported answers and uncertainty sanitization (Q02, Q17)
- Preservation of EPS estimate metadata through prompt construction (Q16)
- General portfolio routing and historical replay disclosure (Q18, Q19)
"""
import asyncio
from datetime import date

import pytest

from services.universe.registry import UniverseRegistry
from services.ai.analyst import AIAnalyst
from services.ai.prompt_registry import build_chat_prompt
from services.ai.tools import AITools


class FakeAnalystProvider:
    def __init__(self, draft):
        self.draft = draft
        self.called = False
        self.last_prompt = None

    async def generate_structured(self, prompt, **kwargs):
        self.called = True
        self.last_prompt = prompt
        return self.draft, {"model": "local-test", "eval_count": 10}


# ==============================================================================
# Priority 1: Ticker Extraction, Acronyms, Multi-ticker
# ==============================================================================

def test_q20_unknown_ticker_zzztest_not_hijacked_by_eps():
    """Q20: ZZZTEST is identified as unknown ticker, not hijacked by acronym 'EPS'."""
    q = "Đánh giá cổ phiếu mã ZZZTEST: EPS, P/E và P/B hiện tại là bao nhiêu?"
    extracted = UniverseRegistry.extract_all_symbols_from_text(q)
    assert extracted == ["ZZZTEST"]
    assert UniverseRegistry.extract_symbol_from_text(q) == "ZZZTEST"

    # Verify acronyms are excluded
    assert UniverseRegistry.extract_symbol_from_text("Chỉ số EPS của công ty là bao nhiêu?") is None
    assert UniverseRegistry.extract_symbol_from_text("Tỷ số P/E và P/B là bao nhiêu?") is None
    assert UniverseRegistry.extract_symbol_from_text("Biên EBITDA và ROE năm nay") is None
    assert UniverseRegistry.extract_symbol_from_text("Định giá theo phương pháp DCF và so sánh EV/EBITDA") is None


def test_multi_ticker_extraction_all_target_cases():
    """Verify multi-ticker recognition for Q03, Q09, Q12, Q13, Q14, Q15, Q17."""
    assert UniverseRegistry.extract_all_symbols_from_text("So sánh MBB và VCB về tăng trưởng") == ["MBB", "VCB"]
    assert UniverseRegistry.extract_all_symbols_from_text("So sánh GAS và POW về mô hình kinh doanh") == ["GAS", "POW"]
    assert UniverseRegistry.extract_all_symbols_from_text("So sánh SSI và VIX về lợi nhuận") == ["SSI", "VIX"]
    assert UniverseRegistry.extract_all_symbols_from_text("So sánh REE và PC1 về các mảng kinh doanh") == ["REE", "PC1"]
    assert UniverseRegistry.extract_all_symbols_from_text("So sánh FPT và CMG về tăng trưởng") == ["FPT", "CMG"]
    assert UniverseRegistry.extract_all_symbols_from_text("VCB, HPG và FPT: định giá thế nào?") == ["VCB", "HPG", "FPT"]
    assert UniverseRegistry.extract_all_symbols_from_text("Kiểm tra dữ liệu hiện có của VIX, DSE và HPG") == ["VIX", "DSE", "HPG"]


# ==============================================================================
# Priority 2: Metric-Aware & Entity-Aware Validation
# ==============================================================================

def test_q06_vhm_gross_margin_cannot_substantiate_revenue_change(monkeypatch):
    """Q06: Gross margin evidence cannot be used as revenue-growth or revenue-decline evidence."""
    context = {
        "symbol": "VHM",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {}}],
        "evidence": [{
            "claim_type": "FACT",
            "responsible_module": "fundamentals",
            "symbol": "VHM",
            "metric": "gross_margin",
            "value": 44.16,
            "unit": "%",
            "source": "CANONICAL_FINANCIALS",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
        }],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "Doanh thu VHM giảm 44.16%.",
        "claims": [{
            "claim_type": "FACT",
            "text": "Doanh thu VHM giảm 44.16% so với năm trước.",
            "citation_ids": ["E001"],
        }],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("Phân tích doanh thu VHM?", session=object(), symbol="VHM"))

    # The invalid claim must be suppressed
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "Margin evidence cannot be presented as revenue growth" in result["uncertainty"][0]


def test_q07_vic_pe_cannot_be_described_as_profit(monkeypatch):
    """Q07: P/E valuation multiple cannot be described as profit or net income."""
    context = {
        "symbol": "VIC",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "valuation", "status": "AVAILABLE", "data": {}}],
        "evidence": [{
            "claim_type": "MODEL_OUTPUT",
            "responsible_module": "valuation",
            "symbol": "VIC",
            "metric": "pe",
            "value": 85.74,
            "unit": "multiple",
            "source": "LOTUSMARKET",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
        }],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "Lợi nhuận hợp nhất của VIC là 85.74 tỷ.",
        "claims": [{
            "claim_type": "FACT",
            "text": "Lợi nhuận hợp nhất của VIC đạt 85.74.",
            "citation_ids": ["E001"],
        }],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("Lợi nhuận VIC bao nhiêu?", session=object(), symbol="VIC"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "Valuation multiple evidence cannot be presented as profit" in result["uncertainty"][0]


def test_q10_plx_company_revenue_cannot_cite_as_oil_price(monkeypatch):
    """Q10: Company revenue growth cannot substantiate oil price movement."""
    context = {
        "symbol": "PLX",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {}}],
        "evidence": [{
            "claim_type": "FACT",
            "responsible_module": "fundamentals",
            "symbol": "PLX",
            "metric": "revenue_yoy",
            "value": 40.92,
            "unit": "%",
            "source": "CANONICAL_FINANCIALS",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
        }],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "Giá dầu tăng 40.92%.",
        "claims": [{
            "claim_type": "FACT",
            "text": "Giá dầu trong năm qua tăng 40.92% so với cùng kỳ.",
            "citation_ids": ["E001"],
        }],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("Giá dầu ảnh hưởng PLX thế nào?", session=object(), symbol="PLX"))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "cannot substantiate commodity price changes" in result["uncertainty"][0]


def test_q12_q13_entity_consistency_prevents_cross_stock_attribution(monkeypatch):
    """Q12/Q13: Citations for Stock A cannot support claims about Stock B."""
    context = {
        "symbol": "REE, PC1",
        "symbols": ["REE", "PC1"],
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "valuation", "status": "AVAILABLE", "data": {}}],
        "evidence": [
            {
                "claim_type": "MODEL_OUTPUT",
                "responsible_module": "valuation",
                "symbol": "REE",
                "metric": "pe",
                "value": 10.84,
                "unit": "multiple",
                "source": "LOTUSMARKET",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
            {
                "claim_type": "MODEL_OUTPUT",
                "responsible_module": "valuation",
                "symbol": "PC1",
                "metric": "pe",
                "value": 18.50,
                "unit": "multiple",
                "source": "LOTUSMARKET",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
        ],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "P/E của PC1 là 10.84.",
        "claims": [{
            "claim_type": "FACT",
            # Mismatch: asserting PC1 using REE's citation E001
            "text": "P/E của PC1 là 10.84 lần.",
            "citation_ids": ["E001"],
        }],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("So sánh REE và PC1", session=object()))

    assert result["status"] == "INSUFFICIENT_DATA"
    assert "Claim for PC1 cannot be supported solely by citations from REE" in result["uncertainty"][0]


# ==============================================================================
# Priority 3: Preserving Grounded Facts & Sanitizing Uncertainty
# ==============================================================================

def test_q01_q08_contradictory_uncertainty_is_filtered(monkeypatch):
    """Q01/Q08: If a metric is provided with evidence, contradictory uncertainty is stripped."""
    context = {
        "symbol": "FPT",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "valuation", "status": "AVAILABLE", "data": {}}],
        "evidence": [
            {
                "claim_type": "MODEL_OUTPUT",
                "responsible_module": "valuation",
                "symbol": "FPT",
                "metric": "pe",
                "value": 10.56,
                "unit": "multiple",
                "source": "LOTUSMARKET",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
            {
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "symbol": "FPT",
                "metric": "gross_margin",
                "value": 34.65,
                "unit": "%",
                "source": "CANONICAL_FINANCIALS",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
        ],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "P/E của FPT là 10.56. Biên lợi nhuận gộp là 34.65%.",
        "claims": [
            {"claim_type": "FACT", "text": "P/E của FPT là 10.56.", "citation_ids": ["E001"]},
            {"claim_type": "FACT", "text": "Biên lợi nhuận gộp của FPT là 34.65%.", "citation_ids": ["E002"]},
        ],
        "uncertainty": [
            "Mức định giá P/E chưa được cung cấp trong dữ liệu hiện có.",
            "Công ty chưa cung cấp thông tin về biên lợi nhuận (gross margin).",
            "Dòng tiền tự do chưa được tính toán.",
        ],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("Định giá FPT", session=object(), symbol="FPT"))

    assert result["status"] == "AVAILABLE"
    # Contradictions are filtered out
    assert not any("p/e" in u.lower() for u in result["uncertainty"])
    assert not any("biên lợi nhuận" in u.lower() for u in result["uncertainty"])
    # Legitimate missing indicator survives
    assert any("Dòng tiền tự do" in u for u in result["uncertainty"])


def test_q02_vcb_facts_survive_when_uncertainty_has_ungrounded_numbers(monkeypatch):
    """Q02: Grounded banking metrics survive even if LLM wrote ungrounded year in uncertainty."""
    context = {
        "symbol": "VCB",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {}}],
        "evidence": [
            {
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "symbol": "VCB",
                "metric": "roe",
                "value": 21.5,
                "unit": "%",
                "source": "CANONICAL_FINANCIALS",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
        ],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "ROE của VCB là 21.5%.",
        "claims": [{"claim_type": "FACT", "text": "ROE của VCB là 21.5%.", "citation_ids": ["E001"]}],
        # Contains ungrounded year 2024 (which previously caused entire answer discard)
        "uncertainty": ["Chưa có số liệu tăng trưởng tín dụng năm 2024."],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("Phân tích VCB", session=object(), symbol="VCB"))

    # The answer survives and is returned as PARTIAL/AVAILABLE without generic discard!
    assert result["status"] in ("AVAILABLE", "PARTIAL")
    assert "21.5" in result["answer"]
    assert len(result["claims"]) >= 1


def test_q14_q15_missing_stock_in_comparison_is_explicitly_disclosed(monkeypatch):
    """Q14/Q15: Multi-ticker comparison with one missing stock renders valid stock facts and discloses missing stock."""
    context = {
        "symbol": "FPT, CMG",
        "symbols": ["FPT", "CMG"],
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {}}],
        "evidence": [
            {
                "claim_type": "FACT",
                "responsible_module": "fundamentals",
                "symbol": "FPT",
                "metric": "revenue_yoy",
                "value": 20.6,
                "unit": "%",
                "source": "CANONICAL_FINANCIALS",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
            },
        ],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "FPT có tăng trưởng doanh thu 20.6%.",
        "claims": [{"claim_type": "FACT", "text": "FPT có tăng trưởng doanh thu 20.6%.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question("So sánh FPT và CMG", session=object()))

    assert result["status"] == "PARTIAL"
    assert "FPT" in result["answer"]
    # CMG missing notice is automatically appended
    missing_notice = [c for c in result["claims"] if "CMG" in c["text"] and c["claim_type"] == "UNCERTAINTY"]
    assert len(missing_notice) == 1
    assert "chưa có sẵn hoặc chưa đủ điều kiện kiểm chứng" in missing_notice[0]["text"]


# ==============================================================================
# Priority 4: EPS Denominator & Estimate Note in Prompt Construction
# ==============================================================================

def test_q16_vix_eps_estimate_and_denominator_note_preserved_in_prompt():
    """Q16: Denominator note and estimate status survive in verifiable_evidence passed to LLM."""
    context = {
        "symbol": "VIX",
        "as_of_date": "2026-10-27",
        "evidence_register": [
            {
                "id": "E038",
                "claim_type": "MODEL_OUTPUT",
                "responsible_module": "valuation",
                "symbol": "VIX",
                "metric": "pe",
                "value": 19.2,
                "unit": "multiple",
                "source": "LOTUSMARKET",
                "data_origin": "LINEAGED_INGESTION",
                "freshness": "AVAILABLE",
                "is_estimate": True,
                "diagnostic_reason": "EPS_DENOMINATOR_ESTIMATE_PERIOD_END_SHARES",
                "note": "Mathematically calculated from canonical adjusted close (12500.0 VND) / EPS TTM (651.0 VND). Post-corporate-action share basis. (Denominator uses period-end shares fallback; multiple is an estimate.)",
            }
        ],
    }
    prompt = build_chat_prompt("Hỏi về định giá P/E và mẫu số EPS của VIX", context)

    # Note, estimate flag, and symbol must be present in serialized prompt
    assert "Denominator uses period-end shares fallback" in prompt
    assert '"is_estimate":true' in prompt
    assert '"symbol":"VIX"' in prompt


# ==============================================================================
# Priority 5: Historical Cutoff (Q18) & General Portfolio (Q19)
# ==============================================================================

def test_q18_historical_intraday_honesty_disclosure(monkeypatch):
    """Q18: Queries requesting an intraday timestamp (e.g. 15:00) receive an explicit EOD limitation notice."""
    context = {
        "symbol": "VIX",
        "as_of_date": "2026-10-19",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "fundamentals", "status": "AVAILABLE", "data": {}}],
        "evidence": [{
            "claim_type": "FACT",
            "responsible_module": "fundamentals",
            "symbol": "VIX",
            "metric": "price",
            "value": 12500.0,
            "unit": "VND",
            "source": "LOTUSMARKET",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
        }],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "Giá VIX là 12500 đồng.",
        "claims": [{"claim_type": "FACT", "text": "Giá VIX là 12500 đồng.", "citation_ids": ["E001"]}],
        "uncertainty": [],
    })
    analyst = AIAnalyst(provider=provider)
    result = asyncio.run(analyst.answer_question(
        "Hãy đánh giá VIX tại thời điểm 15:00 ngày 19/10/2026",
        session=object(),
        as_of=date(2026, 10, 19),
    ))

    assert result["status"] == "PARTIAL"
    assert any("chốt phiên theo ngày (EOD)" in c["text"] for c in result["claims"])


def test_q19_portfolio_allocation_routing_without_single_ticker(monkeypatch):
    """Q19: General portfolio query without a recognized stock ticker routes to VN100 market context."""
    context = {
        "symbol": "VN100",
        "as_of_date": "2026-10-27",
        "decision_state": "AVAILABLE",
        "tools": [{"name": "regime", "status": "AVAILABLE", "data": {}}],
        "evidence": [{
            "claim_type": "MODEL_OUTPUT",
            "responsible_module": "regime",
            "symbol": "VN100",
            "metric": "market_regime",
            "value": "NEUTRAL",
            "source": "vn100_price_breadth_v1",
            "data_origin": "LINEAGED_INGESTION",
            "freshness": "AVAILABLE",
        }],
    }
    monkeypatch.setattr(AITools, "get_context", lambda *args, **kwargs: context)
    provider = FakeAnalystProvider({
        "answer": "Phương án phân bổ minh họa cho 100 triệu đồng trong thị trường hiện tại...",
        "claims": [{"claim_type": "MODEL_OUTPUT", "text": "Thị trường đang ở chế độ NEUTRAL.", "citation_ids": ["E001"]}],
        "uncertainty": ["Rủi ro tập trung ngành"],
    })
    analyst = AIAnalyst(provider=provider)
    q = "Giả sử tôi có 100 triệu đồng, thời gian đầu tư 3 năm; tôi muốn nghiên cứu phương pháp phân bổ danh mục cổ phiếu Việt Nam."
    result = asyncio.run(analyst.answer_question(q, session=object()))

    assert result["status"] in ("AVAILABLE", "PARTIAL")
    assert provider.called is True
    assert "phân bổ" in result["answer"] or "NEUTRAL" in result["answer"]
