"""
Vietstock Public News Provider.
Fetches public news articles from:
https://vietstock.info/api/news/today

Integrates with IngestionPipeline to parse, validate, stage, and promote
into canonical EventRecord objects with data lineage and quality reports.
"""
import json
import logging
import time
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import httpx

from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .pipeline import IngestionPipeline
from .http_client import ProviderUnavailableError, RateLimitedError

logger = logging.getLogger(__name__)

_VIETSTOCK_NEWS_URL = "https://vietstock.info/api/news/today"
_HEADERS = {
    "User-Agent": "InvestmentIntel/1.0 (Personal Research App)",
    "Accept": "application/json"
}
_DEFAULT_TIMEOUT = 15.0
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class VietstockNewsProvider(BaseProvider):
    """
    Public news provider fetching from Vietstock unauthenticated API.
    Disclaimer: Public research source without SLA; for personal/research use.
    """
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        super().__init__("VIETSTOCK")
        self.timeout = timeout
        self.endpoint_url = _VIETSTOCK_NEWS_URL

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("Vietstock news provider does not provide macroeconomic series.")

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError("Vietstock news provider does not provide market OHLCV data.")

    def fetch_today_news(self) -> List[Dict[str, Any]]:
        """
        Fetches today's news articles from Vietstock API.
        Handles retries, rate limits, and parsing errors safely.
        """
        max_attempts = 3
        backoff = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(self.endpoint_url, headers=_HEADERS)
                    if response.status_code == 429:
                        logger.warning("Vietstock rate limited (HTTP 429). Attempt %d/%d", attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise RateLimitedError("Vietstock rate limit exceeded")

                    if response.status_code >= 500:
                        logger.warning("Vietstock server error HTTP %d. Attempt %d/%d", response.status_code, attempt, max_attempts)
                        if attempt < max_attempts:
                            time.sleep(backoff)
                            backoff *= 2
                            continue
                        raise ProviderUnavailableError(f"Vietstock server error: HTTP {response.status_code}")

                    if response.status_code != 200:
                        logger.warning("Vietstock returned non-200 HTTP %d", response.status_code)
                        return []

                    raw_bytes = response.content
                    if len(raw_bytes) > _MAX_RESPONSE_BYTES:
                        raise ProviderUnavailableError(f"Vietstock payload exceeded {_MAX_RESPONSE_BYTES} bytes")

                    data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
                    if not isinstance(data, dict):
                        logger.warning("Vietstock returned unexpected JSON structure")
                        return []

                    articles_raw = data.get("articles") or []
                    if not isinstance(articles_raw, list):
                        return []

                    cleaned_articles: List[Dict[str, Any]] = []
                    for item in articles_raw:
                        if not isinstance(item, dict):
                            continue

                        title = str(item.get("title") or "").strip()
                        url = str(item.get("url") or "").strip()
                        pub_str = item.get("publishedAt")

                        if not title:
                            continue

                        snippet = (
                            item.get("snippet")
                            or item.get("summaryVi")
                            or item.get("contentLimited")
                            or ""
                        )

                        cleaned_articles.append({
                            "id": item.get("id"),
                            "title": title,
                            "url": url,
                            "published_at": pub_str,
                            "snippet": str(snippet).strip(),
                            "sourceName": item.get("sourceName", "Vietstock"),
                            "event_type": "Market",
                            "materiality": "INFORMATIONAL",
                            "severity": 50.0,
                            "sentiment": "NEUTRAL",
                        })

                    return cleaned_articles

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning("Vietstock network error on attempt %d/%d: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise ProviderUnavailableError(f"Vietstock endpoint unreachable: {exc}") from exc

        return []

    def ingest_to_database(
        self,
        session: Session,
        source_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Runs the full IngestionPipeline: Raw -> Staging -> Validation -> Canonical EventRecord -> Lineage.
        """
        articles = self.fetch_today_news()
        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_news_events(
            provider=self.name,
            articles=articles,
            source_url=self.endpoint_url,
            source_id=source_id
        )
        return result
