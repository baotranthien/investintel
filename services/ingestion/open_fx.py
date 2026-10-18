"""
Free Foreign-Exchange Rates Provider.
Provides daily currency reference rates without requiring an API key.

Primary candidate: Frankfurter API (https://api.frankfurter.dev/v2)
Verified fallback for VND: Open Exchange Rates free endpoint (https://open.er-api.com/v6/latest/USD)

Authority: REPUTABLE_SECONDARY.
Disclaimer: Reference FX rate only; never labeled as an official State Bank of Vietnam (SBV) central rate.
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
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB cap
_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App; Multi-Provider)",
    "Accept": "application/json"
}

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v2"
OPEN_ER_API_BASE_URL = "https://open.er-api.com/v6"


class FreeFxProvider(BaseProvider):
    """
    Unauthenticated Foreign Exchange Rate Provider.
    Checks Frankfurter first; falls back to open.er-api.com when VND is unsupported.
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("OPEN_EXCHANGE_RATES")
        self.timeout = timeout
        self.frankfurter_url = FRANKFURTER_BASE_URL
        self.open_er_url = OPEN_ER_API_BASE_URL

    async def _try_frankfurter_rate(self, base: str = "USD", quote: str = "VND") -> Optional[MacroDataPoint]:
        """
        Attempts to fetch rate from Frankfurter API.
        Returns None if quote currency is not supported.
        """
        url = f"{self.frankfurter_url}/latest?base={base}&symbols={quote}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=_HEADERS)
                if res.status_code == 200:
                    data = res.json()
                    rates = data.get("rates", {})
                    if quote in rates and rates[quote] is not None:
                        rate_val = float(rates[quote])
                        obs_str = data.get("date")
                        obs_date = datetime.strptime(obs_str, "%Y-%m-%d").date() if obs_str else date.today()
                        return MacroDataPoint(
                            series_id=f"FX_{base}_{quote}",
                            observation_date=obs_date,
                            release_date=obs_date,
                            value=rate_val,
                            unit=f"{quote}_PER_{base}",
                            frequency="DAILY"
                        )
        except Exception as exc:
            logger.debug("Frankfurter FX lookup failed for %s/%s: %s", base, quote, exc)
        return None

    async def _fetch_open_er_rate(self, base: str = "USD", quote: str = "VND") -> MacroDataPoint:
        """
        Fetches reference exchange rate from open.er-api.com unauthenticated endpoint.
        """
        url = f"{self.open_er_url}/latest/{base}"
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(url, headers=_HEADERS)
                    if res.status_code == 429:
                        logger.warning("open.er-api rate limited (HTTP 429). Attempt %d/%d", attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("open.er-api rate limit exceeded")

                    if res.status_code >= 500:
                        logger.warning("open.er-api server error HTTP %d. Attempt %d/%d", res.status_code, attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"open.er-api server error: HTTP {res.status_code}")

                    if res.status_code != 200:
                        raise ProviderUnavailableError(f"open.er-api returned HTTP {res.status_code}")

                    if len(res.content) > _MAX_RESPONSE_BYTES:
                        raise ProviderUnavailableError(f"open.er-api response exceeded {_MAX_RESPONSE_BYTES} bytes")

                    data = res.json()
                    if data.get("result") != "success":
                        raise ProviderUnavailableError(f"open.er-api result status: {data.get('result')}")

                    rates = data.get("rates", {})
                    if quote not in rates or rates[quote] is None:
                        raise ProviderUnavailableError(f"Currency quote {quote} not found in rates")

                    rate_val = float(rates[quote])
                    time_unix = data.get("time_last_update_unix")
                    if time_unix:
                        obs_date = datetime.fromtimestamp(time_unix, tz=timezone.utc).date()
                    else:
                        obs_date = date.today()

                    return MacroDataPoint(
                        series_id=f"FX_{base}_{quote}",
                        observation_date=obs_date,
                        release_date=obs_date,
                        value=rate_val,
                        unit=f"{quote}_PER_{base}",
                        frequency="DAILY"
                    )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning("open.er-api network error on attempt %d/%d: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"open.er-api unreachable: {exc}") from exc

        raise ProviderUnavailableError("open.er-api exhausted retry attempts")

    async def fetch_macro_series(self, series_id: str = "FX_USD_VND", **kwargs) -> List[MacroDataPoint]:
        """
        Fetches reference exchange rate. First checks Frankfurter, falls back to open.er-api.
        """
        base = kwargs.get("base", "USD")
        quote = kwargs.get("quote", "VND")

        # Try Frankfurter first as requested
        point = await self._try_frankfurter_rate(base=base, quote=quote)
        if point is None:
            # Fallback to verified open.er-api
            point = await self._fetch_open_er_rate(base=base, quote=quote)

        # Standardize series_id to match request
        point.series_id = series_id
        return self.validate_macro_data([point])

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError("FX provider does not provide equity market data.")

    async def ingest_to_database(
        self,
        session: Session,
        series_id: str = "FX_USD_VND",
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs the canonical IngestionPipeline for reference FX rate.
        """
        records = await self.fetch_macro_series(series_id)
        source_url = f"{self.open_er_url}/latest/USD"
        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_macro_series(
            provider=self.name,
            series_id=series_id,
            records=records,
            source_url=source_url,
            source_id=source_id
        )
        return result
