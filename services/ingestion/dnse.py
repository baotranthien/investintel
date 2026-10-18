"""
DNSE Public Market Data Provider.
Fetches public OHLCV candles from DNSE / Entrade endpoints:
https://services.entrade.com.vn/chart-api/v2/ohlcs/(stock|index)

Based on the reference implementation in trangcm/vn-market-data (tag v0.2.0).
Provides robust retry backoff, response size capping, Vietnam timezone normalization (Asia/Ho_Chi_Minh),
and full integration with IngestionPipeline.
"""
import re
import json
import logging
import math
import time
from datetime import datetime, date, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import httpx

from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_BASE_URL = "https://services.entrade.com.vn/chart-api/v2/ohlcs"
_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App)",
    "Accept": "application/json"
}
_PRICE_SCALE = 1000.0  # DNSE stock prices are reported in thousands of VND
_VN_TZ = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh timezone (UTC+7)
_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB response buffer cap


def normalize_symbol(symbol: str) -> str:
    """Uppercase, strips whitespace and non-alphanumeric characters."""
    if not symbol:
        return ""
    cleaned = re.sub(r'[^A-Za-z0-9]', '', symbol.strip())
    return cleaned.upper()


def _coerce_float(val: Any) -> Optional[float]:
    """Coerces numeric values to float, handling nulls and NaNs safely."""
    try:
        x = float(val)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def _to_epoch(d: date) -> int:
    """Converts a date to Unix seconds at UTC midnight."""
    return int(datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc).timestamp())


class DnseProvider(BaseProvider):
    """
    Public market data provider fetching from DNSE's public unauthenticated HTTP endpoints.
    Disclaimer: Public research source without SLA; for personal/research use.
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("DNSE")
        self.timeout = timeout
        self.base_url = _BASE_URL

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("DNSE does not provide macroeconomic series.")

    def _fetch_raw_response(
        self,
        endpoint_url: str,
        params: Dict[str, Any]
    ) -> Tuple[int, bytes]:
        """
        Executes HTTP GET with retry backoff and response body size capping.
        """
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    with client.stream("GET", endpoint_url, params=params, headers=_HEADERS) as response:
                        status_code = response.status_code
                        if status_code == 429:
                            logger.warning("DNSE rate limited (HTTP 429). Attempt %d/%d", attempt, max_attempts)
                            if attempt < max_attempts:
                                time.sleep(backoff)
                                backoff *= 2
                                continue
                            raise RateLimitedError("DNSE rate limit exceeded")

                        if status_code >= 500:
                            logger.warning("DNSE server error (HTTP %d). Attempt %d/%d", status_code, attempt, max_attempts)
                            if attempt < max_attempts:
                                time.sleep(backoff)
                                backoff *= 2
                                continue
                            raise ProviderUnavailableError(f"DNSE server unavailable: HTTP {status_code}")

                        if status_code != 200:
                            logger.warning("DNSE non-200 response: HTTP %d", status_code)
                            return status_code, b""

                        buf = bytearray()
                        for chunk in response.iter_bytes():
                            buf += chunk
                            if len(buf) > _MAX_RESPONSE_BYTES:
                                raise ProviderUnavailableError(
                                    f"DNSE response exceeded {_MAX_RESPONSE_BYTES} bytes cap"
                                )
                        return status_code, bytes(buf)

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning("DNSE network error on attempt %d/%d: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"DNSE connection failed: {exc}") from exc

        return 500, b""

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        is_index: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetches and standardizes OHLCV candles from DNSE.
        Returns empty list safely on missing data or invalid symbol without crashing.
        """
        norm_sym = normalize_symbol(symbol)
        if not norm_sym:
            return []

        kind = "index" if is_index else "stock"
        endpoint_url = f"{self.base_url}/{kind}"
        from_ts = _to_epoch(start_date)
        # Add 1 day to make end_date inclusive
        to_ts = _to_epoch(end_date) + 86400

        params = {
            "from": from_ts,
            "to": to_ts,
            "symbol": norm_sym,
            "resolution": "1D"
        }

        status, body = self._fetch_raw_response(endpoint_url, params)
        if status != 200 or not body:
            return []

        try:
            data = json.loads(body)
        except (ValueError, TypeError) as exc:
            logger.warning("DNSE malformed JSON payload for %s: %s", norm_sym, exc)
            return []

        if not isinstance(data, dict):
            logger.warning("DNSE unexpected payload format for %s", norm_sym)
            return []

        t_arr = data.get("t")
        c_arr = data.get("c")
        if not isinstance(t_arr, list) or not isinstance(c_arr, list) or not t_arr or not c_arr:
            return []

        o_arr = data.get("o") if isinstance(data.get("o"), list) else []
        h_arr = data.get("h") if isinstance(data.get("h"), list) else []
        l_arr = data.get("l") if isinstance(data.get("l"), list) else []
        v_arr = data.get("v") if isinstance(data.get("v"), list) else []

        scale = 1.0 if is_index else _PRICE_SCALE
        records: List[Dict[str, Any]] = []

        for i in range(len(t_arr)):
            raw_ts = t_arr[i]
            if raw_ts is None:
                continue

            try:
                bar_date = datetime.fromtimestamp(raw_ts, tz=_VN_TZ).date()
            except (TypeError, ValueError, OverflowError, OSError):
                continue

            if bar_date < start_date or bar_date > end_date:
                continue

            ci = _coerce_float(c_arr[i]) if i < len(c_arr) else None
            oi = _coerce_float(o_arr[i]) if i < len(o_arr) else None
            hi = _coerce_float(h_arr[i]) if i < len(h_arr) else None
            li = _coerce_float(l_arr[i]) if i < len(l_arr) else None
            vi = _coerce_float(v_arr[i]) if i < len(v_arr) else 0.0

            if ci is None:
                continue

            # For stock bars, require complete OHLC
            if not is_index and None in (oi, hi, li):
                continue

            close_scaled = ci * scale
            open_scaled = (oi * scale) if oi is not None else close_scaled
            high_scaled = (hi * scale) if hi is not None else close_scaled
            low_scaled = (li * scale) if li is not None else close_scaled

            records.append({
                "symbol": norm_sym,
                "observation_date": bar_date,
                "open": open_scaled,
                "high": high_scaled,
                "low": low_scaled,
                "close": close_scaled,
                "adjusted_close": close_scaled,
                "volume": vi or 0.0
            })

        records.sort(key=lambda r: r["observation_date"])
        return records

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        is_index: bool = False
    ) -> List[MarketDataPoint]:
        """
        Async implementation matching the BaseProvider contract.
        """
        raw_rows = self.fetch_ohlcv(symbol, start_date, end_date, is_index=is_index)
        return [
            MarketDataPoint(
                symbol=row["symbol"],
                observation_date=row["observation_date"],
                close=row["close"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                volume=row["volume"],
            )
            for row in raw_rows
        ]

    def ingest_to_database(
        self,
        session: Session,
        symbol: str,
        start_date: date,
        end_date: date,
        exchange: str = "HOSE",
        source_id: Optional[int] = None,
        is_index: bool = False
    ) -> Dict[str, Any]:
        """
        Runs the full IngestionPipeline: Raw -> Staging -> Validation -> Canonical -> Lineage.
        """
        norm_sym = normalize_symbol(symbol)
        raw_records = self.fetch_ohlcv(norm_sym, start_date, end_date, is_index=is_index)
        source_url = f"{self.base_url}/{'index' if is_index else 'stock'}?symbol={norm_sym}"

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_market_data(
            provider=self.name,
            symbol=norm_sym,
            exchange=exchange,
            records=raw_records,
            source_url_or_path=source_url,
            source_id=source_id
        )
        return result
