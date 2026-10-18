"""
Smoke and Unit Tests for Public Vietnam Stock and News Ingestion.
Tests:
1. DNSE Market Data Provider (OHLCV fetching, timezone, scaling, pipeline promotion).
2. Vietstock News Provider (Article parsing, EventRecord promotion, pipeline lineage).
3. Data quality checks, staging rejections, lineage integrity, and run logging.
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from database.models import (
    Asset,
    Price,
    EventRecord,
    DataLineage,
    DataRun,
    DataQualityReportRecord,
    StagingRecord,
    DataSource,
)
from services.ingestion.dnse import DnseProvider, normalize_symbol, _VN_TZ
from services.ingestion.vietstock import VietstockNewsProvider
from services.ingestion.pipeline import IngestionPipeline


def test_dnse_symbol_normalization():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol(" vcb ") == "VCB"
    assert normalize_symbol("mbb.vn") == "MBBVN"
    assert normalize_symbol("hp-g") == "HPG"
    assert normalize_symbol("") == ""


def test_dnse_payload_parsing_and_scaling():
    provider = DnseProvider()
    mock_payload = {
        "t": [1791770400, 1791856800],
        "o": [58.1, 57.1],
        "h": [58.8, 57.4],
        "l": [57.1, 56.1],
        "c": [57.1, 56.3],
        "v": [5930000, 6775400]
    }

    with patch.object(provider, "_fetch_raw_response", return_value=(200, str(mock_payload).replace("'", '"').encode("utf-8"))):
        # Let's request the range that covers both timestamps
        start_d = date(2026, 10, 10)
        end_d = date(2026, 10, 20)
        records = provider.fetch_ohlcv("FPT", start_d, end_d, is_index=False)

        assert len(records) == 2
        # Verify 1000.0 scale applied to stock prices
        assert records[0]["close"] == 57100.0
        assert records[0]["open"] == 58100.0
        assert records[0]["high"] == 58800.0
        assert records[0]["low"] == 57100.0
        assert records[0]["volume"] == 5930000.0
        assert isinstance(records[0]["observation_date"], date)


def test_dnse_handles_empty_and_error_responses_safely():
    provider = DnseProvider()
    # 404 response
    with patch.object(provider, "_fetch_raw_response", return_value=(404, b"")):
        res = provider.fetch_ohlcv("INVALID_TICKER", date(2026, 1, 1), date(2026, 1, 5))
        assert res == []

    # Malformed JSON
    with patch.object(provider, "_fetch_raw_response", return_value=(200, b"not a json")):
        res = provider.fetch_ohlcv("FPT", date(2026, 1, 1), date(2026, 1, 5))
        assert res == []


def test_dnse_live_smoke_ingestion(db_session):
    """
    Real Smoke Test:
    Fetches actual recent data for FPT from DNSE public API with minimal requests (5 days),
    ingests via IngestionPipeline into PostgreSQL, and validates lineage, run, and quality report.
    """
    source = db_session.query(DataSource).filter(DataSource.name == "DNSE").first()
    if not source:
        source = DataSource(
            name="DNSE",
            provider="DNSE (Entrade Public Market Data API)",
            country="VNM",
            authority_level="REPUTABLE_SECONDARY",
            source_type="API",
            base_url="https://services.entrade.com.vn/chart-api/v2/ohlcs",
            license_status="PUBLIC_RESEARCH_ONLY",
            access_method="PUBLIC_HTTP",
            active=True
        )
        db_session.add(source)
        db_session.flush()

    provider = DnseProvider()
    end_date = date.today()
    start_date = end_date - timedelta(days=5)

    outcome = provider.ingest_to_database(
        session=db_session,
        symbol="FPT",
        start_date=start_date,
        end_date=end_date,
        exchange="HOSE",
        source_id=source.id
    )

    assert outcome["provider"] == "DNSE"
    assert outcome["symbol"] == "FPT"
    assert outcome["status"] in ("SUCCESS", "PARTIAL", "INSUFFICIENT_DATA")

    if outcome["records_valid"] > 0:
        # Check canonical Price table
        asset = db_session.query(Asset).filter(Asset.symbol == "FPT").first()
        assert asset is not None
        prices = db_session.query(Price).filter(Price.asset_id == asset.id).all()
        assert len(prices) > 0

        # Check DataLineage record
        lineage = db_session.query(DataLineage).filter(
            DataLineage.record_table == "prices",
            DataLineage.raw_source.like("%DNSE%")
        ).first()
        assert lineage is not None
        assert lineage.url.startswith("https://services.entrade.com.vn")

        # Check DataRun
        run = db_session.query(DataRun).filter(DataRun.run_id == outcome["run_id"]).first()
        assert run is not None
        assert run.provider == "DNSE"
        assert run.records_fetched == outcome["records_received"]

        # Check DataQualityReportRecord
        report = db_session.query(DataQualityReportRecord).filter(
            DataQualityReportRecord.run_id == outcome["run_id"]
        ).first()
        assert report is not None
        assert report.completeness_score > 0.0


def test_vietstock_live_smoke_ingestion(db_session):
    """
    Real Smoke Test:
    Fetches real today news from https://vietstock.info/api/news/today,
    ingests via IngestionPipeline, and validates EventRecord, DataLineage, and DataRun.
    """
    source = db_session.query(DataSource).filter(DataSource.name == "VIETSTOCK").first()
    if not source:
        source = DataSource(
            name="VIETSTOCK",
            provider="Vietstock Public News API",
            country="VNM",
            authority_level="REPUTABLE_SECONDARY",
            source_type="API",
            base_url="https://vietstock.info/api/news/today",
            license_status="PUBLIC_RESEARCH_ONLY",
            access_method="PUBLIC_HTTP",
            active=True
        )
        db_session.add(source)
        db_session.flush()

    provider = VietstockNewsProvider()
    outcome = provider.ingest_to_database(
        session=db_session,
        source_id=source.id
    )

    assert outcome["provider"] == "VIETSTOCK"
    assert outcome["dataset"] == "news_events"
    assert outcome["status"] in ("SUCCESS", "PARTIAL", "INSUFFICIENT_DATA")

    if outcome["records_valid"] > 0:
        # Verify EventRecord exists
        events = db_session.query(EventRecord).all()
        assert len(events) > 0

        # Verify Lineage
        lineage = db_session.query(DataLineage).filter(
            DataLineage.record_table == "events",
            DataLineage.raw_source.like("%VIETSTOCK%")
        ).first()
        assert lineage is not None

        # Verify DataRun
        run = db_session.query(DataRun).filter(DataRun.run_id == outcome["run_id"]).first()
        assert run is not None
        assert run.provider == "VIETSTOCK"


def test_pipeline_rejects_malformed_news_articles(db_session):
    """
    Verifies that invalid articles (missing title or missing URL) are rejected
    into StagingRecord and not promoted to EventRecord.
    """
    pipeline = IngestionPipeline(db_session)
    malformed_articles = [
        {"id": 99991, "title": "", "url": "https://example.com/empty-title", "published_at": "2026-10-14T10:00:00Z"},
        {"id": 99992, "title": "Valid Title", "url": "", "published_at": "2026-10-14T10:00:00Z"},
        {"id": 99993, "title": "No Published At", "url": "https://example.com/no-pub", "published_at": None},
    ]

    outcome = pipeline.ingest_news_events(
        provider="TEST_PROVIDER",
        articles=malformed_articles,
        source_url="https://example.com/news"
    )

    assert outcome["status"] == "FAILED"
    assert outcome["records_rejected"] == 3
    assert outcome["records_valid"] == 0

    # Ensure staging records were saved with REJECTED status
    staged = db_session.query(StagingRecord).filter(
        StagingRecord.run_id == outcome["run_id"]
    ).all()
    assert len(staged) == 3
    for s in staged:
        assert s.status == "REJECTED"
        assert len(s.validation_errors) > 0
