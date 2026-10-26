"""
Unit and Integration Tests for DataCoreProvider.
Tests unauthenticated catalog preview, credential gating, authenticated queries,
and error handling. All tests use deterministic mocking for offline, reliable execution.
"""
from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from services.ingestion.datacore import DataCoreProvider, normalize_symbol
from services.ingestion.http_client import ProviderUnavailableError, RateLimitedError


def test_datacore_symbol_normalization():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol("  vcb  ") == "VCB"
    assert normalize_symbol("^vnindex") == "VNINDEX"
    assert normalize_symbol("") == ""


def test_datacore_unauthenticated_state():
    provider = DataCoreProvider(api_key="")
    assert not provider.is_authenticated

    # Full queries must be safely blocked and report missing credential
    res = provider.fetch_data("dataset_historical_price")
    assert res["status"] == "BLOCKED_MISSING_CREDENTIAL"
    assert "X_API_KEY" in res["reason"]


def test_datacore_preview_success():
    provider = DataCoreProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": True,
        "data": {
            "fields": ["date", "symbol", "close_price"],
            "dataDetail": [
                ["2026-10-23", "FPT", 56000],
                ["2026-10-24", "FPT", 56200],
            ],
        },
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = provider.preview_dataset("dataset_historical_price")
        assert res["dataset_code"] == "dataset_historical_price"
        assert res["num_preview_rows"] == 2
        assert "close_price" in res["fields"]


def test_datacore_preview_rate_limit():
    provider = DataCoreProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate Limit Exceeded"

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(RateLimitedError):
            provider.preview_dataset("dataset_historical_price")


def test_datacore_preview_server_error():
    provider = DataCoreProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(ProviderUnavailableError):
            provider.preview_dataset("dataset_historical_price")


def test_datacore_authenticated_success():
    provider = DataCoreProvider(api_key="datacore_test_secret_key")
    assert provider.is_authenticated

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": True,
        "data": {
            "fields": ["symbol", "date", "open_price", "high_price", "low_price", "close_price", "vol_total"],
            "dataDetail": [
                ["FPT", "2026-10-23", 56500, 56800, 55900, 56000, 10104800],
            ],
            "totalPage": 1,
            "currentPage": 1,
        },
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.fetch_data("dataset_historical_price", page=1, size=10)
        assert res["status"] == "SUCCESS"
        assert len(res["rows"]) == 1
        assert res["fields"][0] == "symbol"


def test_datacore_authenticated_invalid_key():
    provider = DataCoreProvider(api_key="invalid_test_key")
    assert provider.is_authenticated

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {
        "status": False,
        "httpCode": 401,
        "message": "UnAuthorizedException",
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.fetch_data("dataset_historical_price")
        assert res["status"] == "AUTH_FAILED"
        assert "401" in res["reason"] or "UnAuthorized" in res["reason"]
