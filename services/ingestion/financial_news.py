"""
Financial News RSS Ingestion Provider for Vietnam Market.
Fetches public news feeds from reliable publishers (CafeF and VnEconomy).
Parses, deduplicates, and validates articles into canonical EventRecords via IngestionPipeline.
"""
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Set
import httpx
from sqlalchemy.orm import Session

from database.models import DataSource, EventRecord
from .base import BaseProvider, MacroDataPoint, MarketDataPoint
from .http_client import ProviderUnavailableError, RateLimitedError
from .pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

# Official, verified public RSS feeds for Vietnamese financial news
DEFAULT_NEWS_FEEDS = [
    {
        "publisher": "CafeF",
        "url": "https://cafef.vn/thi-truong-chung-khoan.rss",
        "category": "MARKET",
    },
    {
        "publisher": "CafeF",
        "url": "https://cafef.vn/doanh-nghiep.rss",
        "category": "CORPORATE",
    },
    {
        "publisher": "VnEconomy",
        "url": "https://vneconomy.vn/chung-khoan.rss",
        "category": "MARKET",
    },
]

# Supported ticker universe for entity mapping
KNOWN_TICKERS = {
    "FPT", "VCB", "MBB", "MWG", "HPG", "SSI", "VHM", "VIC", "VNM", "TCB",
    "ACB", "STB", "BID", "CTG", "VRE", "MSN", "GAS", "PLX", "SAB", "POW",
    "HDB", "TPB", "SHB", "VIB", "BVH", "BCM", "GVR", "KDH", "PDR", "NVL",
    "VCI", "HCM", "DGC", "DXG", "DIG", "NLG", "KBC", "PVD", "PVS", "REE",
}

# Materiality & Event Classification Keywords
MATERIAL_KEYWORDS = {
    "cổ tức", "lợi nhuận", "thâu tóm", "giải chấp", "thua lỗ", "tăng vốn",
    "phát hành", "điều tra", "khởi tố", "thanh tra", "trái phiếu", "vỡ nợ",
    "đình chỉ", "sáp nhập", "mua lại", "phá sản", "hủy niêm yết"
}

EARNINGS_KEYWORDS = {"lợi nhuận", "doanh thu", "báo cáo tài chính", "bctc", "kết quả kinh doanh", "lãi ròng"}
REGULATION_KEYWORDS = {"thanh tra", "xử phạt", "ủy ban chứng khoán", "ubck", "khởi tố", "nghị định", "bộ tài chính"}
MACRO_KEYWORDS = {"lạm phát", "lãi suất", "tỷ giá", "ngân hàng nhà nước", "fed", "gdp", "cpi", "fdi"}

POSITIVE_KEYWORDS = {"tăng trưởng", "lợi nhuận kỷ lục", "vượt kế hoạch", "khởi sắc", "bứt phá", "mua ròng", "tăng mạnh", "vượt đỉnh"}
NEGATIVE_KEYWORDS = {"thua lỗ", "sụt giảm", "lao dốc", "bán tháo", "giảm mạnh", "xử phạt", "khởi tố", "khó khăn", "nợ xấu", "thủng đáy"}

_HEADERS = {
    "User-Agent": "InvestIntel/1.0 (Personal Research Ingestion Bot)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags, decode entities, and normalize whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _sanitize_xml(raw_bytes: bytes) -> str:
    """Sanitize XML string by decoding and replacing unescaped ampersands."""
    text = raw_bytes.decode("utf-8", errors="replace")
    # Fix stray ampersands not part of XML entities
    text = re.sub(r"&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    # Remove ASCII control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def _extract_tickers(text: str, candidates: Set[str] = KNOWN_TICKERS) -> List[str]:
    """Find whole-word ticker matches in upper-cased text."""
    if not text:
        return []
    upper_text = text.upper()
    return [t for t in candidates if re.search(r"\b" + t + r"\b", upper_text)]


def _classify_article(title: str, snippet: str) -> tuple[str, str, str, float]:
    """
    Returns (event_type, materiality, sentiment, severity).
    Deterministic heuristics without hallucinations.
    """
    combined = f"{title} {snippet}".lower()

    # Event Type
    if any(k in combined for k in EARNINGS_KEYWORDS):
        event_type = "Earnings"
    elif any(k in combined for k in REGULATION_KEYWORDS):
        event_type = "Regulation"
    elif any(k in combined for k in MACRO_KEYWORDS):
        event_type = "Macro"
    else:
        event_type = "News"

    # Materiality
    is_material = any(k in combined for k in MATERIAL_KEYWORDS)
    materiality = "MATERIAL" if is_material else "INFORMATIONAL"
    severity = 65.0 if is_material else 40.0

    # Sentiment
    pos_score = sum(1 for k in POSITIVE_KEYWORDS if k in combined)
    neg_score = sum(1 for k in NEGATIVE_KEYWORDS if k in combined)
    if pos_score > neg_score:
        sentiment = "POSITIVE"
    elif neg_score > pos_score:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return event_type, materiality, sentiment, severity


class FinancialNewsProvider(BaseProvider):
    """
    Ingests financial news articles from verified Vietnamese RSS feeds.
    Provides Point-In-Time timestamps, URL deduplication, and entity linking.
    """

    def __init__(
        self,
        feeds: Optional[List[Dict[str, str]]] = None,
        timeout: float = 15.0,
    ):
        super().__init__("FINANCIAL_NEWS")
        self.feeds = feeds or DEFAULT_NEWS_FEEDS
        self.timeout = timeout

    async def fetch_macro_series(self, series_id: str, **kwargs) -> List[MacroDataPoint]:
        raise NotImplementedError("FinancialNewsProvider does not provide macro series.")

    async def fetch_market_data(self, symbol: str, start_date: date, end_date: date) -> List[MarketDataPoint]:
        raise NotImplementedError("FinancialNewsProvider does not provide market data.")

    def parse_feed_xml(self, xml_content: str, publisher: str, category: str = "MARKET") -> List[Dict[str, Any]]:
        """Parses RSS XML content into normalized article dictionaries."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as exc:
            logger.warning("XML parse error for %s: %s", publisher, exc)
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        items = channel.findall("item")
        articles: List[Dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)

        for item in items:
            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description")
            pub_date_node = item.find("pubDate")

            raw_title = title_node.text if title_node is not None and title_node.text else ""
            raw_link = link_node.text if link_node is not None and link_node.text else ""
            raw_desc = desc_node.text if desc_node is not None and desc_node.text else ""
            raw_pub_date = pub_date_node.text if pub_date_node is not None and pub_date_node.text else ""

            title = _strip_html(raw_title)
            link = raw_link.strip()
            snippet = _strip_html(raw_desc)

            if not title or not link or not (link.startswith("http://") or link.startswith("https://")):
                continue

            # Publication timestamp
            pub_dt: Optional[datetime] = None
            if raw_pub_date:
                try:
                    pub_dt = parsedate_to_datetime(raw_pub_date.strip())
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    else:
                        pub_dt = pub_dt.astimezone(timezone.utc)
                except Exception:
                    pub_dt = None

            # Guard against future dates beyond current UTC + 1 hour
            if pub_dt and pub_dt > now_utc:
                pub_dt = now_utc

            # Linked tickers
            matched_tickers = _extract_tickers(f"{title} {snippet}")

            # Classification
            event_type, materiality, sentiment, severity = _classify_article(title, snippet)

            impacts = [{"entity_name": sym, "impact_type": "NEWS"} for sym in matched_tickers]
            sectors = ["FINANCE"]
            if any(sym in {"FPT"} for sym in matched_tickers):
                sectors.append("TECHNOLOGY")
            if any(sym in {"VCB", "MBB", "TCB", "ACB", "BID", "CTG"} for sym in matched_tickers):
                sectors.append("BANK")
            if any(sym in {"HPG"} for sym in matched_tickers):
                sectors.append("MATERIALS")
            if any(sym in {"MWG"} for sym in matched_tickers):
                sectors.append("RETAIL")

            articles.append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "source": publisher,
                "sourceName": publisher,
                "published_at": pub_dt or now_utc,
                "event_type": event_type,
                "materiality": materiality,
                "sentiment": sentiment,
                "severity": severity,
                "affected_sectors": list(set(sectors)),
                "impacts": impacts,
                "matched_tickers": matched_tickers,
                "category": category,
            })

        return articles

    def fetch_articles(self, max_per_feed: int = 30) -> List[Dict[str, Any]]:
        """Fetches from all configured RSS feeds with retries and deduplication."""
        all_articles: List[Dict[str, Any]] = []
        seen_urls: Set[str] = set()

        for feed_info in self.feeds:
            url = feed_info["url"]
            publisher = feed_info["publisher"]
            category = feed_info.get("category", "MARKET")

            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.get(url, headers=_HEADERS)
                        if resp.status_code == 429:
                            if attempt < max_attempts:
                                time.sleep(1.0)
                                continue
                            logger.warning("Rate limit on RSS feed: %s", url)
                            break
                        if resp.status_code != 200:
                            logger.warning("Feed %s returned HTTP %d", url, resp.status_code)
                            break

                        xml_clean = _sanitize_xml(resp.content)
                        parsed = self.parse_feed_xml(xml_clean, publisher, category)

                        count = 0
                        for art in parsed:
                            if art["url"] not in seen_urls:
                                seen_urls.add(art["url"])
                                all_articles.append(art)
                                count += 1
                                if count >= max_per_feed:
                                    break
                        break
                except Exception as exc:
                    logger.warning("Error fetching RSS feed %s (attempt %d): %s", url, attempt, exc)

        return all_articles

    def ingest_to_database(
        self,
        session: Session,
        max_articles: int = 50,
        source_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs full pipeline staging, deduplication, and canonical EventRecord promotion.
        """
        articles = self.fetch_articles(max_per_feed=max_articles // len(self.feeds) + 5)
        if not articles:
            return {
                "provider": self.name,
                "dataset": "news_events",
                "status": "INSUFFICIENT_DATA",
                "records_received": 0,
                "records_promoted": 0,
                "records_rejected": 0,
            }

        if source_id is None:
            source = session.query(DataSource).filter_by(name="FINANCIAL_NEWS").first()
            if not source:
                source = DataSource(
                    name="FINANCIAL_NEWS",
                    provider="CafeF & VnEconomy RSS Feeds",
                    country="VNM",
                    authority_level="REPUTABLE_SECONDARY",
                    source_type="RSS_FEED",
                    base_url="https://cafef.vn",
                    active=True,
                )
                session.add(source)
                session.flush()
            source_id = source.id

        pipeline = IngestionPipeline(session)
        result = pipeline.ingest_news_events(
            provider=self.name,
            articles=articles[:max_articles],
            source_url="https://cafef.vn/rss",
            source_id=source_id,
        )
        return result
