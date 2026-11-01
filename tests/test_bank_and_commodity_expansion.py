import asyncio
from datetime import date
from database.connection import SessionLocal
from database.models import Asset, BankMetric, MacroCommodity
from services.ai.analyst import AIAnalyst
from services.ai.tools import AITools


class MockDraftProvider:
    def __init__(self, draft: dict | None = None):
        self.draft = draft or {
            "answer": "Báo cáo phân tích tự động.",
            "claims": [
                {
                    "claim_type": "FACT",
                    "text": "Số liệu được kiểm chứng tự động.",
                    "citation_ids": ["E001"],
                }
            ],
            "uncertainty": [],
        }

    async def generate_structured(self, prompt, **kwargs):
        return self.draft, {"eval_count": 25}


def test_bank_metrics_extraction_and_precomputation():
    db = SessionLocal()
    try:
        # Check context for MBB and VCB
        context = AITools.get_context(
            symbol=["MBB", "VCB"],
            as_of=date(2026, 10, 27),
            session=db,
            question="So sánh tăng trưởng tín dụng, NIM và tỷ lệ nợ xấu của MBB và VCB trong 2 quý gần nhất?",
        )
        evidence = context.get("evidence", [])
        assert evidence, "Evidence should not be empty for MBB and VCB"

        # Check bank metrics exist in evidence
        mbb_nim = next((e for e in evidence if e.get("symbol") == "MBB" and e.get("metric") == "nim"), None)
        vcb_nim = next((e for e in evidence if e.get("symbol") == "VCB" and e.get("metric") == "nim"), None)
        assert mbb_nim is not None, "MBB NIM should be present in evidence"
        assert vcb_nim is not None, "VCB NIM should be present in evidence"
        assert float(mbb_nim["value"]) > 4.0
        assert float(vcb_nim["value"]) < 3.5

        # Check analyst precomputation
        analyst = AIAnalyst(provider=MockDraftProvider())
        citations = analyst._citations(context)
        injected = analyst._inject_precomputed_metrics(citations, ["MBB", "VCB"], context)

        # Check nim_diff citation
        nim_diff = next((c for c in injected if c.metric == "nim_diff"), None)
        assert nim_diff is not None, "Precomputed nim_diff citation should be present"
        assert nim_diff.value == round(float(mbb_nim["value"]) - float(vcb_nim["value"]), 2)
        assert "MBB,VCB" in nim_diff.symbol

        # Check credit_growth_diff citation
        credit_diff = next((c for c in injected if c.metric == "credit_growth_diff"), None)
        assert credit_diff is not None, "Precomputed credit_growth_diff citation should be present"

        # Check structured summary
        summary, flags = analyst._build_structured_data_summary(injected, context, ["MBB", "VCB"])
        assert "nim_diff" in summary["comparisons"]
        assert "MBB" in summary["symbols"]
        assert "VCB" in summary["symbols"]
        assert "nim" in summary["symbols"]["MBB"]["metrics"]
    finally:
        db.close()


def test_commodity_extraction_and_pearson_correlation():
    db = SessionLocal()
    try:
        # Check context for PLX and oil keywords
        context = AITools.get_context(
            symbol="PLX",
            as_of=date(2026, 10, 27),
            session=db,
            question="PLX có mối tương quan như thế nào với giá dầu Brent thế giới trong quý gần nhất?",
        )
        evidence = context.get("evidence", [])
        assert evidence, "Evidence should not be empty for PLX"

        # Check brent_close exists in evidence
        brent_ev = next((e for e in evidence if e.get("metric") == "brent_close"), None)
        assert brent_ev is not None, "BRENT close price should be present in evidence"
        assert float(brent_ev["value"]) > 50.0

        # Check series are present in context
        assert "commodity_series" in context and context["commodity_series"] is not None
        assert "stock_price_series" in context and context["stock_price_series"] is not None
        assert len(context["commodity_series"]) >= 5

        # Check analyst precomputes pearson correlation
        analyst = AIAnalyst(provider=MockDraftProvider())
        citations = analyst._citations(context)
        injected = analyst._inject_precomputed_metrics(citations, ["PLX"], context)

        pearson = next((c for c in injected if c.metric == "pearson_correlation"), None)
        assert pearson is not None, "Pearson correlation citation should be present"
        assert -1.0 <= pearson.value <= 1.0
        assert pearson.symbol == "PLX"

        # Check fallback claims
        summary, flags = analyst._build_structured_data_summary(injected, context, ["PLX"])
        fallback_claims = analyst._build_fallback_claims(injected, summary, ["PLX"])
        assert any("tương quan" in c.text.lower() or "pearson" in c.text.lower() for c in fallback_claims)
    finally:
        db.close()


def test_q03_q10_smoke_execution():
    async def _run():
        db = SessionLocal()
        try:
            analyst = AIAnalyst(provider=MockDraftProvider())

            # Q03
            res_q03 = await analyst.answer_question(
                "So sánh tăng trưởng tín dụng, NIM và tỷ lệ nợ xấu của MBB và VCB trong 2 quý gần nhất?",
                session=db,
                as_of=date(2026, 10, 27),
            )
            assert res_q03["status"] in {"AVAILABLE", "PARTIAL_DATA_ONLY", "PARTIAL"}
            assert res_q03["structured_data_summary"] is not None
            assert "MBB" in res_q03["structured_data_summary"]["symbols"]
            assert "VCB" in res_q03["structured_data_summary"]["symbols"]

            # Q10
            res_q10 = await analyst.answer_question(
                "PLX có mối tương quan như thế nào với giá dầu Brent thế giới trong quý gần nhất?",
                session=db,
                as_of=date(2026, 10, 27),
            )
            assert res_q10["status"] in {"AVAILABLE", "PARTIAL_DATA_ONLY", "PARTIAL"}
            assert res_q10["structured_data_summary"] is not None
            assert any(c["metric"] == "pearson_correlation" for c in res_q10["citations"])
        finally:
            db.close()

    asyncio.run(_run())
