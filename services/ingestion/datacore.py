"""
DataCore Vietnam Provider.
Client integration for the DataCore Vietnam REST API (gateway.datacore.vn).
Supports:
1. Preview mode (no-key): previews publicly documented catalog datasets (e.g. dataset_historical_price, gross_domestic_product_dataset_ds).
2. Authenticated mode: queries full datasets with X_API_KEY when configured.
3. Clean-room implementation using httpx (without requiring pandas).
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from .base import BaseProvider, MarketDataPoint, MacroDataPoint
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_GATEWAY_URL = "https://gateway.datacore.vn"
_PREVIEW_URL = f"{_GATEWAY_URL}/data/ds/preview"
_GET_DATA_URL = f"{_GATEWAY_URL}/data/ds/get-data"
_SEARCH_URL = f"{_GATEWAY_URL}/data/ds/search"

_DEFAULT_TIMEOUT = 15.0


def normalize_symbol(symbol: str) -> str:
    if not symbol:
        return ""
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        clean = clean[1:]
    return re.sub(r"[^A-Za-z0-9]", "", clean)


class DataCoreProvider(BaseProvider):
    """
    DataCore Vietnam provider supporting unauthenticated catalog previews and
    authenticated commercial queries via X_API_KEY.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("DATACORE")
        self.api_key = api_key or os.getenv("X_API_KEY") or os.getenv("DATACORE_API_KEY") or ""
        self.timeout = timeout

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "InvestIntel/1.0 (Clean-Room DataCore Client)",
        }
        if self.is_authenticated:
            headers["x-api-key"] = self.api_key.strip()
        return headers

    def preview_dataset(self, dataset_code: str) -> Dict[str, Any]:
        """
        Public unauthenticated preview of a DataCore dataset.
        Returns metadata and fixed sample rows (up to 10 rows).
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(_PREVIEW_URL, params={"dataSetCode": dataset_code}, headers=self._get_headers())
                if resp.status_code == 429:
                    raise RateLimitedError("DataCore preview rate limit exceeded")
                if resp.status_code >= 500:
                    raise ProviderUnavailableError(f"DataCore gateway error HTTP {resp.status_code}")
                if resp.status_code != 200:
                    logger.warning("DataCore preview HTTP %d: %s", resp.status_code, resp.text[:200])
                    return {"fields": [], "rows": [], "error": f"HTTP {resp.status_code}"}

                data = resp.json()
                inner = data.get("data") or {}
                fields = inner.get("fields") or []
                rows = inner.get("dataDetail") or []
                return {
                    "dataset_code": dataset_code,
                    "fields": fields,
                    "rows": rows,
                    "num_preview_rows": len(rows),
                    "authenticated": False,
                }
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(f"DataCore preview request failed: {exc}") from exc

    def fetch_data(
        self,
        dataset_code: str,
        page: int = 1,
        size: int = 50,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Queries DataCore dataset in authenticated paid mode.
        If X_API_KEY is missing, returns status BLOCKED_MISSING_CREDENTIAL.
        """
        if not self.is_authenticated:
            logger.info("DataCore full query requested without X_API_KEY; reporting unconfigured credential")
            return {
                "status": "BLOCKED_MISSING_CREDENTIAL",
                "dataset_code": dataset_code,
                "fields": [],
                "rows": [],
                "reason": "DataCore paid API requires X_API_KEY in environment",
            }

        payload: Dict[str, Any] = {
            "dataSetCode": dataset_code,
            "page": page,
            "size": size,
        }
        if conditions:
            payload["conditions"] = conditions

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(_GET_DATA_URL, json=payload, headers=self._get_headers())
                if resp.status_code in (401, 403):
                    return {
                        "status": "AUTH_FAILED",
                        "dataset_code": dataset_code,
                        "fields": [],
                        "rows": [],
                        "reason": f"DataCore authentication failed HTTP {resp.status_code}",
                    }
                if resp.status_code != 200:
                    raise ProviderUnavailableError(f"DataCore HTTP {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                if not data.get("status") and data.get("httpCode") in (401, 403):
                    return {
                        "status": "AUTH_FAILED",
                        "dataset_code": dataset_code,
                        "fields": [],
                        "rows": [],
                        "reason": data.get("message") or "Unauthorized",
                    }

                inner = data.get("data") or {}
                return {
                    "status": "SUCCESS",
                    "dataset_code": dataset_code,
                    "fields": inner.get("fields") or [],
                    "rows": inner.get("dataDetail") or [],
                    "total_page": inner.get("totalPage"),
                    "current_page": inner.get("currentPage"),
                }
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(f"DataCore request failed: {exc}") from exc

    async def fetch_market_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[MarketDataPoint]:
        """
        Fetches price observations from DataCore if authenticated.
        Returns empty list when unauthenticated.
        """
        if not self.is_authenticated:
            logger.debug("DataCore market data skipped: X_API_KEY not configured")
            return []

        norm_sym = normalize_symbol(symbol)
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            self.fetch_data,
            "dataset_historical_price",
            1,
            100,
            {"symbol": norm_sym},
        )
        if res.get("status") != "SUCCESS":
            return []

        points: List[MarketDataPoint] = []
        fields = res.get("fields") or []
        rows = res.get("rows") or []

        sym_idx = fields.index("symbol") if "symbol" in fields else -1
        date_idx = fields.index("date") if "date" in fields else -1
        close_idx = fields.index("close_price") if "close_price" in fields else -1
        open_idx = fields.index("open_price") if "open_price" in fields else -1
        high_idx = fields.index("high_price") if "high_price" in fields else -1
        low_idx = fields.index("low_price") if "low_price" in fields else -1
        vol_idx = fields.index("vol_total") if "vol_total" in fields else -1

        for r in rows:
            if not isinstance(r, list) or len(r) <= max(date_idx, close_idx):
                continue
            try:
                obs_dt = datetime.fromisoformat(str(r[date_idx])[:10]).date()
            except (ValueError, TypeError):
                continue

            if not (start_date <= obs_dt <= end_date):
                continue

            c_val = float(r[close_idx]) if close_idx >= 0 and r[close_idx] is not None else 0.0
            o_val = float(r[open_idx]) if open_idx >= 0 and r[open_idx] is not None else c_val
            h_val = float(r[high_idx]) if high_idx >= 0 and r[high_idx] is not None else c_val
            l_val = float(r[low_idx]) if low_idx >= 0 and r[low_idx] is not None else c_val
            v_val = float(r[vol_idx]) if vol_idx >= 0 and r[vol_idx] is not None else 0.0

            points.append(MarketDataPoint(
                symbol=norm_sym,
                observation_date=obs_dt,
                close=c_val,
                open=o_val,
                high=h_val,
                low=l_val,
                volume=v_val,
            ))
        return points

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        if not self.is_authenticated:
            logger.debug("DataCore macro series skipped: X_API_KEY not configured")
            return []
        return []
