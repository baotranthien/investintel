"""
Deterministic Unit Tests for FinancialNewsProvider (CafeF / VnEconomy RSS Ingestion).
Verifies XML parsing, ticker matching, date parsing, sanitization, and pipeline integration.
"""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock

from database.models import DataSource, EventRecord, StagingRecord, DataQualityReportRecord
from services.ingestion.financial_news import (
    FinancialNewsProvider,
    _extract_tickers,
    _strip_html,
    _sanitize_xml,
    _classify_article,
)

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Kênh thông tin tài chính - kinh tế Việt Nam</title>
    <link>https://cafef.vn</link>
    <description>CafeF</description>
    <item>
      <title><![CDATA[FPT công bố lợi nhuận kỷ lục 9 tháng đầu năm, vượt kế hoạch]]></title>
      <link>https://cafef.vn/fpt-cong-bo-loi-nhuan-ky-luc-9-thang-12345.chn</link>
      <description><![CDATA[<a href="https://cafef.vn/fpt.chn"><img src="thumb.jpg" /></a>Doanh thu mảng công nghệ của FPT tăng trưởng 28%, ban lãnh đạo dự kiến chi trả cổ tức tiền mặt.]]></description>
      <pubDate>Sun, 18 Oct 2026 09:30:00 +0700</pubDate>
    </item>
    <item>
      <title><![CDATA[Khối ngoại bán ròng mạnh tại HPG và VCB trong phiên biến động]]></title>
      <link>https://cafef.vn/khoi-ngoai-ban-rong-hpg-vcb-67890.chn</link>
      <description><![CDATA[Áp lực bán gia tăng khiến HPG giảm 1.5%, trong khi VCB giữ giá tham chiếu.]]></description>
      <pubDate>Sat, 17 Oct 2026 15:45:00 +0700</pubDate>
    </item>
    <item>
      <title><![CDATA[Ngân hàng Nhà nước duy trì lãi suất điều hành ổn định hỗ trợ tăng trưởng]]></title>
      <link>https://cafef.vn/nhnn-duy-tri-lai-suat-dieu-hanh-11111.chn</link>
      <description><![CDATA[Mục tiêu kiểm soát lạm phát và ổn định tỷ giá được ưu tiên hàng đầu.]]></description>
      <pubDate>Fri, 16 Oct 2026 08:00:00 +0700</pubDate>
    </item>
    <item>
      <title><![CDATA[Tin trùng lặp về FPT]]></title>
      <link>https://cafef.vn/fpt-cong-bo-loi-nhuan-ky-luc-9-thang-12345.chn</link>
      <description><![CDATA[Bài viết trùng URL với bài đầu tiên.]]></description>
      <pubDate>Sun, 18 Oct 2026 09:30:00 +0700</pubDate>
    </item>
  </channel>
</rss>
"""


def test_strip_html_and_decode_entities():
    raw = '<p>Thị trường chứng khoán &amp; cổ phiếu <a href="#">FPT</a> tăng mạnh!</p>'
    cleaned = _strip_html(raw)
    assert "<p>" not in cleaned
    assert "<a" not in cleaned
    assert "&amp;" not in cleaned
    assert "FPT tăng mạnh!" in cleaned


def test_sanitize_xml_removes_stray_ampersands():
    bad_xml = b"<root><title>Doanh thu & Loi nhuan</title></root>"
    sanitized = _sanitize_xml(bad_xml)
    assert "&amp;" in sanitized
    assert "Doanh thu &amp; Loi nhuan" in sanitized


def test_extract_tickers_word_boundary():
    # True positives
    tickers = _extract_tickers("Cổ phiếu FPT và HPG bứt phá mạnh")
    assert "FPT" in tickers
    assert "HPG" in tickers

    # False positives check: substring shouldn't match
    negative_test = _extract_tickers("Công ty Cổ phần Thủy sản Thực phẩm sạch (không có ticker)")
    assert "FPT" not in negative_test
    assert "HPG" not in negative_test


def test_classify_article_heuristics():
    event_type, materiality, sentiment, severity = _classify_article(
        "FPT công bố lợi nhuận kỷ lục và chi trả cổ tức",
        "Tăng trưởng doanh thu 25%"
    )
    assert event_type == "Earnings"
    assert materiality == "MATERIAL"
    assert sentiment == "POSITIVE"
    assert severity >= 50.0

    m_type, m_mat, m_sent, _ = _classify_article(
        "Ngân hàng Nhà nước họp về lạm phát và tỷ giá",
        "Chính sách tiền tệ ổn định"
    )
    assert m_type == "Macro"
    assert m_mat == "INFORMATIONAL"
    assert m_sent == "NEUTRAL"


def test_parse_feed_xml_and_deduplicate():
    provider = FinancialNewsProvider()
    articles = provider.parse_feed_xml(SAMPLE_RSS_XML, publisher="CafeF", category="MARKET")

    assert len(articles) == 4  # parse_feed_xml parses all valid items; fetch_articles deduplicates
    first = articles[0]
    assert first["title"] == "FPT công bố lợi nhuận kỷ lục 9 tháng đầu năm, vượt kế hoạch"
    assert "FPT" in first["matched_tickers"]
    assert first["source"] == "CafeF"
    assert first["materiality"] == "MATERIAL"
    assert first["event_type"] == "Earnings"
    assert first["published_at"].year == 2026
    assert first["published_at"].month == 10

    second = articles[1]
    assert "HPG" in second["matched_tickers"]
    assert "VCB" in second["matched_tickers"]


def test_parse_feed_xml_handles_malformed_xml():
    provider = FinancialNewsProvider()
    articles = provider.parse_feed_xml("<unclosed><broken", publisher="CafeF")
    assert articles == []


def test_ingest_to_database_mocked(db_session):
    provider = FinancialNewsProvider()
    mock_articles = [
        {
            "title": "FPT đạt kỷ lục lợi nhuận mới",
            "url": "https://cafef.vn/fpt-ky-luc-999.chn",
            "snippet": "Mảng chuyển đổi số của FPT tăng trưởng vượt trội.",
            "source": "CafeF",
            "sourceName": "CafeF",
            "published_at": datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc),
            "event_type": "Earnings",
            "materiality": "MATERIAL",
            "sentiment": "POSITIVE",
            "severity": 65.0,
            "affected_sectors": ["FINANCE", "TECHNOLOGY"],
            "impacts": [{"entity_name": "FPT", "impact_type": "NEWS"}],
            "matched_tickers": ["FPT"],
            "category": "MARKET",
        }
    ]

    with patch.object(provider, "fetch_articles", return_value=mock_articles):
        result = provider.ingest_to_database(db_session, max_articles=5)

        assert result["status"] == "SUCCESS"
        assert result["records_valid"] == 1
        assert result["records_rejected"] == 0

        # Verify EventRecord in database
        event = db_session.query(EventRecord).filter(EventRecord.title.like("%FPT đạt kỷ lục%")).first()
        assert event is not None
        assert event.materiality == "MATERIAL"
        assert event.event_type == "Earnings"
        assert event.published_at.year == 2026
        assert event.published_at.month == 10
        assert event.published_at.day == 18
        assert event.published_at.hour == 10
        assert any(i.get("entity_name") == "FPT" for i in event.impacts)
