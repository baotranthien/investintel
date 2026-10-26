"""
Unit and Integration Tests for VietcapProvider.
All automated tests use deterministic mocking so they run offline, fast,
and reliably without depending on external network availability.
"""
from datetime import date, datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

from database.models import Asset, DataSource, DataLineage, FinancialStatement, NormalizedIncome, Price
from services.ingestion.vietcap import VietcapProvider, normalize_symbol
from services.ingestion.base import MarketDataPoint
from services.ingestion.http_client import ProviderUnavailableError, RateLimitedError


# ------------------------------------------------------------------------------
# 1. Helper function tests
# ------------------------------------------------------------------------------
def test_vietcap_symbol_normalization():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol("  vcb  ") == "VCB"
    assert normalize_symbol("^vnindex") == "VNINDEX"
    assert normalize_symbol("^VN30") == "VN30"
    assert normalize_symbol("") == ""


# ------------------------------------------------------------------------------
# 2. OHLCV Candle Parsing & Scaling (Full VND)
# ------------------------------------------------------------------------------
MOCK_GAP_CHART_RESPONSE = [
    {
        "t": ["1792713600", "1792972800"],
        "o": [56800, 56500],
        "h": [57200, 56800],
        "l": [56200, 55900],
        "c": [57000, 56000],
        "v": [7090600, 10104800],
    }
]


def test_vietcap_ohlcv_parsing():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_GAP_CHART_RESPONSE

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        bars = provider.fetch_ohlcv("FPT", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        assert len(bars) == 2
        assert bars[0]["symbol"] == "FPT"
        assert bars[0]["close"] == 57000.0
        assert bars[0]["open"] == 56800.0
        assert bars[0]["high"] == 57200.0
        assert bars[0]["low"] == 56200.0
        assert bars[0]["volume"] == 7090600.0
        assert bars[1]["close"] == 56000.0


def test_vietcap_ohlcv_empty_unknown_symbol():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        bars = provider.fetch_ohlcv("NONEXISTENT", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        assert bars == []


# ------------------------------------------------------------------------------
# 3. Real-time Quotes & Intraday Board
# ------------------------------------------------------------------------------
MOCK_BOARD_RESPONSE = [
    {
        "listingInfo": {
            "symbol": "FPT",
            "ceiling": 60500,
            "floor": 52700,
            "refPrice": 56600,
        },
        "matchPrice": {
            "matchPrice": 56000,
            "accumulatedVolume": 10104800,
            "accumulatedValue": 568.5,  # Million VND -> 568,500,000 VND
            "openPrice": 56500,
            "highPrice": 56800,
            "lowPrice": 55900,
            "avgMatchPrice": 56260,
            "foreignBuyValue": 125000000,
            "foreignSellValue": 80000000,
        },
    }
]


def test_vietcap_fetch_quotes():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_BOARD_RESPONSE

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        quotes = provider.fetch_quotes(["FPT"])
        assert len(quotes) == 1
        q = quotes[0]
        assert q["symbol"] == "FPT"
        assert q["close"] == 56000.0
        assert q["traded_value"] == 568_500_000.0
        assert q["foreign_net_value"] == 45_000_000.0


# ------------------------------------------------------------------------------
# 4. Audited Financial Statements with publicDate
# ------------------------------------------------------------------------------
MOCK_FINANCIAL_STATEMENTS = {
    "successful": True,
    "data": {
        "quarters": [
            {
                "organCode": "FPT",
                "ticker": "FPT",
                "yearReport": 2026,
                "lengthReport": 2,
                "publicDate": "2026-08-22T00:00:00",
                "isa1": 15000000000000.0,
                "isa3": 14950000000000.0,
                "isa4": -9000000000000.0,
                "isa5": 5950000000000.0,
                "isa11": 2500000000000.0,
                "isa16": 2600000000000.0,
                "isa20": 2150000000000.0,
                "isa22": 1850000000000.0,
                "isa23": 1450.0,
            }
        ],
        "years": [],
    }
}


def test_vietcap_fetch_financial_statements():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_FINANCIAL_STATEMENTS

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        data = provider.fetch_financial_statements("FPT", "INCOME_STATEMENT")
        assert len(data["quarters"]) == 1
        q = data["quarters"][0]
        assert q["yearReport"] == 2026
        assert q["lengthReport"] == 2
        assert q["publicDate"] == "2026-08-22T00:00:00"
        assert q["isa3"] == 14950000000000.0


# ------------------------------------------------------------------------------
# 5. Financial Statements Ingestion & Lineage to Database
# ------------------------------------------------------------------------------
def test_vietcap_ingest_fundamentals_to_db(db_session):
    provider = VietcapProvider()

    # Ensure asset exists
    asset = db_session.query(Asset).filter(Asset.symbol == "FPT").first()
    if not asset:
        asset = Asset(symbol="FPT", name="FPT Corp", asset_type="STOCK", exchange="HOSE", status="ACTIVE")
        db_session.add(asset)
        db_session.commit()

    # Mock fetch_financial_statements to return controlled mock data
    with patch.object(provider, "fetch_financial_statements", return_value=MOCK_FINANCIAL_STATEMENTS["data"]):
        result = provider.ingest_fundamentals(db_session, "FPT", periods_limit=4)
        assert result["status"] == "SUCCESS"
        assert result["symbol"] == "FPT"
        assert result["statements_created"] + result["statements_existing"] >= 1

        # Check that statement row exists in DB
        stmt = db_session.query(FinancialStatement).filter(
            FinancialStatement.symbol == "FPT",
            FinancialStatement.fiscal_year == 2026,
            FinancialStatement.fiscal_quarter == 2,
        ).first()
        assert stmt is not None
        assert stmt.source_name == "VIETCAP_IQ"
        assert stmt.unit_scale == "BILLION_VND"
        assert stmt.publication_date == date(2026, 8, 22)

        # Check normalized income
        norm = db_session.query(NormalizedIncome).filter(NormalizedIncome.statement_id == stmt.id).first()
        assert norm is not None
        assert round(norm.revenue, 1) == 14950.0  # 14.95 trillion / 1e9 = 14,950 billion VND
        assert round(norm.net_income, 1) == 2150.0

        # Check DataLineage checksum and availability
        lineage = db_session.query(DataLineage).filter(
            DataLineage.record_table == "financial_statements",
            DataLineage.record_id == str(stmt.id),
        ).first()
        assert lineage is not None
        assert lineage.checksum is not None
        assert lineage.retrieved_at is not None


# ------------------------------------------------------------------------------
# 6. Rate Limit and Error Resilience
# ------------------------------------------------------------------------------
def test_vietcap_rate_limit_error():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        with pytest.raises(RateLimitedError):
            provider.fetch_ohlcv("FPT", start_date=date(2026, 1, 1), end_date=date(2026, 1, 5))


def test_vietcap_provider_unavailable_error():
    provider = VietcapProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.text = "Bad Gateway"

    with patch.object(provider, "_get_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_getter.return_value = mock_client

        with pytest.raises(ProviderUnavailableError):
            provider.fetch_ohlcv("FPT", start_date=date(2026, 1, 1), end_date=date(2026, 1, 5))
