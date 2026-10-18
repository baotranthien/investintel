"""
Tests for Tiered Fallback Market Data Provider (DNSE -> VNDIRECT -> Local CSV).
"""
import asyncio
from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock

from services.ingestion.base import MarketDataPoint
from services.ingestion.market_data import FallbackMarketDataProvider, MarketDataCsvProvider


def test_fallback_primary_dnse_success():
    """When DNSE succeeds, it should be used directly without fallback."""
    provider = FallbackMarketDataProvider()
    expected_points = [
        MarketDataPoint(
            symbol="FPT",
            observation_date=date(2026, 10, 14),
            close=57100.0,
            open=56500.0,
            high=57500.0,
            low=56200.0,
            volume=7000000.0
        )
    ]
    with patch("services.ingestion.dnse.DnseProvider.fetch_market_data", new_callable=AsyncMock) as mock_dnse:
        mock_dnse.return_value = expected_points
        points = asyncio.run(provider.fetch_market_data("FPT", date(2026, 10, 1), date(2026, 10, 15)))
        assert len(points) == 1
        assert points[0].close == 57100.0


def test_fallback_dnse_fails_vndirect_succeeds():
    """When DNSE raises an exception or returns empty, fallback to VNDIRECT."""
    provider = FallbackMarketDataProvider()
    expected_points = [
        MarketDataPoint(
            symbol="FPT",
            observation_date=date(2026, 10, 14),
            close=57200.0,
            open=56500.0,
            high=57500.0,
            low=56200.0,
            volume=6500000.0
        )
    ]
    with patch("services.ingestion.dnse.DnseProvider.fetch_market_data", new_callable=AsyncMock, side_effect=Exception("DNSE Network Error")):
        with patch("services.ingestion.vndirect.VndirectProvider.fetch_market_data", new_callable=AsyncMock, return_value=expected_points):
            points = asyncio.run(provider.fetch_market_data("FPT", date(2026, 10, 1), date(2026, 10, 15)))
            assert len(points) == 1
            assert points[0].close == 57200.0


def test_fallback_both_fail_csv_succeeds():
    """When both online APIs fail, fallback to local CSV."""
    provider = FallbackMarketDataProvider()
    expected_points = [
        MarketDataPoint(
            symbol="FPT",
            observation_date=date(2026, 9, 30),
            close=56000.0,
            open=55000.0,
            high=56500.0,
            low=55000.0,
            volume=5000000.0
        )
    ]
    with patch("services.ingestion.dnse.DnseProvider.fetch_market_data", new_callable=AsyncMock, side_effect=Exception("DNSE down")):
        with patch("services.ingestion.vndirect.VndirectProvider.fetch_market_data", new_callable=AsyncMock, side_effect=Exception("VND down")):
            with patch("services.ingestion.market_data.MarketDataCsvProvider.fetch_market_data", new_callable=AsyncMock, return_value=expected_points):
                points = asyncio.run(provider.fetch_market_data("FPT", date(2026, 9, 1), date(2026, 10, 1)))
                assert len(points) == 1
                assert points[0].close == 56000.0


def test_ingest_to_database_fallback_tracking(db_session):
    """Verifies that ingest_to_database reports provider_used and fallback_triggered correctly."""
    provider = FallbackMarketDataProvider()
    
    # Simulate DNSE failure and VNDirect success
    with patch("services.ingestion.dnse.DnseProvider.ingest_to_database", side_effect=Exception("DNSE 503")):
        mock_vnd_result = {
            "status": "SUCCESS",
            "symbol": "FPT",
            "records_valid": 5,
            "provider": "VNDIRECT"
        }
        with patch("services.ingestion.vndirect.VndirectProvider.ingest_to_database", new_callable=AsyncMock, return_value=mock_vnd_result):
            res = asyncio.run(provider.ingest_to_database(
                session=db_session,
                symbol="FPT",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 15),
                save_eod_csv=False
            ))
            assert res["status"] == "SUCCESS"
            assert res["provider_used"] == "VNDIRECT"
            assert res["fallback_triggered"] is True
            assert res["fallback_tier"] == 2
