"""
World Bank Indicators API Provider.
Fetches official macroeconomic indicators from the World Bank API v2:
https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json

Authentication is NOT required.
Authority: INTERNATIONAL_OFFICIAL / REPUTABLE_SECONDARY for Vietnam macroeconomic data.
Preserves genuine observation periods (Annual Dec 31), units, and null values without fabrication.
"""
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import httpx

from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MiB cap
_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App; Multi-Provider)",
    "Accept": "application/json"
}

WORLD_BANK_INDICATORS: Dict[str, Dict[str, Any]] = {
    "WB_VNM_GDP": {
        "indicator": "NY.GDP.MKTP.CD",
        "name": "Vietnam GDP (Current US$)",
        "unit": "USD",
        "frequency": "ANNUAL",
        "country": "VNM"
    },
    "WB_VNM_CPI": {
        "indicator": "FP.CPI.TOTL.ZG",
        "name": "Vietnam Inflation, Consumer Prices (Annual %)",
        "unit": "PERCENT",
        "frequency": "ANNUAL",
        "country": "VNM"
    },
    "WB_VNM_CAB": {
        "indicator": "BN.CAB.XOKA.CD",
        "name": "Vietnam Current Account Balance (Current US$)",
        "unit": "USD",
        "frequency": "ANNUAL",
        "country": "VNM"
    },
    "WB_VNM_RES": {
        "indicator": "FI.RES.TOTL.CD",
        "name": "Vietnam Total Reserves including Gold (Current US$)",
        "unit": "USD",
        "frequency": "ANNUAL",
        "country": "VNM"
    },
    "WB_VNM_UEM": {
        "indicator": "SL.UEM.TOTL.ZS",
        "name": "Vietnam Unemployment Rate (% of Total Labor Force)",
        "unit": "PERCENT",
        "frequency": "ANNUAL",
        "country": "VNM"
    },
}

# Reverse lookup by raw World Bank indicator code
_CODE_TO_SERIES = {v["indicator"]: k for k, v in WORLD_BANK_INDICATORS.items()}


class WorldBankProvider(BaseProvider):
    """
    World Bank API v2 macro indicator adapter.
    Unauthenticated open public interface.
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("WORLD_BANK")
        self.timeout = timeout
        self.base_url = "https://api.worldbank.org/v2"

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        """
        Fetch World Bank macro series for a given series_id or indicator code.
        Accepts registered series_id (e.g. 'WB_VNM_GDP') or raw indicator (e.g. 'NY.GDP.MKTP.CD').
        """
        config = WORLD_BANK_INDICATORS.get(series_id)
        if config:
            indicator_code = config["indicator"]
            country = kwargs.get("country", config.get("country", "VNM"))
            unit = config["unit"]
            frequency = config["frequency"]
            canonical_series_id = series_id
        else:
            indicator_code = series_id
            canonical_series_id = _CODE_TO_SERIES.get(series_id, series_id)
            country = kwargs.get("country", "VNM")
            unit = kwargs.get("unit", "USD" if ".CD" in series_id else "PERCENT")
            frequency = kwargs.get("frequency", "ANNUAL")

        per_page = kwargs.get("per_page", 100)
        url = f"{self.base_url}/country/{country}/indicator/{indicator_code}"
        params = {
            "format": "json",
            "per_page": per_page
        }

        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params, headers=_HEADERS)
                    if response.status_code == 429:
                        logger.warning("World Bank rate limited (HTTP 429). Attempt %d/%d", attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("World Bank rate limit exceeded")

                    if response.status_code >= 500:
                        logger.warning("World Bank server error HTTP %d. Attempt %d/%d", response.status_code, attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"World Bank server error: HTTP {response.status_code}")

                    if response.status_code != 200:
                        raise ProviderUnavailableError(f"World Bank returned HTTP {response.status_code}")

                    if len(response.content) > _MAX_RESPONSE_BYTES:
                        raise ProviderUnavailableError(f"World Bank response exceeded {_MAX_RESPONSE_BYTES} bytes")

                    data = response.json()
                    # World Bank returns [pagination_meta, data_list] or an error dict
                    if not isinstance(data, list) or len(data) < 2:
                        # Sometimes World Bank returns an error object e.g. [{"message": ...}]
                        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict) and "message" in data[0]:
                            msg = data[0]["message"]
                            raise ProviderUnavailableError(f"World Bank API message: {msg}")
                        return []

                    records_raw = data[1]
                    if not isinstance(records_raw, list):
                        return []

                    results: List[MacroDataPoint] = []
                    for item in records_raw:
                        if not isinstance(item, dict):
                            continue
                        val = item.get("value")
                        if val is None:
                            # Preserve missing observations as missing
                            continue
                        try:
                            num_val = float(val)
                        except (ValueError, TypeError):
                            continue

                        date_str = str(item.get("date", "")).strip()
                        if not date_str:
                            continue

                        # World Bank annual dates are 'YYYY'
                        try:
                            if len(date_str) == 4 and date_str.isdigit():
                                obs_date = date(int(date_str), 12, 31)
                            elif "-" in date_str:
                                parts = date_str.split("-")
                                obs_date = date(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1)
                            else:
                                continue
                        except (ValueError, IndexError):
                            continue

                        results.append(MacroDataPoint(
                            series_id=canonical_series_id,
                            observation_date=obs_date,
                            release_date=None,
                            value=num_val,
                            unit=unit,
                            frequency=frequency
                        ))

                    # Sort chronologically ascending
                    results.sort(key=lambda p: p.observation_date)
                    return self.validate_macro_data(results)

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning("World Bank network error on attempt %d/%d: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"World Bank endpoint unreachable: {exc}") from exc

        return []

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError("World Bank provider does not provide equity market data.")

    async def ingest_to_database(
        self,
        session: Session,
        series_id: str,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs the canonical IngestionPipeline for a World Bank macroeconomic series.
        """
        records = await self.fetch_macro_series(series_id)
        config = WORLD_BANK_INDICATORS.get(series_id, {})
        ind_code = config.get("indicator", series_id)
        source_url = f"{self.base_url}/country/VNM/indicator/{ind_code}?format=json"

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_macro_series(
            provider=self.name,
            series_id=series_id,
            records=records,
            source_url=source_url,
            source_id=source_id
        )
        return result
