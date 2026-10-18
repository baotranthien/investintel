"""
GDELT 2.0 Doc API Public News Provider.
Fetches public international and Vietnam equity-market news and events from:
https://api.gdeltproject.org/api/v2/doc/doc

Authentication is NOT required.
Authority: REPUTABLE_SECONDARY (Article-discovery / indexing engine, not original publisher).
Enforces strict request pacing (>= 5.5s inter-request interval) to respect GDELT per-IP quotas.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import httpx

from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MiB cap
_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App; Multi-Provider)",
    "Accept": "application/json"
}
_MIN_PACING_SECONDS = 5.5


class GDELTNewsProvider(BaseProvider):
    """
    Public article-discovery provider using the GDELT 2.0 Doc API.
    Provides bounded queries, strict rate-pacing, and canonical EventRecord promotion.
    """
    _last_request_time: float = 0.0
    _lock = asyncio.Lock()

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("GDELT")
        self.timeout = timeout
        self.endpoint_url = _GDELT_DOC_URL

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("GDELT does not provide macroeconomic time series.")

    async def fetch_market_data(self, symbol: str, start_date, end_date) -> List[MarketDataPoint]:
        raise NotImplementedError("GDELT does not provide equity market OHLCV data.")

    async def _pace_request(self) -> None:
        """Enforces minimum inter-request interval of 5.5s to comply with GDELT IP limit."""
        async with GDELTNewsProvider._lock:
            now = time.monotonic()
            elapsed = now - GDELTNewsProvider._last_request_time
            if elapsed < _MIN_PACING_SECONDS:
                wait_time = _MIN_PACING_SECONDS - elapsed
                logger.debug("GDELT rate-pacing: waiting %.2f seconds", wait_time)
                await asyncio.sleep(wait_time)
            GDELTNewsProvider._last_request_time = time.monotonic()

    async def search_articles(
        self,
        query: str = "vietnam stock market",
        max_records: int = 15,
        mode: str = "artlist"
    ) -> List[Dict[str, Any]]:
        """
        Executes an unauthenticated query against GDELT Doc 2.0 API.
        Returns normalized article dictionaries ready for canonical event ingestion.
        """
        params = {
            "query": query,
            "mode": mode,
            "format": "json",
            "maxrecords": min(max_records, 50),
            "sort": "datedesc"
        }

        await self._pace_request()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.endpoint_url, params=params, headers=_HEADERS)
                if response.status_code == 429:
                    logger.warning("GDELT rate limited (HTTP 429). Backing off.")
                    return []

                if response.status_code >= 500:
                    logger.warning("GDELT server error HTTP %d", response.status_code)
                    return []

                if response.status_code != 200:
                    logger.warning("GDELT non-200 HTTP %d", response.status_code)
                    return []

                if len(response.content) > _MAX_RESPONSE_BYTES:
                    logger.warning("GDELT payload exceeded size cap")
                    return []

                # Handle potential UTF-8 issues gracefully
                text = response.content.decode("utf-8", errors="replace")
                # Sometimes GDELT returns HTML error pages or empty bodies with 200
                if not text.strip().startswith("{") and not text.strip().startswith("["):
                    logger.warning("GDELT returned non-JSON body")
                    return []

                data = json.loads(text)
                if not isinstance(data, dict):
                    return []

                raw_articles = data.get("articles") or []
                if not isinstance(raw_articles, list):
                    return []

                cleaned: List[Dict[str, Any]] = []
                for item in raw_articles:
                    if not isinstance(item, dict):
                        continue

                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    if not title or not url:
                        continue

                    # Parse seendate e.g. "20241014T143000Z"
                    seendate_raw = item.get("seendate")
                    published_at = None
                    if seendate_raw and isinstance(seendate_raw, str):
                        try:
                            # Format: YYYYMMDDTHHMMSSZ
                            clean_ts = seendate_raw.replace("T", "").replace("Z", "")
                            if len(clean_ts) >= 14:
                                dt = datetime.strptime(clean_ts[:14], "%Y%m%d%H%M%S")
                                published_at = dt.replace(tzinfo=timezone.utc).isoformat()
                        except ValueError:
                            published_at = None

                    domain = item.get("domain", "GDELT Index")
                    cleaned.append({
                        "id": url,  # Stable deduplication key
                        "title": title,
                        "url": url,
                        "published_at": published_at,
                        "snippet": f"[{domain}] {title}",
                        "sourceName": f"GDELT ({domain})",
                        "event_type": "Market",
                        "materiality": "INFORMATIONAL",
                        "severity": 40.0,
                        "sentiment": "NEUTRAL",
                    })

                return cleaned

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            logger.warning("GDELT network error: %s", exc)
            return []
        except Exception as exc:
            logger.warning("GDELT unexpected error: %s", exc)
            return []

    async def ingest_to_database(
        self,
        session: Session,
        query: str = "vietnam stock market",
        max_records: int = 15,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs the canonical IngestionPipeline for GDELT news events.
        """
        articles = await self.search_articles(query=query, max_records=max_records)
        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_news_events(
            provider=self.name,
            articles=articles,
            source_url=self.endpoint_url,
            source_id=source_id
        )
        return result
