from datetime import date

from database.models import Document, DocumentChunk
from services.research.rag import DocumentRAGService, LocalEmbeddingProvider


def test_local_rag_seeded_documents_are_temporally_filtered(db_session):
    service = DocumentRAGService(session=db_session)
    service.seed_fixture_documents()

    early = service.retrieve_documents(
        "FPT revenue and cash position",
        ticker="FPT",
        as_of_date=date(2023, 6, 1),
        limit=10,
    )
    assert early["status"] == "AVAILABLE"
    assert len(early["documents"]) == 1
    assert all(item["publication_date"] <= "2023-06-01" for item in early["documents"])

    later = service.retrieve_documents(
        "FPT revenue and operating efficiency",
        ticker="FPT",
        as_of_date=date(2023, 10, 1),
        limit=10,
    )
    assert later["status"] == "AVAILABLE"
    assert len(later["documents"]) >= 2
    assert all(item["publication_date"] <= "2023-10-01" for item in later["documents"])


def test_local_rag_filters_ticker_and_source(db_session):
    service = DocumentRAGService(session=db_session)
    service.seed_fixture_documents()

    result = service.retrieve_documents(
        "Vietcombank liquidity stability",
        ticker="VCB",
        as_of_date=date(2023, 9, 1),
        limit=10,
    )
    assert result["status"] == "AVAILABLE"
    assert all(item["ticker"] == "VCB" for item in result["documents"])
    assert all(item["source"] == "SYNTHETIC_FIXTURE" for item in result["documents"])
    assert all(item["document_id"].startswith("VCB") for item in result["documents"])


def test_local_rag_citation_ids_point_to_real_chunks_and_are_deterministic(db_session):
    service = DocumentRAGService(session=db_session)
    service.seed_fixture_documents()

    first = service.retrieve_documents(
        "FPT digital transformation operating efficiency",
        ticker="FPT",
        as_of_date=date(2023, 10, 1),
        limit=5,
    )
    second = service.retrieve_documents(
        "FPT digital transformation operating efficiency",
        ticker="FPT",
        as_of_date=date(2023, 10, 1),
        limit=5,
    )

    assert first["status"] == "AVAILABLE"
    assert first["documents"] == second["documents"]
    assert all(item["citation_id"].startswith("FPT-") for item in first["documents"])
    assert all(item["chunk_id"] for item in first["documents"])
    assert all(item["text"] for item in first["documents"])


def test_local_rag_empty_result_returns_insufficient_data(db_session):
    db_session.query(DocumentChunk).delete()
    db_session.query(Document).delete()
    db_session.commit()

    service = DocumentRAGService(session=db_session)
    result = service.retrieve_documents(
        "nonexistent company concept only for test coverage",
        ticker="ZZZ",
        as_of_date=date(2023, 1, 1),
        limit=5,
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["documents"] == []


def test_local_embedding_provider_reports_configured_or_not_configured():
    provider = LocalEmbeddingProvider()
    status = provider.describe()
    assert status["provider"] == "local-feature-vector"
    assert status["status"] in {"CONFIGURED", "NOT_CONFIGURED"}
