"""
Comprehensive Deterministic Unit and Integration Tests for Multi-Provider Free Data Expansion.
Covers:
1. World Bank Indicators Provider (GDP, CPI, Current Account, Reserves, Unemployment)
2. Free FX Provider (Frankfurter check + open.er-api fallback)
3. GDELT Doc 2.0 News Provider (Rate-pacing, normalization, deduplication, event promotion)
4. BLS Provider (Unauthenticated v1 mode <= 10 years & v2 registered key mode)
5. VNDirect Market Data Provider (kVND scaling, conflict protection, canonical promotion)
6. Single-Provider Isolation (Failure in one provider does not abort others)
"""
import os
import json
import asyncio
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from database.models import (
    Asset,
    Price,
    EventRecord,
    DataLineage,
    DataRun,
    DataQualityReportRecord,
    StagingRecord,
    DataSource,
    MacroSeries,
    MacroObservation,
)
from services.ingestion.world_bank import WorldBankProvider, WORLD_BANK_INDICATORS
from services.ingestion.open_fx import FreeFxProvider
from services.ingestion.gdelt import GDELTNewsProvider
from services.ingestion.bls import BlsProvider
from services.ingestion.vndirect import VndirectProvider, normalize_symbol
from services.ingestion.pipeline import IngestionPipeline
from services.ingestion.scheduler import run_ingestion_cycle
from services.ingestion.http_client import ProviderUnavailableError, RateLimitedError


# =====================================================================
# 1. WORLD BANK INDICATORS PROVIDER TESTS
# =====================================================================

def test_world_bank_indicators_dictionary():
    assert "WB_VNM_GDP" in WORLD_BANK_INDICATORS
    assert "WB_VNM_CPI" in WORLD_BANK_INDICATORS
    assert "WB_VNM_CAB" in WORLD_BANK_INDICATORS
    assert "WB_VNM_RES" in WORLD_BANK_INDICATORS
    assert "WB_VNM_UEM" in WORLD_BANK_INDICATORS
    assert WORLD_BANK_INDICATORS["WB_VNM_GDP"]["indicator"] == "NY.GDP.MKTP.CD"
    assert WORLD_BANK_INDICATORS["WB_VNM_GDP"]["unit"] == "USD"
    assert WORLD_BANK_INDICATORS["WB_VNM_GDP"]["frequency"] == "ANNUAL"


def test_world_bank_payload_parsing():
    provider = WorldBankProvider()
    mock_response = [
        {"page": 1, "pages": 1, "per_page": 50, "total": 3},
        [
            {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"}, "country": {"id": "VN", "value": "Viet Nam"}, "countryiso3code": "VNM", "date": "2023", "value": 433355555555.0, "unit": "", "obs_status": "", "decimal": 0},
            {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"}, "country": {"id": "VN", "value": "Viet Nam"}, "countryiso3code": "VNM", "date": "2022", "value": 408802379058.0, "unit": "", "obs_status": "", "decimal": 0},
            {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP"}, "country": {"id": "VN", "value": "Viet Nam"}, "countryiso3code": "VNM", "date": "2021", "value": None, "unit": "", "obs_status": "", "decimal": 0},
        ]
    ]

    mock_client = MagicMock()
    mock_resp_obj = MagicMock()
    mock_resp_obj.status_code = 200
    mock_resp_obj.content = json.dumps(mock_response).encode("utf-8")
    mock_resp_obj.json.return_value = mock_response
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp_obj)

    with patch("httpx.AsyncClient", return_value=mock_client):
        data = asyncio.run(provider.fetch_macro_series("WB_VNM_GDP"))
        # 2 non-null observations, sorted chronologically ascending
        assert len(data) == 2
        assert data[0].observation_date == date(2022, 12, 31)
        assert data[0].value == 408802379058.0
        assert data[0].unit == "USD"
        assert data[0].frequency == "ANNUAL"
        assert data[1].observation_date == date(2023, 12, 31)
        assert data[1].value == 433355555555.0


def test_world_bank_empty_and_error_handling():
    provider = WorldBankProvider()

    # Empty data list
    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.content = b'[{"page": 1, "pages": 1, "per_page": 50, "total": 0}, []]'
    empty_resp.json.return_value = [{"page": 1, "pages": 1, "per_page": 50, "total": 0}, []]
    mock_client = MagicMock()
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=empty_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = asyncio.run(provider.fetch_macro_series("WB_VNM_CPI"))
        assert res == []

    # HTTP 500 error raises ProviderUnavailableError
    err_resp = MagicMock()
    err_resp.status_code = 500
    err_resp.content = b'Server Error'
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=err_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ProviderUnavailableError):
            asyncio.run(provider.fetch_macro_series("WB_VNM_CPI"))


def test_world_bank_canonical_ingestion_and_idempotency(db_session):
    provider = WorldBankProvider()
    mock_points = [
        {"indicator": {"id": "FP.CPI.TOTL.ZG"}, "date": "2023", "value": 3.25},
        {"indicator": {"id": "FP.CPI.TOTL.ZG"}, "date": "2022", "value": 3.15},
    ]
    mock_response = [{"page": 1}, mock_points]

    mock_client = MagicMock()
    mock_resp_obj = MagicMock()
    mock_resp_obj.status_code = 200
    mock_resp_obj.content = json.dumps(mock_response).encode("utf-8")
    mock_resp_obj.json.return_value = mock_response
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp_obj)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res1 = asyncio.run(provider.ingest_to_database(db_session, "WB_VNM_CPI"))
        assert res1["status"] == "SUCCESS"
        assert res1["records_inserted"] == 2

        # Verify PostgreSQL / SQLite canonical macro observation
        obs = db_session.query(MacroObservation).filter(
            MacroObservation.series_id == "WB_VNM_CPI"
        ).order_by(MacroObservation.observation_date.asc()).all()
        assert len(obs) == 2
        assert obs[0].value == 3.15
        assert obs[1].value == 3.25

        # Verify lineage
        lineage = db_session.query(DataLineage).filter(
            DataLineage.record_table == "macro_observations",
            DataLineage.record_id == str(obs[0].id)
        ).first()
        assert lineage is not None
        assert "WORLD_BANK" in lineage.raw_source

        # Idempotent repeated run: should not duplicate
        res2 = asyncio.run(provider.ingest_to_database(db_session, "WB_VNM_CPI"))
        assert res2["records_inserted"] == 0
        total_obs = db_session.query(MacroObservation).filter(
            MacroObservation.series_id == "WB_VNM_CPI"
        ).count()
        assert total_obs == 2


# =====================================================================
# 2. FREE FOREIGN-EXCHANGE PROVIDER TESTS
# =====================================================================

def test_free_fx_fallback_to_open_er():
    provider = FreeFxProvider()

    # Frankfurter does not have VND, returns without VND
    frank_resp = MagicMock()
    frank_resp.status_code = 200
    frank_resp.json.return_value = {"amount": 1.0, "base": "USD", "date": "2026-10-14", "rates": {"EUR": 0.92, "JPY": 149.5}}

    # open.er-api has VND
    open_er_resp = MagicMock()
    open_er_resp.status_code = 200
    open_er_resp.content = b'{"result":"success"}'
    open_er_resp.json.return_value = {
        "result": "success",
        "provider": "https://www.exchangerate-api.com",
        "time_last_update_unix": 1728950400,
        "base_code": "USD",
        "rates": {"USD": 1.0, "VND": 25450.0}
    }

    mock_client = MagicMock()
    async def mock_get(url, **kwargs):
        if "frankfurter" in url:
            return frank_resp
        return open_er_resp

    mock_client.__aenter__.return_value.get = AsyncMock(side_effect=mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        data = asyncio.run(provider.fetch_macro_series("FX_USD_VND"))
        assert len(data) == 1
        point = data[0]
        assert point.series_id == "FX_USD_VND"
        assert point.value == 25450.0
        assert point.unit == "VND_PER_USD"
        assert point.frequency == "DAILY"


def test_free_fx_canonical_ingestion(db_session):
    provider = FreeFxProvider()
    open_er_resp = MagicMock()
    open_er_resp.status_code = 200
    open_er_resp.content = b'{"result":"success"}'
    open_er_resp.json.return_value = {
        "result": "success",
        "provider": "https://www.exchangerate-api.com",
        "time_last_update_unix": 1728950400,
        "base_code": "USD",
        "rates": {"USD": 1.0, "VND": 25500.0}
    }

    mock_client = MagicMock()
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=open_er_resp)

    with patch.object(provider, "_try_frankfurter_rate", return_value=None):
        with patch("httpx.AsyncClient", return_value=mock_client):
            res = asyncio.run(provider.ingest_to_database(db_session, "FX_USD_VND"))
            assert res["status"] == "SUCCESS"
            assert res["records_inserted"] == 1

            obs = db_session.query(MacroObservation).filter(
                MacroObservation.series_id == "FX_USD_VND"
            ).first()
            assert obs is not None
            assert obs.value == 25500.0


# =====================================================================
# 3. GDELT NEWS PROVIDER TESTS
# =====================================================================

def test_gdelt_article_parsing_and_seendate():
    provider = GDELTNewsProvider()
    mock_payload = {
        "articles": [
            {
                "url": "https://en.vietnamplus.vn/vietnam-stock-market-news-article1.vnp",
                "title": "Vietnam stock market hits new monthly milestone",
                "seendate": "20241014T153000Z",
                "domain": "vietnamplus.vn"
            },
            {
                "url": "https://vir.com.vn/fdi-inflows-boost-equities-article2.html",
                "title": "FDI inflows boost Vietnamese equities",
                "seendate": "invalid_date",
                "domain": "vir.com.vn"
            }
        ]
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = json.dumps(mock_payload).encode("utf-8")
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

    with patch.object(provider, "_pace_request", new_callable=AsyncMock):
        with patch("httpx.AsyncClient", return_value=mock_client):
            articles = asyncio.run(provider.search_articles(query="vietnam market", max_records=5))
            assert len(articles) == 2
            assert articles[0]["title"] == "Vietnam stock market hits new monthly milestone"
            assert articles[0]["published_at"] == "2024-10-14T15:30:00+00:00"
            assert articles[0]["sourceName"] == "GDELT (vietnamplus.vn)"
            # Invalid date does not crash, published_at is None
            assert articles[1]["published_at"] is None


def test_gdelt_handles_rate_limit_gracefully():
    provider = GDELTNewsProvider()
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.content = b"Too Many Requests"
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

    with patch.object(provider, "_pace_request", new_callable=AsyncMock):
        with patch("httpx.AsyncClient", return_value=mock_client):
            articles = asyncio.run(provider.search_articles(query="vietnam"))
            # Must return empty list safely without raising uncaught exception
            assert articles == []


def test_gdelt_canonical_event_ingestion(db_session):
    provider = GDELTNewsProvider()
    articles = [
        {
            "id": "https://test.news/gdelt1",
            "title": "Vietnam Tech Export Surge",
            "url": "https://test.news/gdelt1",
            "published_at": "2026-10-14T08:00:00+00:00",
            "snippet": "[test.news] Vietnam Tech Export Surge",
            "sourceName": "GDELT (test.news)",
            "event_type": "Market",
            "materiality": "INFORMATIONAL",
            "severity": 40.0,
            "sentiment": "POSITIVE",
        }
    ]

    with patch.object(provider, "search_articles", new_callable=AsyncMock, return_value=articles):
        res = asyncio.run(provider.ingest_to_database(db_session))
        assert res["status"] == "SUCCESS"
        assert res["records_valid"] == 1

        # Verify EventRecord
        event = db_session.query(EventRecord).filter(
            EventRecord.title == "Vietnam Tech Export Surge"
        ).first()
        assert event is not None
        assert event.source_id is not None or "GDELT" in str(event.sources)


# =====================================================================
# 4. BLS PUBLIC ACCESS MODE TESTS
# =====================================================================

def test_bls_unauthenticated_mode_10_year_clamp():
    # Ensure no API key set
    with patch.dict(os.environ, {}, clear=True):
        provider = BlsProvider()
        assert provider.mode == "V1_UNAUTHENTICATED"
        assert "v1" in provider.base_url

        mock_payload_captured = {}
        async def mock_post(url, payload, **kwargs):
            mock_payload_captured.update(payload)
            mock_r = MagicMock()
            mock_r.json.return_value = {
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [{
                        "seriesID": "CUUR0000SA0",
                        "data": [{"year": "2024", "period": "M08", "value": "314.796"}]
                    }]
                }
            }
            return mock_r

        with patch("services.ingestion.bls.shared_http_client.post_json", side_effect=mock_post):
            data = asyncio.run(provider.fetch_macro_series("CUUR0000SA0", start_year="2000", end_year="2024"))
            assert len(data) == 1
            # Verified clamp to 10-year window (2024 - 9 = 2015)
            assert mock_payload_captured["startyear"] == "2015"
            assert mock_payload_captured["endyear"] == "2024"
            assert "registrationkey" not in mock_payload_captured


def test_bls_registered_mode_with_key():
    with patch.dict(os.environ, {"BLS_API_KEY": "fake_bls_key"}):
        provider = BlsProvider()
        assert provider.mode == "V2_REGISTERED"
        assert "v2" in provider.base_url

        mock_payload_captured = {}
        async def mock_post(url, payload, **kwargs):
            mock_payload_captured.update(payload)
            mock_r = MagicMock()
            mock_r.json.return_value = {
                "status": "REQUEST_SUCCEEDED",
                "Results": {"series": [{"seriesID": "CUUR0000SA0", "data": []}]}
            }
            return mock_r

        with patch("services.ingestion.bls.shared_http_client.post_json", side_effect=mock_post):
            asyncio.run(provider.fetch_macro_series("CUUR0000SA0", start_year="2010", end_year="2024"))
            assert mock_payload_captured["registrationkey"] == "fake_bls_key"


# =====================================================================
# 5. VNDIRECT STOCK PROVIDER TESTS
# =====================================================================

def test_vndirect_symbol_normalization():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol("  vcb ") == "VCB"
    assert normalize_symbol("mbb-vn") == "MBBVN"


def test_vndirect_payload_scaling_and_parsing():
    provider = VndirectProvider()
    mock_payload = {
        "data": [
            {
                "code": "FPT",
                "date": "2024-10-10",
                "basicPrice": 134.0,
                "open": 134.5,
                "high": 135.0,
                "low": 133.8,
                "close": 134.0,
                "nmVolume": 2500000.0
            }
        ]
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = json.dumps(mock_payload).encode("utf-8")
    mock_resp.json.return_value = mock_payload
    mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        bars = asyncio.run(provider.fetch_market_data("FPT", date(2024, 10, 1), date(2024, 10, 15)))
        assert len(bars) == 1
        b = bars[0]
        assert b.symbol == "FPT"
        assert b.observation_date == date(2024, 10, 10)
        # 134.0 * 1000.0 = 134000.0 VND
        assert b.close == 134000.0
        assert b.open == 134500.0
        assert b.high == 135000.0
        assert b.low == 133800.0
        assert b.volume == 2500000.0


def test_vndirect_market_bar_conflict_protection(db_session):
    provider = VndirectProvider()
    # First insert a canonical price for FPT on 2024-10-10
    asset = db_session.query(Asset).filter(Asset.symbol == "FPT").first()
    if not asset:
        asset = Asset(symbol="FPT", name="FPT Corporation", asset_type="STOCK", exchange="HOSE")
        db_session.add(asset)
        db_session.flush()

    obs_d = date(2024, 10, 10)
    existing_price = db_session.query(Price).filter(
        Price.asset_id == asset.id,
        Price.observation_date == obs_d
    ).first()
    if not existing_price:
        existing_price = Price(
            asset_id=asset.id,
            observation_date=obs_d,
            raw_close=130000.0,
            adjusted_close=130000.0,
            source="DNSE",
            status="VALID"
        )
        db_session.add(existing_price)
    else:
        existing_price.raw_close = 130000.0
        existing_price.adjusted_close = 130000.0
        existing_price.source = "DNSE"
        existing_price.status = "VALID"
    db_session.commit()

    # Now attempt to ingest conflicting price (134,000 VND) from VNDirect on same date
    from services.ingestion.base import MarketDataPoint
    mock_bars = [
        MarketDataPoint(
            symbol="FPT",
            observation_date=obs_d,
            close=134000.0,
            open=134500.0,
            high=135000.0,
            low=133800.0,
            volume=2000000.0
        )
    ]

    with patch.object(provider, "fetch_market_data", new_callable=AsyncMock, return_value=mock_bars):
        res = asyncio.run(provider.ingest_to_database(db_session, "FPT", obs_d, obs_d))
        # Conflicting bar should be rejected, existing canonical price preserved
        assert res["records_rejected"] == 1
        refreshed_price = db_session.query(Price).filter(
            Price.asset_id == asset.id,
            Price.observation_date == obs_d
        ).first()
        assert refreshed_price.raw_close == 130000.0  # Preserved original


# =====================================================================
# 6. PROVIDER ISOLATION IN SCHEDULER
# =====================================================================

def test_scheduler_provider_isolation(db_session):
    """
    Verifies that if FRED is missing credentials and World Bank fails with HTTP 500,
    the remaining providers (e.g. Free FX, CSV) still execute and are not blocked.
    """
    with patch.dict(os.environ, {
        "FRED_API_KEY": "",  # Missing key
        "ENABLE_FRED_CSV_FALLBACK": "false",  # Test credential-blocked state
        "ENABLE_BLS_INGESTION": "false",
        "ENABLE_WORLDBANK_INGESTION": "true",
        "ENABLE_FX_INGESTION": "true",
        "ENABLE_VNDIRECT_INGESTION": "false",
        "ENABLE_LOTUSMARKET_INGESTION": "false",
        "ENABLE_VIETCAP_INGESTION": "false",
    }):
        # Mock World Bank to raise exception
        async def mock_wb_fetch(*args, **kwargs):
            raise ProviderUnavailableError("World Bank cluster down")

        # Mock FX to succeed
        from services.ingestion.base import MacroDataPoint
        async def mock_fx_fetch(*args, **kwargs):
            return [MacroDataPoint(
                series_id="FX_USD_VND",
                observation_date=date.today(),
                value=25400.0,
                unit="VND_PER_USD",
                frequency="DAILY"
            )]

        # Mock NSO to avoid real network calls in this isolation test.
        # NSO_VIETNAM is now a real functional provider (NsoProvider), NOT BLOCKED.
        async def mock_nso_fetch(*args, **kwargs):
            return []  # Empty list -> INSUFFICIENT_DATA

        with patch("services.ingestion.scheduler.WorldBankProvider.fetch_macro_series", side_effect=mock_wb_fetch):
            with patch("services.ingestion.scheduler.FreeFxProvider.fetch_macro_series", side_effect=mock_fx_fetch):
                with patch("services.ingestion.scheduler.NsoProvider.fetch_macro_series", side_effect=mock_nso_fetch):
                    results = asyncio.run(run_ingestion_cycle(session_factory=lambda: db_session))
                    statuses = {r.get("provider"): r.get("status") for r in results}

                    # FRED is recorded as BLOCKED_MISSING_CREDENTIAL when fallback is disabled
                    assert statuses.get("FRED") == "BLOCKED_MISSING_CREDENTIAL"

                    # World Bank is recorded as FAILURE
                    assert statuses.get("WORLD_BANK") == "FAILURE"

                    # Free FX completed successfully
                    assert statuses.get("OPEN_EXCHANGE_RATES") == "SUCCESS"

                    # NSO_VIETNAM is now a real functional provider (NsoProvider) — NOT BLOCKED_UNSUPPORTED.
                    # With empty mock data it returns INSUFFICIENT_DATA. Check it is a live-provider status.
                    nso_status = statuses.get("NSO_VIETNAM")
                    assert nso_status is not None, "NSO_VIETNAM should produce a run result"
                    assert nso_status != "BLOCKED_UNSUPPORTED_PUBLIC_INTERFACE", (
                        "NSO_VIETNAM is a functional provider and must not report as unsupported"
                    )

                    # SBV still has no machine-readable public API
                    assert statuses.get("SBV") == "BLOCKED_UNSUPPORTED_PUBLIC_INTERFACE"


def test_scheduler_fred_csv_fallback_when_enabled(db_session):
    """
    Verifies that when FRED_API_KEY is empty but ENABLE_FRED_CSV_FALLBACK is true,
    FRED/DGS10 successfully uses the public CSV fallback and avoids BLOCKED_MISSING_CREDENTIAL.
    """
    from services.ingestion.base import MacroDataPoint
    mock_point = MacroDataPoint(
        series_id="DGS10",
        observation_date=date(2026, 10, 15),
        release_date=date(2026, 10, 15),
        value=5.10,
        unit="PERCENT",
        frequency="DAILY"
    )

    with patch.dict(os.environ, {
        "FRED_API_KEY": "",
        "ENABLE_FRED_CSV_FALLBACK": "true",
        "ENABLE_BLS_INGESTION": "false",
        "ENABLE_WORLDBANK_INGESTION": "false",
        "ENABLE_FX_INGESTION": "false",
        "ENABLE_NSO_INGESTION": "false",
        "ENABLE_VNDIRECT_INGESTION": "false",
        "ENABLE_LOTUSMARKET_INGESTION": "false",
        "ENABLE_VIETCAP_INGESTION": "false",
    }):
        with patch("services.ingestion.scheduler.FredProvider.fetch_macro_series", new_callable=AsyncMock, return_value=[mock_point]):
            results = asyncio.run(run_ingestion_cycle(session_factory=lambda: db_session))
            statuses = {r.get("provider"): r.get("status") for r in results}
            # FRED is NOT blocked; it succeeds or processes via fallback
            assert statuses.get("FRED") in ("SUCCESS", "IDEMPOTENT_UNCHANGED", "PARTIAL")
            assert statuses.get("FRED") != "BLOCKED_MISSING_CREDENTIAL"
