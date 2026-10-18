from datetime import date
from uuid import uuid4

from database.models import (
    Asset,
    DataLineage,
    DataSource,
    MacroObservation,
    MacroSeries,
    Price,
)
from services.ingestion.base import MacroDataPoint
from services.ingestion.pipeline import IngestionPipeline


def test_macro_ingestion_is_idempotent_and_versions_revisions(db_session):
    source = db_session.query(DataSource).filter(DataSource.name == "FRED").first()
    if source is None:
        source = DataSource(name="FRED", provider="Federal Reserve", active=True)
        db_session.add(source)
    db_session.flush()
    series_id = f"TEST_RATE_{uuid4().hex[:8]}"
    db_session.add(MacroSeries(
        id=series_id, name="Test rate", provider="FRED", frequency="DAILY",
        unit="PERCENT", source_id=source.id,
    ))
    db_session.commit()

    pipeline = IngestionPipeline(db_session)
    original = MacroDataPoint(
        series_id=series_id, observation_date=date(2025, 1, 2),
        release_date=date(2025, 1, 3), value=4.25, unit="PERCENT", frequency="DAILY",
    )
    first = pipeline.ingest_macro_series("FRED", series_id, [original], "https://fred.example", source.id)
    repeat = pipeline.ingest_macro_series("FRED", series_id, [original], "https://fred.example", source.id)

    revised = original.model_copy(update={"release_date": date(2025, 1, 10), "value": 4.5})
    revision = pipeline.ingest_macro_series("FRED", series_id, [revised], "https://fred.example", source.id)

    observations = db_session.query(MacroObservation).filter(
        MacroObservation.series_id == series_id,
    ).order_by(MacroObservation.version).all()
    assert first["records_inserted"] == 1
    assert repeat["records_inserted"] == 0
    assert revision["records_updated"] == 1
    assert [(row.version, row.value) for row in observations] == [(1, 4.25), (2, 4.5)]
    assert observations[1].supersedes_id == observations[0].id
    assert observations[1].published_at.date() == date(2025, 1, 10)
    assert db_session.query(DataLineage).filter(
        DataLineage.record_table == "macro_observations",
        DataLineage.record_id == str(observations[1].id),
    ).count() == 1


def test_market_conflict_does_not_overwrite_canonical_history(db_session):
    source = db_session.query(DataSource).filter(DataSource.name == "HOSE_CSV").first()
    if source is None:
        source = DataSource(name="HOSE_CSV", provider="Verified local file", active=True)
        db_session.add(source)
    symbol = f"IT{uuid4().hex[:8].upper()}"
    asset = Asset(symbol=symbol, name="Ingestion test", asset_type="STOCK", exchange="HOSE")
    db_session.add_all([source, asset])
    db_session.commit()

    pipeline = IngestionPipeline(db_session)
    baseline = {
        "observation_date": date(2025, 2, 3), "open": 10.0, "high": 12.0,
        "low": 9.0, "close": 11.0, "adjusted_close": 11.0, "volume": 100.0,
    }
    pipeline.ingest_market_data("HOSE_CSV", asset.symbol, "HOSE", [baseline], "local://test.csv", source.id)
    conflicting = {**baseline, "close": 99.0, "adjusted_close": 99.0}
    result = pipeline.ingest_market_data(
        "HOSE_CSV", asset.symbol, "HOSE", [conflicting], "local://test.csv", source.id
    )

    canonical = db_session.query(Price).filter(Price.asset_id == asset.id).one()
    assert canonical.raw_close == 11.0
    assert result["status"] == "FAILED"
    assert result["records_rejected"] == 1


def test_empty_market_ingestion_reports_insufficient_data(db_session):
    result = IngestionPipeline(db_session).ingest_market_data(
        "HOSE_CSV", "EMPTY_TEST", "HOSE", [], "local://missing.csv"
    )

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["records_received"] == 0