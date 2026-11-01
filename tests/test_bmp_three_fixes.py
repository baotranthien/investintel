# -*- coding: utf-8 -*-
"""
Targeted tests for the 3 fixes from the BMP Qwen 3.5 9B diagnostic report:
1. Dynamic Evidence Selection: Prioritizes user-requested metrics and scales context budget (up to 16 items).
2. UI Decoupling Contract: AppleSmartFallback alarmist banner only triggers in fallback mode (PARTIAL_DATA_ONLY).
3. Status Determination Logic: Differentiates between missing requested metrics vs auxiliary caveat uncertainties.
"""
from datetime import date
from decimal import Decimal
import re
import pytest

from services.ai.analyst import AIAnalyst
from services.ai.prompt_registry import (
    METRIC_CATEGORY_PATTERNS,
    build_chat_prompt,
    extract_requested_metric_groups,
)
from services.ai.schemas import AIChatResponse, AICitation, AIClaim


def test_extract_requested_metric_groups():
    """Verify keyword extraction for metric categories."""
    q1 = "Phân tích biên lợi nhuận gộp, biên ròng và tỷ lệ nợ của BMP"
    groups1 = extract_requested_metric_groups(q1)
    assert "gross_margin" in groups1
    assert "net_margin" in groups1
    assert ("debt_to_assets" in groups1 or "debt_generic" in groups1)

    q2 = "Định giá P/E, P/B hiện tại của BMP so với ngành, doanh thu và dòng tiền thế nào?"
    groups2 = extract_requested_metric_groups(q2)
    assert "pe" in groups2
    assert "pb" in groups2
    assert "revenue" in groups2
    assert ("operating_cash_flow" in groups2 or "cash_flow_generic" in groups2)

    q3 = "BMP có tốt không?"
    groups3 = extract_requested_metric_groups(q3)
    assert len(groups3) == 0

    # Specific atomic indicators
    q4 = "Phân tích nợ phải trả/tổng tài sản, nợ vay/vốn chủ, lưu chuyển tiền thuần từ HĐKD và tiền mặt của BMP"
    groups4 = extract_requested_metric_groups(q4)
    assert "debt_to_assets" in groups4
    assert "debt_to_equity" in groups4
    assert "operating_cash_flow" in groups4
    assert "cash_balance" in groups4


def test_build_chat_prompt_prioritizes_requested_metrics():
    """Verify build_chat_prompt selects and prioritizes requested indicators instead of cutting off at 5."""
    evidence = [
        {"id": f"E{i:03d}", "metric": f"other_metric_{i}", "value": 1.0, "unit": "x", "source": "TEST", "symbol": "BMP", "claim_type": "FACT", "data_origin": "CANONICAL", "freshness": "AVAILABLE"}
        for i in range(1, 20)
    ]
    # Add target metrics near the end of the evidence register
    evidence.extend([
        {"id": "E100", "metric": "gross_margin", "value": 44.86, "unit": "%", "source": "TEST", "symbol": "BMP", "claim_type": "FACT", "data_origin": "CANONICAL", "freshness": "AVAILABLE"},
        {"id": "E101", "metric": "net_margin", "value": 22.47, "unit": "%", "source": "TEST", "symbol": "BMP", "claim_type": "FACT", "data_origin": "CANONICAL", "freshness": "AVAILABLE"},
        {"id": "E102", "metric": "debt_to_assets", "value": 15.38, "unit": "%", "source": "TEST", "symbol": "BMP", "claim_type": "FACT", "data_origin": "CANONICAL", "freshness": "AVAILABLE"},
    ])

    context = {
        "symbol": "BMP",
        "symbols": ["BMP"],
        "as_of_date": "2026-10-28",
        "evidence_register": evidence,
    }

    question = "Phân tích biên lợi nhuận gộp và ròng (gross & net margin) cùng tỷ lệ nợ của BMP"
    prompt = build_chat_prompt(question, context)

    # Verify that gross_margin, net_margin, and debt_to_assets are present in the prompt
    assert "gross_margin" in prompt
    assert "44.86" in prompt
    assert "net_margin" in prompt
    assert "22.47" in prompt
    assert "debt_to_assets" in prompt
    assert "15.38" in prompt

    # Verify telemetry in compact_context and context
    telemetry = context.get("evidence_telemetry")
    assert telemetry is not None
    assert "gross_margin" in telemetry["requested_categories"]
    assert ("debt_to_assets" in telemetry["requested_categories"] or "debt_generic" in telemetry["requested_categories"])
    assert telemetry["selected_count"] > 5


def test_status_determination_available_with_auxiliary_caveat():
    """Verify status is AVAILABLE when requested metrics are fulfilled, even if an auxiliary caveat exists."""
    question = "Phân tích biên lợi nhuận gộp, biên ròng và tỷ lệ nợ phải trả/tổng tài sản của BMP"
    requested_groups = extract_requested_metric_groups(question)
    assert "gross_margin" in requested_groups
    assert "net_margin" in requested_groups
    assert "debt_to_assets" in requested_groups

    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="gross_margin", value=44.86, unit="%", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="net_margin", value=22.47, unit="%", source="TEST", symbol="BMP"),
        "E003": AICitation(id="E003", claim_type="FACT", responsible_module="fundamentals", metric="debt_to_assets", value=15.38, unit="%", source="TEST", symbol="BMP"),
    }

    substantive_claims = [
        AIClaim(claim_type="FACT", text="Biên lợi nhuận gộp đạt 44.86% và biên ròng đạt 22.47%.", citation_ids=["E001", "E002"]),
        AIClaim(claim_type="FACT", text="Tỷ lệ nợ trên tổng tài sản duy trì ở mức an toàn 15.38%.", citation_ids=["E003"]),
    ]

    auxiliary_caveat = AIClaim(
        claim_type="UNCERTAINTY",
        text="Cần lưu ý rủi ro biến động giá nguyên vật liệu PVC từ thị trường quốc tế.",
        citation_ids=[],
    )

    all_claims = substantive_claims + [auxiliary_caveat]

    status, uncovered_requested_groups = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=all_claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )

    assert uncovered_requested_groups == set()
    assert status == "AVAILABLE"


def test_status_determination_partial_when_requested_metric_missing():
    """Verify status is PARTIAL when a directly requested metric category is missing from citations."""
    question = "Phân tích biên lợi nhuận gộp, biên ròng và tỷ lệ nợ phải trả/tổng tài sản của BMP"
    requested_groups = extract_requested_metric_groups(question)

    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="gross_margin", value=44.86, unit="%", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="net_margin", value=22.47, unit="%", source="TEST", symbol="BMP"),
    }

    substantive_claims = [
        AIClaim(claim_type="FACT", text="Biên lợi nhuận gộp đạt 44.86% và biên ròng đạt 22.47%.", citation_ids=["E001", "E002"]),
    ]

    status, uncovered_requested_groups = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=substantive_claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )

    assert "debt_to_assets" in uncovered_requested_groups
    assert status == "PARTIAL"


# ==============================================================================
# PHASE 2 HARDENING: 10 SPECIFIC TEST SCENARIOS
# ==============================================================================

def test_scenario_1_gross_margin_requested_not_satisfied_by_net_margin():
    """Scenario 1: Gross Margin requested != Net Margin provided -> PARTIAL."""
    question = "Biên lợi nhuận gộp của BMP là bao nhiêu?"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="net_margin", value=22.47, unit="%", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Biên lợi nhuận ròng đạt 22.47%.", citation_ids=["E001"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "gross_margin" in uncovered
    assert status == "PARTIAL"


def test_scenario_2_debt_to_assets_requested_not_satisfied_by_debt_to_equity():
    """Scenario 2: Debt-to-Assets requested != Debt-to-Equity provided -> PARTIAL."""
    question = "Tỷ lệ nợ phải trả trên tổng tài sản của BMP là bao nhiêu?"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="de_ratio", value=0.15, unit="x", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Tỷ lệ nợ vay trên vốn chủ đạt 0.15 lần.", citation_ids=["E001"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "debt_to_assets" in uncovered
    assert status == "PARTIAL"


def test_scenario_3_operating_cash_flow_requested_not_satisfied_by_cash_balance():
    """Scenario 3: Operating Cash Flow requested != Cash Balance provided -> PARTIAL."""
    question = "Lưu chuyển tiền thuần từ HĐKD của BMP như thế nào?"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="cash", value=1200000000000, unit="VND", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Tiền và tương đương tiền hiện tại đạt 1,200 tỷ VND.", citation_ids=["E001"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "operating_cash_flow" in uncovered
    assert status == "PARTIAL"


def test_scenario_4_empty_requested_metric_list_no_automatic_available():
    """Scenario 4: Empty requested metric list does not automatically yield AVAILABLE if claims ungrounded."""
    question = "BMP có tốt không?"
    # Substantive claims with no valid citations
    claims = [
        AIClaim(claim_type="FACT", text="BMP là doanh nghiệp sản xuất ống nhựa hàng đầu.", citation_ids=[]),
    ]
    status, _ = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id={},
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert status == "PARTIAL"


def test_scenario_5_general_bmp_query_status_based_on_substantive_claims():
    """Scenario 5: General BMP query achieves AVAILABLE when valid substantive claims are grounded."""
    question = "Đánh giá cổ phiếu BMP"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="market", metric="price", value=125000, unit="VND", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="pe", value=9.8, unit="x", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Thị giá BMP là 125,000 VND với hệ số P/E đạt 9.8 lần.", citation_ids=["E001", "E002"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert uncovered == set()
    assert status == "AVAILABLE"


def test_scenario_6_three_metrics_requested_only_two_cited_is_partial():
    """Scenario 6: 3 metrics requested, only 2 cited -> PARTIAL."""
    question = "Cho biết doanh thu, biên lợi nhuận gộp và nợ vay/vốn chủ của BMP"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="revenue", value=5000000000000, unit="VND", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="gross_margin", value=44.86, unit="%", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Doanh thu đạt 5,000 tỷ VND và biên gộp là 44.86%.", citation_ids=["E001", "E002"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "debt_to_equity" in uncovered
    assert status == "PARTIAL"


def test_scenario_7_three_metrics_requested_all_three_cited_is_available():
    """Scenario 7: 3 metrics requested, all 3 cited with matching evidence -> AVAILABLE."""
    question = "Cho biết doanh thu, biên lợi nhuận gộp và nợ vay/vốn chủ của BMP"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="revenue", value=5000000000000, unit="VND", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="gross_margin", value=44.86, unit="%", source="TEST", symbol="BMP"),
        "E003": AICitation(id="E003", claim_type="FACT", responsible_module="fundamentals", metric="de_ratio", value=0.15, unit="x", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Doanh thu đạt 5,000 tỷ VND, biên gộp là 44.86% và tỷ lệ D/E là 0.15 lần.", citation_ids=["E001", "E002", "E003"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert uncovered == set()
    assert status == "AVAILABLE"


def test_scenario_8_secondary_caveat_outside_query_scope_does_not_demote_available():
    """Scenario 8: Secondary caveat outside query scope does not demote AVAILABLE."""
    question = "Biên lợi nhuận gộp và doanh thu của BMP thế nào?"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="fundamentals", metric="gross_margin", value=44.86, unit="%", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="revenue", value=5000000000000, unit="VND", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Doanh thu 5,000 tỷ VND và biên gộp 44.86%.", citation_ids=["E001", "E002"]),
        AIClaim(claim_type="UNCERTAINTY", text="Cần lưu ý rủi ro biến động giá nguyên vật liệu PVC thế giới.", citation_ids=[]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=["Rủi ro giá hạt nhựa PVC thế giới biến động."],
        canonical_symbol="BMP",
    )
    assert uncovered == set()
    assert status == "AVAILABLE"


def test_scenario_9_claim_citing_wrong_metric_citation_is_not_covered():
    """Scenario 9: Claim citing wrong metric citation is not covered -> PARTIAL."""
    question = "Tỷ lệ nợ phải trả trên tổng tài sản của BMP là bao nhiêu?"
    # Claim says debt ratio is 9.8%, but cites E005 which has metric 'pe'
    evidence_by_id = {
        "E005": AICitation(id="E005", claim_type="FACT", responsible_module="fundamentals", metric="pe", value=9.8, unit="x", source="TEST", symbol="BMP"),
    }
    claims = [
        AIClaim(claim_type="FACT", text="Tỷ lệ nợ trên tổng tài sản là 9.8%.", citation_ids=["E005"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "debt_to_assets" in uncovered
    assert status == "PARTIAL"


def test_scenario_10_bento_grid_metrics_omitted_from_ai_narrative_not_counted_as_ai_answer():
    """Scenario 10: Bento grid structured summary does not count as AI narrative coverage -> PARTIAL."""
    question = "Phân tích ROE của BMP"
    evidence_by_id = {
        "E001": AICitation(id="E001", claim_type="FACT", responsible_module="market", metric="price", value=125000, unit="VND", source="TEST", symbol="BMP"),
        "E002": AICitation(id="E002", claim_type="FACT", responsible_module="fundamentals", metric="roe", value=35.2, unit="%", source="TEST", symbol="BMP"),
    }
    # AI narrative only cites price E001; ROE E002 is present only in structured table
    claims = [
        AIClaim(claim_type="FACT", text="Thị giá BMP là 125,000 VND.", citation_ids=["E001"]),
    ]
    status, uncovered = AIAnalyst.determine_response_status(
        question=question,
        cited_claims=claims,
        evidence_by_id=evidence_by_id,
        final_uncertainty=[],
        canonical_symbol="BMP",
    )
    assert "roe" in uncovered
    assert status == "PARTIAL"


def test_ui_fallback_banner_decoupling_contract():
    """Verify frontend code enforces decoupling: AppleSmartFallback receives isFallbackMode."""
    with open("apps/web/src/components/apple-smart-fallback.tsx", "r", encoding="utf-8") as f:
        fallback_code = f.read()

    assert "isFallbackMode?: boolean" in fallback_code
    assert "{isFallbackMode && (" in fallback_code

    with open("apps/web/src/app/ai/page.tsx", "r", encoding="utf-8") as f:
        page_code = f.read()

    assert 'isFallbackMode={answer.status === "PARTIAL_DATA_ONLY"}' in page_code
