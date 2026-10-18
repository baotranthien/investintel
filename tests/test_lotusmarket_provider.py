"""
Unit and Integration Tests for LotusMarketProvider.

All automated tests use deterministic mocking so they run offline, fast,
and reliably without depending on external network availability.
"""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest

from database.models import Asset, DataSource, DataRun, DataLineage, EventRecord, Price, StagingRecord
from services.ingestion.lotusmarket import (
    LotusMarketProvider,
    _parse_pipe_vol,
    _parse_cafef_date,
    _clean_html_anchor,
    normalize_symbol,
)
from services.ingestion.base import MarketDataPoint
from services.ingestion.http_client import ProviderUnavailableError, RateLimitedError
from services.ingestion.reconciliation import MarketDataReconciliationEngine
from services.events.engine import EventEngine


# ------------------------------------------------------------------------------
# 1. Helper function tests
# ------------------------------------------------------------------------------
def test_normalize_symbol():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol("  hpg  ") == "HPG"
    assert normalize_symbol("vn-index") == "VNINDEX"
    assert normalize_symbol("") == ""


def test_parse_pipe_vol():
    assert _parse_pipe_vol("58.2|120000") == 120000
    assert _parse_pipe_vol("20.5|50000|extra") == 50000
    assert _parse_pipe_vol("invalid") == 0
    assert _parse_pipe_vol("") == 0


def test_parse_cafef_date():
    # 1782147600000 ms -> 2026-06-23 in UTC+7
    dt = _parse_cafef_date("/Date(1782147600000)/")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 6
    assert dt.day == 23

    assert _parse_cafef_date("") is None
    assert _parse_cafef_date("invalid") is None


def test_clean_html_anchor():
    assert _clean_html_anchor("<a href='...'>Nguyen Van A</a>") == "Nguyen Van A"
    assert _clean_html_anchor("Tran Thi B") == "Tran Thi B"
    assert _clean_html_anchor("") == ""


# ------------------------------------------------------------------------------
# 2. VPS Quote parsing & error handling
# ------------------------------------------------------------------------------
MOCK_VPS_RESPONSE = [
    {
        "sym": "FPT",
        "lastPrice": 58.2,
        "r": 58.0,
        "openPrice": 58.7,
        "highPrice": 58.7,
        "lowPrice": 57.9,
        "lot": 373330,
        "c": 62.0,
        "f": 54.0,
        "fBVol": 139071,
        "fSVolume": 56850,
        "g1": "58.1|15000",
        "g2": "58.3|22000",
    },
    {
        "sym": "ACB",
        "lastPrice": 20.6,
        "r": 20.6,
        "openPrice": 20.7,
        "highPrice": 20.75,
        "lowPrice": 20.55,
        "lot": 516030,
        "c": 22.0,
        "f": 19.2,
        "fBVol": 219460,
        "fSVolume": 346202,
        "g1": "20.55|35000",
        "g2": "20.65|41000",
    },
]


def test_vps_quotes_parsing():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_VPS_RESPONSE
        mock_get.return_value = mock_resp

        quotes = provider.fetch_quotes(["FPT", "ACB"])
        assert len(quotes) == 2

        fpt = quotes[0]
        assert fpt["symbol"] == "FPT"
        assert fpt["close"] == 58200.0  # 58.2 * 1000 VND
        assert fpt["ref_price"] == 58000.0
        assert fpt["open"] == 58700.0
        assert fpt["high"] == 58700.0
        assert fpt["low"] == 57900.0
        assert fpt["volume"] == 373330.0
        assert fpt["foreign_buy_vol"] == 139071
        assert fpt["foreign_sell_vol"] == 56850
        assert fpt["foreign_net_vol"] == 139071 - 56850
        assert fpt["bid"] == 58100.0
        assert fpt["bid_vol"] == 15000
        assert fpt["ask"] == 58300.0
        assert fpt["ask_vol"] == 22000


def test_vps_empty_and_invalid():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        quotes = provider.fetch_quotes(["INVALID999"])
        assert quotes == []


def test_vps_rate_limiting():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        with pytest.raises(RateLimitedError):
            provider.fetch_quotes(["FPT"])


def test_vps_server_error():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_get.return_value = mock_resp

        with pytest.raises(ProviderUnavailableError):
            provider.fetch_quotes(["FPT"])


# ------------------------------------------------------------------------------
# 3. Entrade Historical OHLCV normalization & consistency
# ------------------------------------------------------------------------------
MOCK_ENTRADE_RESPONSE = {
    "t": [1782147600, 1782234000],  # 2026-06-23, 2026-06-24
    "o": [57.0, 58.0],
    "h": [58.5, 59.0],
    "l": [56.5, 57.5],
    "c": [58.0, 58.5],
    "v": [2500000, 3100000],
}


def test_entrade_ohlcv_normalization():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_ENTRADE_RESPONSE
        mock_get.return_value = mock_resp

        start_d = date(2026, 6, 20)
        end_d = date(2026, 6, 25)
        candles = provider.fetch_ohlcv("FPT", start_d, end_d)
        assert len(candles) == 2

        c1 = candles[0]
        assert c1["symbol"] == "FPT"
        assert c1["observation_date"] == date(2026, 6, 23)
        assert c1["open"] == 57000.0
        assert c1["high"] == 58500.0
        assert c1["low"] == 56500.0
        assert c1["close"] == 58000.0
        assert c1["volume"] == 2500000.0

        # Verify OHLC consistency
        for c in candles:
            assert c["high"] >= c["low"]
            assert c["high"] >= c["open"]
            assert c["low"] <= c["open"]
            assert c["volume"] >= 0


def test_entrade_inconsistent_candle_rejected():
    provider = LotusMarketProvider()
    # Inconsistent candle where high < low
    bad_resp = {
        "t": [1782147600],
        "o": [57.0],
        "h": [55.0],  # high is 55.0
        "l": [58.0],  # low is 58.0 (impossible!)
        "c": [56.0],
        "v": [1000],
    }
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bad_resp
        mock_get.return_value = mock_resp

        candles = provider.fetch_ohlcv("FPT", date(2026, 6, 20), date(2026, 6, 25))
        assert len(candles) == 0  # rejected by quality check


# ------------------------------------------------------------------------------
# 4. CafeF Insider Shareholder Transactions
# ------------------------------------------------------------------------------
MOCK_CAFEF_RESPONSE = {
    "Success": True,
    "Data": {
        "TotalCount": 2,
        "Data": [
            {
                "TransactionMan": "<a href='...'>Nguyen Van A</a>",
                "TransactionManPosition": "Pho Tong Giam Doc",
                "PlanBeginDate": "/Date(1782147600000)/",
                "PlanEndDate": "/Date(1782234000000)/",
                "PublishedDate": "/Date(1782147600000)/",
                "PlanBuyVolume": 200000,
                "PlanSellVolume": 0,
                "RealBuyVolume": 200000,
                "RealSellVolume": 0,
                "VolumeAfterTransaction": 1500000,
                "TyLeSoHuu": 0.05,
            }
        ]
    }
}


def test_cafef_insider_transactions():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_CAFEF_RESPONSE
        mock_get.return_value = mock_resp

        events = provider.fetch_insider_transactions("FPT")
        assert len(events) == 1
        ev = events[0]
        assert "Nguyen Van A" in ev["title"]
        assert "BUY 200,000 CP" in ev["title"]
        assert ev["event_type"] == "CorporateAction"
        assert ev["sentiment"] == "POSITIVE"
        assert ev["materiality"] == "RELEVANT"
        assert ev["sourceName"] == "LotusMarket / CafeF"


# ------------------------------------------------------------------------------
# 5. KBS Fundamentals Graceful Degradation
# ------------------------------------------------------------------------------
def test_kbs_fundamentals_handles_400_gracefully():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "<HTML>400 Bad Request</HTML>"
        mock_get.return_value = mock_resp

        # Must return None safely without raising or fabricating fake metrics
        fund = provider.fetch_fundamentals("FPT")
        assert fund is None


def test_kbs_fundamentals_success():
    provider = LotusMarketProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "TradingDate": "2026-10-16",
                "MarketCapital": 120000000000000,
                "PE": 18.5,
                "PB": 3.8,
                "EPS": 4200,
                "BVPS": 21000,
                "Beta": 1.15,
                "Yield": 2.5,
            }
        ]
        mock_get.return_value = mock_resp

        fund = provider.fetch_fundamentals("FPT")
        assert fund is not None
        assert fund["pe"] == 18.5
        assert fund["pb"] == 3.8
        assert fund["eps"] == 4200.0


# ------------------------------------------------------------------------------
# 6. Database Pipeline Ingestion, Lineage, and Idempotency
# ------------------------------------------------------------------------------
def test_pipeline_ingestion_and_idempotency(db_session):
    provider = LotusMarketProvider()

    # Create dummy source
    ds = db_session.query(DataSource).filter(DataSource.name == "LOTUSMARKET").first()
    if not ds:
        ds = DataSource(
            name="LOTUSMARKET",
            provider="LotusMarket",
            source_type="API",
            active=True
        )
        db_session.add(ds)
        db_session.flush()

    mock_candles = [
        {
            "symbol": "FPT",
            "observation_date": date(2028, 6, 23),
            "open": 57000.0,
            "high": 58500.0,
            "low": 56500.0,
            "close": 58000.0,
            "adjusted_close": 58000.0,
            "volume": 2500000.0,
        }
    ]

    with patch.object(provider, "fetch_ohlcv", return_value=mock_candles):
        # First ingestion -> promotes to Price
        res1 = provider.ingest_to_database(
            db_session, "FPT", date(2028, 6, 23), date(2028, 6, 23), source_id=ds.id
        )
        assert res1["status"] == "SUCCESS"
        assert res1["records_valid"] == 1
        assert res1["records_rejected"] == 0

        price_row = db_session.query(Price).join(Asset).filter(
            Asset.symbol == "FPT",
            Price.observation_date == date(2028, 6, 23)
        ).first()
        assert price_row is not None
        assert price_row.raw_close == 58000.0

        # StagingRecord created
        staged = db_session.query(StagingRecord).filter(
            StagingRecord.provider == "LOTUSMARKET"
        ).first()
        assert staged is not None
        assert staged.status == "PROMOTED"

        # Second ingestion with identical data -> idempotent (records_valid=1, records_rejected=0)
        res2 = provider.ingest_to_database(
            db_session, "FPT", date(2028, 6, 23), date(2028, 6, 23), source_id=ds.id
        )
        assert res2["records_valid"] == 1
        assert res2["records_rejected"] == 0

        # Third ingestion with CONFLICTING data -> preserves canonical, rejects conflict
        conflicting_candle = [
            {
                "symbol": "FPT",
                "observation_date": date(2028, 6, 23),
                "open": 57000.0,
                "high": 58500.0,
                "low": 56500.0,
                "close": 99999.0,  # CONFLICT
                "adjusted_close": 99999.0,
                "volume": 2500000.0,
            }
        ]
        with patch.object(provider, "fetch_ohlcv", return_value=conflicting_candle):
            res3 = provider.ingest_to_database(
                db_session, "FPT", date(2028, 6, 23), date(2028, 6, 23), source_id=ds.id
            )
            assert res3["records_rejected"] == 1

            # Assert original price 58000.0 is untouched
            db_session.refresh(price_row)
            assert price_row.raw_close == 58000.0


# ------------------------------------------------------------------------------
# 7. Reconciliation against DNSE
# ------------------------------------------------------------------------------
def test_reconciliation_lotusmarket_against_dnse():
    recon_engine = MarketDataReconciliationEngine()

    candles_lotus = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 6, 23), close=58000.0, volume=2500000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 6, 24), close=58500.0, volume=3100000.0),
    ]
    candles_dnse = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 6, 23), close=58000.0, volume=2500000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 6, 24), close=58500.0, volume=3100000.0),
    ]

    report = recon_engine.reconcile_candles(
        symbol="FPT",
        candles_a=candles_lotus,
        candles_b=candles_dnse,
        provider_a_name="LOTUSMARKET",
        provider_b_name="DNSE"
    )

    assert report.status == "CONSISTENT"
    assert report.matching_dates_count == 2
    assert report.major_disagreement_count == 0
    assert report.max_close_diff_pct == 0.0
