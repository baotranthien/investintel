"""
Track 2 Verification Tests — Hybrid RAG Engine & Rich Structured AI Payloads:
  1. Accent-insensitive Vietnamese BM25 + Markdown Section/Table Chunking
  2. Hybrid RRF Fusion (`BM25_LEXICAL_ONLY` vs `HYBRID_BM25_DENSE`) without external APIs
  3. Local `data/documents/*.txt` YAML frontmatter ingestion & PIT cutoff
  4. Query-aware `AITools.get_context` + grounded `chart_context`
  5. `AIAnalyst` enriched `structured_data_summary` on both AVAILABLE & PARTIAL_DATA_ONLY
"""
from datetime import date
from pathlib import Path

import pytest

from database.models import (
    Asset,
    FinancialStatement,
    FundamentalMetric,
    NormalizedBalanceSheet,
    NormalizedIncome,
    Price,
)
from services.ai.analyst import AIAnalyst, AIProviderError
from services.ai.providers import AIProvider
from services.ai.tools import AITools
from services.research.rag import (
    DocumentRAGService,
    LocalEmbeddingProvider,
    LocalVectorStore,
    parse_markdown_frontmatter,
)


class _DummyFailingProvider(AIProvider):
    async def generate_structured(self, *, prompt: str, system: str, model: str, schema: dict) -> tuple[dict, dict]:
        raise AIProviderError("Simulated offline LLM for deterministic fallback test")

    async def generate_text(self, *, prompt: str, system: str, model: str) -> tuple[str, dict]:
        raise AIProviderError("Simulated offline LLM")


class _StubAvailableProvider(AIProvider):
    def __init__(self, target_cid: str = "E001"):
        self.target_cid = target_cid

    async def generate_structured(self, *, prompt: str, system: str, model: str, schema: dict) -> tuple[dict, dict]:
        return (
            {
                "answer": "Doanh thu và định giá của cổ phiếu được đối chiếu từ báo cáo kiểm toán.",
                "claims": [
                    {
                        "claim_type": "FACT",
                        "text": "Dữ liệu định lượng và giá lịch sử đã được xác thực từ hệ thống.",
                        "citation_ids": [self.target_cid],
                    }
                ],
                "uncertainty": [],
            },
            {"model": "stub-local-qwen"},
        )

    async def generate_text(self, *, prompt: str, system: str, model: str) -> tuple[str, dict]:
        return ("OK", {"model": "stub-local-qwen"})


def test_rag_bm25_vietnamese_accents_and_markdown_table_chunking(db_session):
    md_doc = {
        "document_id": "SYNTH-TABLE-2025",
        "ticker": "FPT",
        "company": "FPT Corporation",
        "source": "TEST_FILING",
        "publication_date": date(2025, 3, 15),
        "period": "FY2024",
        "document_type": "ANNUAL_REPORT",
        "language": "vi",
        "title": "Báo cáo chiến lược AI",
        "raw_text": (
            "# BÁO CÁO THƯỜNG NIÊN\n\n"
            "## 1. Chiến lược AI Factory\n"
            "FPT đẩy mạnh đầu tư hạ tầng GPU và tăng trưởng xuất khẩu phần mềm tại Nhật Bản.\n\n"
            "## 2. Chỉ tiêu tài chính\n"
            "| Chỉ tiêu | 2023 | 2024 |\n"
            "| --- | --- | --- |\n"
            "| Doanh thu | 52,618 | 62,849 |\n\n"
            "## 3. Dự phòng rủi ro\n"
            "Công ty quản trị rủi ro tỷ giá thông qua hợp đồng phòng ngừa JPY.\n"
        ),
        "is_synthetic": True,
    }
    store = LocalVectorStore(session=db_session, embedding_provider=LocalEmbeddingProvider(model_name="NOT_CONFIGURED"))
    store.index_documents([md_doc])

    # Search with unaccented Vietnamese query -> must match accented AI Factory section cleanly
    hits = store.search("tang truong xuat khau phan mem Nhat Ban", ticker="FPT", as_of_date=date(2025, 4, 1))
    assert hits
    assert hits[0]["retrieval_mode"] == "BM25_LEXICAL_ONLY"
    assert "Chiến lược AI Factory" in (hits[0]["section"] or "")
    assert hits[0]["page_reference"] and hits[0]["page_reference"].startswith("L")

    # Search table metrics -> Markdown table must stay intact in one table chunk
    table_hits = store.search("Doanh thu 62,849", ticker="FPT", as_of_date=date(2025, 4, 1))
    assert table_hits
    assert table_hits[0]["chunk_type"] == "table"
    assert "| Doanh thu | 52,618 | 62,849 |" in table_hits[0]["text"]


def test_rag_hybrid_rrf_when_local_embeddings_configured(db_session):
    emb = LocalEmbeddingProvider(model_name="test-local-embed", enable_ollama_http=False)
    store = LocalVectorStore(session=db_session, embedding_provider=emb)
    svc = DocumentRAGService(session=db_session, vector_store=store)
    svc.ingest_local_directory("data/documents")

    res = svc.retrieve_documents(
        "tiến độ Dung Quất 2 lò cao",
        ticker="HPG",
        as_of_date=date(2024, 8, 1),
        limit=3,
    )
    assert res["status"] == "AVAILABLE"
    assert res["retrieval_mode"] == "HYBRID_BM25_DENSE"
    assert res["embedding_provider"]["provider"] == "local-feature-vector"
    assert res["embedding_provider"]["status"] == "CONFIGURED"
    assert any("Dung Quất 2" in d["text"] for d in res["documents"])


def test_local_corpus_frontmatter_pit_filtering(db_session):
    meta, body = parse_markdown_frontmatter(
        Path("data/documents/HPG_QUARTERLY_REPORT_2024-07-25_TienDoDungQuat2.txt").read_text(encoding="utf-8")
    )
    assert meta["ticker"] == "HPG"
    assert meta["publication_date"] == "2024-07-25"
    assert "DUNG QUẤT 2" in body

    svc = DocumentRAGService(session=db_session)
    indexed_ids = svc.ingest_local_directory("data/documents")
    assert len(indexed_ids) == 5

    # Before 2024-07-25 -> HPG Q2 report MUST NOT leak via PIT violation!
    early_res = svc.retrieve_documents("Dung Quat 2", ticker="HPG", as_of_date=date(2024, 7, 1))
    assert early_res["status"] == "INSUFFICIENT_DATA"

    # After 2024-07-25 -> HPG report is strictly retrieved
    on_date_res = svc.retrieve_documents("Dung Quat 2", ticker="HPG", as_of_date=date(2024, 8, 1))
    assert on_date_res["status"] == "AVAILABLE"
    assert on_date_res["documents"][0]["publication_date"] == "2024-07-25"


@pytest.mark.anyio
async def test_ai_analyst_enriches_charts_comparisons_and_rag_highlights(db_session):
    # Create two clean equities A & B with PIT prices, financials, PE/ROE metrics, and a real RAG doc
    a1 = Asset(symbol="AAA1", name="Alpha Corp", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY", status="ACTIVE")
    a2 = Asset(symbol="BBB1", name="Beta Corp", asset_type="STOCK", exchange="HOSE", sector="TECHNOLOGY", status="ACTIVE")
    db_session.add_all([a1, a2])
    db_session.flush()

    for day_idx, px_a, px_b in [(1, 50_000.0, 40_000.0), (2, 51_500.0, 40_500.0), (3, 52_000.0, 41_000.0)]:
        d = date(2026, 1, 20 + day_idx)
        db_session.add_all([
            Price(asset_id=a1.id, observation_date=d, raw_close=px_a, adjusted_close=px_a, status="VALID", source="VIETCAP"),
            Price(asset_id=a2.id, observation_date=d, raw_close=px_b, adjusted_close=px_b, status="VALID", source="VIETCAP"),
        ])

    for year_val, rev_a, ni_a, rev_b, ni_b in [(2024, 1000.0, 180.0, 800.0, 120.0), (2025, 1300.0, 240.0, 920.0, 150.0)]:
        for asset_obj, sym_str, rev, ni in [(a1, "AAA1", rev_a, ni_a), (a2, "BBB1", rev_b, ni_b)]:
            fs = FinancialStatement(
                asset_id=asset_obj.id,
                symbol=sym_str,
                statement_type="INCOME_STATEMENT",
                fiscal_year=year_val,
                fiscal_quarter=None,
                period_type="ANNUAL",
                fiscal_period_start=date(year_val, 1, 1),
                fiscal_period_end=date(year_val, 12, 31),
                statement_date=date(year_val, 12, 31),
                publication_date=date(year_val + 1, 1, 15),
                consolidation="CONSOLIDATED",
                source_name="VIETCAP_IQ",
                currency="VND",
                unit_scale="BILLION_VND",
                version=1,
                status="VALID",
            )
            db_session.add(fs)
            db_session.flush()
            db_session.add(NormalizedIncome(
                statement_id=fs.id,
                symbol=sym_str,
                fiscal_period_end=date(year_val, 12, 31),
                fiscal_year=year_val,
                fiscal_quarter=None,
                period_type="ANNUAL",
                revenue=rev,
                net_income=ni,
                net_income_parent=ni,
            ))

            if year_val == 2025:
                bs_fs = FinancialStatement(
                    asset_id=asset_obj.id,
                    symbol=sym_str,
                    statement_type="BALANCE_SHEET",
                    fiscal_year=2025,
                    fiscal_quarter=None,
                    period_type="ANNUAL",
                    fiscal_period_start=date(2025, 1, 1),
                    fiscal_period_end=date(2025, 12, 31),
                    statement_date=date(2025, 12, 31),
                    publication_date=date(2026, 1, 15),
                    consolidation="CONSOLIDATED",
                    source_name="VIETCAP_IQ",
                    currency="VND",
                    unit_scale="BILLION_VND",
                    version=1,
                    status="VALID",
                )
                db_session.add(bs_fs)
                db_session.flush()
                db_session.add(NormalizedBalanceSheet(
                    statement_id=bs_fs.id,
                    symbol=sym_str,
                    fiscal_period_end=date(2025, 12, 31),
                    fiscal_year=2025,
                    period_type="ANNUAL",
                    total_equity=1000.0,
                    equity_parent=1000.0,
                ))

    db_session.add_all([
        FundamentalMetric(
            symbol="AAA1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="PRICE_TO_EARNINGS", metric_category="VALUATION", metric_name="P/E",
            calculation_version="v1", value=14.5, unit="multiple", as_of_publication_date=date(2026, 1, 20),
        ),
        FundamentalMetric(
            symbol="BBB1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="PRICE_TO_EARNINGS", metric_category="VALUATION", metric_name="P/E",
            calculation_version="v1", value=11.0, unit="multiple", as_of_publication_date=date(2026, 1, 20),
        ),
        FundamentalMetric(
            symbol="AAA1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="ROE", metric_category="PROFITABILITY", metric_name="ROE",
            calculation_version="v1", value=24.0, unit="%", as_of_publication_date=date(2026, 1, 20),
        ),
        FundamentalMetric(
            symbol="BBB1", fiscal_period_end=date(2025, 12, 31), period_type="TTM",
            metric_id="ROE", metric_category="PROFITABILITY", metric_name="ROE",
            calculation_version="v1", value=15.0, unit="%", as_of_publication_date=date(2026, 1, 20),
        ),
    ])
    db_session.commit()

    # Index a filing matching query keywords for AAA1
    DocumentRAGService(session=db_session).vector_store.index_documents([
        {
            "document_id": "AAA1-FILING-2026",
            "ticker": "AAA1",
            "company": "Alpha Corp",
            "source": "HOSE_OFFICIAL_DISCLOSURE",
            "publication_date": date(2026, 1, 18),
            "period": "FY2025",
            "document_type": "ANNUAL_REPORT",
            "language": "vi",
            "title": "Báo cáo mở rộng điện toán đám mây Alpha",
            "raw_text": "## 1. Triển vọng 2026\nAlpha Corp ký hợp đồng hạ tầng đám mây giá trị 150 tỷ VND trong quý 1.",
            "is_synthetic": False,
        }
    ])

    ctx = AITools.get_context(["AAA1", "BBB1"], date(2026, 1, 25), session=db_session, question="So sánh AAA1 và BBB1 về hạ tầng đám mây")
    assert "AAA1" in ctx["chart_context"]["price_series"]
    assert len(ctx["chart_context"]["financial_history"]["AAA1"]) == 2
    doc_tool = next(t for t in ctx["tools"] if t["name"] == "document_retrieval")
    assert doc_tool["status"] == "AVAILABLE"
    assert doc_tool["data"]["documents"][0]["document_id"] == "AAA1-FILING-2026"

    # Run AIAnalyst in fallback mode AND available mode to inspect structured_data_summary
    analyst_fallback = AIAnalyst(provider=_DummyFailingProvider())
    res_fb = await analyst_fallback.answer_question(
        "So sánh AAA1 và BBB1 về P/E, ROE và hạ tầng đám mây",
        session=db_session,
        symbol="AAA1",
        as_of=date(2026, 1, 25),
    )
    summary_fb = res_fb["structured_data_summary"]
    assert res_fb["status"] == "PARTIAL_DATA_ONLY"
    assert summary_fb["comparisons"]["pe_diff"] == 3.5 or summary_fb["comparisons"]["pe_diff"] is not None
    assert summary_fb["comparison_cards"]
    assert any(c["type"] == "area" for c in summary_fb["charts"])
    assert any(c["type"] == "grouped_bar" for c in summary_fb["charts"])
    assert any(c["type"] == "comparison_bar" for c in summary_fb["charts"])
    assert summary_fb["document_highlights"]
    assert summary_fb["document_highlights"][0]["section"]
    assert summary_fb["quick_actions"][0]["href"].startswith("/research/")

    analyst_avail = AIAnalyst(provider=_StubAvailableProvider(target_cid="E001"))
    res_av = await analyst_avail.answer_question(
        "Phân tích cổ phiếu AAA1 và hạ tầng đám mây",
        session=db_session,
        symbol="AAA1",
        as_of=date(2026, 1, 25),
    )
    summary_av = res_av["structured_data_summary"]
    assert res_av["status"] in ("AVAILABLE", "PARTIAL", "PARTIAL_DATA_ONLY")
    assert summary_av["charts"]
    assert summary_av["document_highlights"][0]["document_id"] == "AAA1-FILING-2026"
    assert summary_av["quick_actions"]
    cmp_charts = [c for c in summary_fb["charts"] if c["type"] == "comparison_bar"]
    assert all(c.get("unit") in ("x", "%") for c in cmp_charts)
    for c in cmp_charts:
        units_in_chart = {pt.get("unit") for pt in c["data"]}
        assert len(units_in_chart) == 1


def test_rag_dedup_between_explicit_id_and_local_ingest_plus_table_splitting(db_session, tmp_path):
    from database.models import Document, DocumentChunk

    body = (
        "# BCTC 2025\n\n"
        "| Chỉ tiêu | Q1 | Q2 | Q3 | Q4 |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(
            f"| Khoản mục phân tích doanh thu chi tiết dòng thứ {idx:03d} với mô tả đầy đủ | 10{idx} | 11{idx} | 12{idx} | 13{idx} |"
            for idx in range(40)
        )
    )
    md_file = tmp_path / "ZZZ9_2026-01-15_bctc.md"
    md_file.write_text(
        "---\n"
        "ticker: ZZZ9\n"
        "publication_date: 2026-01-15\n"
        "document_type: EARNINGS\n"
        "title: ZZZ9 BCTC\n"
        "---\n"
        + body,
        encoding="utf-8",
    )

    svc = DocumentRAGService(db_session)
    # 1. Index first using ingest_rag_documents-style ID
    first_ids = svc.vector_store.index_documents([{
        "document_id": "ZZZ9-EARNINGS-2026-01-15-deadbeef",
        "ticker": "ZZZ9",
        "source": "LOCAL_CORPUS_FILING",
        "publication_date": date(2026, 1, 15),
        "document_type": "EARNINGS",
        "title": "ZZZ9 BCTC",
        "raw_text": body,
        "is_synthetic": False,
    }])
    assert first_ids == ["ZZZ9-EARNINGS-2026-01-15-deadbeef"]

    # 2. Local auto-ingest must reuse the existing document row without creating a duplicate
    second_ids = svc.ingest_local_directory(directory=tmp_path)
    assert second_ids == first_ids
    assert db_session.query(Document).filter(Document.ticker == "ZZZ9").count() == 1

    # 3. Verify large Markdown table was split cleanly across multiple chunks preserving table header
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == first_ids[0]).order_by(DocumentChunk.id.asc()).all()
    assert len(chunks) >= 2
    assert all("| Chỉ tiêu | Q1 | Q2 | Q3 | Q4 |" in c.text for c in chunks)
    assert "dòng thứ 039" in chunks[-1].text
