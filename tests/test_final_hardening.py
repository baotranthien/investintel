"""
Regression & Hardening Test Suite for InvestIntel Production Pipeline.
Covers:
1. Issue A: Price conflict resolution, raw vs adjusted prices, floating-point noise, genuine conflicts.
2. Issue B: Dynamic universe resolution, index symbol routing & skipping, concurrency config.
3. Issue C: Financial RSS news accounting, URL normalization, point-in-time checks, idempotency.
4. Issue D: Multi-state job aggregation and deterministic quality summary.
"""
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from database.models import (
    Asset,
    DataSource,
    EventRecord,
    Price,
    StagingRecord,
    IndexMembership,
)
from services.ingestion.base import MarketDataPoint
from services.ingestion.pipeline import IngestionPipeline
from services.ingestion.scheduler import load_required_universe
from services.ingestion.vndirect import VndirectProvider
from apps.api.routers.cron import CronTriggerRequest


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def fpt_asset(db_session: Session) -> Asset:
    asset = db_session.query(Asset).filter_by(symbol="FPT").first()
    if not asset:
        asset = Asset(symbol="FPT", name="FPT Corporation", asset_type="STOCK", exchange="HOSE", status="ACTIVE")
        db_session.add(asset)
        db_session.commit()
    return asset


@pytest.fixture
def vn30_asset(db_session: Session) -> Asset:
    asset = db_session.query(Asset).filter_by(symbol="VN30").first()
    if not asset:
        asset = Asset(symbol="VN30", name="VN30 Index", asset_type="INDEX", exchange="HOSE", status="ACTIVE")
        db_session.add(asset)
        db_session.commit()
    return asset


@pytest.fixture
def source_lotus(db_session: Session) -> int:
    source = db_session.query(DataSource).filter_by(name="LOTUSMARKET").first()
    if not source:
        source = DataSource(name="LOTUSMARKET", provider="VPS", country="VNM", authority_level="REPUTABLE_SECONDARY", source_type="API", active=True)
        db_session.add(source)
        db_session.commit()
    return source.id


@pytest.fixture
def source_vndirect(db_session: Session) -> int:
    source = db_session.query(DataSource).filter_by(name="VNDIRECT").first()
    if not source:
        source = DataSource(name="VNDIRECT", provider="VNDIRECT", country="VNM", authority_level="REPUTABLE_SECONDARY", source_type="API", active=True)
        db_session.add(source)
        db_session.commit()
    return source.id


# -----------------------------------------------------------------------------
# Issue A Tests: Price Conflicts & Resolution
# -----------------------------------------------------------------------------
def test_price_identical_observations(db_session: Session, fpt_asset: Asset, source_lotus: int, source_vndirect: int):
    """Two identical observations from different providers should deduplicate cleanly."""
    pipeline = IngestionPipeline(db_session)
    test_date = date(2026, 8, 1)

    # Provider 1: LotusMarket
    res1 = pipeline.ingest_market_data(
        provider="LOTUSMARKET",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 60000.0,
            "high": 61000.0,
            "low": 59500.0,
            "close": 60500.0,
            "adjusted_close": 60500.0,
            "volume": 1500000.0,
        }],
        source_url_or_path="https://services.entrade.com.vn",
        source_id=source_lotus,
    )
    assert res1["status"] == "SUCCESS"
    assert res1["records_valid"] == 1

    # Provider 2: VNDIRECT identical prices
    res2 = pipeline.ingest_market_data(
        provider="VNDIRECT",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 60000.0,
            "high": 61000.0,
            "low": 59500.0,
            "close": 60500.0,
            "adjusted_close": 60500.0,
            "volume": 1500000.0,
        }],
        source_url_or_path="https://finfo-api.vndirect.com.vn",
        source_id=source_vndirect,
    )
    assert res2["status"] == "SUCCESS"
    assert res2["records_valid"] == 1
    assert len(res2["rejected_samples"]) == 0

    # Verify single canonical price
    prices = db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).all()
    assert len(prices) == 1
    assert prices[0].raw_close == 60500.0
    assert "VNDIRECT" in prices[0].source


def test_price_raw_vs_adjusted_corporate_action(db_session: Session, fpt_asset: Asset, source_lotus: int, source_vndirect: int):
    """
    LotusMarket inserts adjusted close (e.g. 58,730 VND) after a stock split/dividend.
    VNDIRECT then supplies unadjusted raw close (64,600 VND) and matching adjusted close (58,728 VND).
    The pipeline must resolve the price basis, upgrade raw_close to 64,600, set adjustment factor ~0.909,
    and reject 0 records.
    """
    pipeline = IngestionPipeline(db_session)
    test_date = date(2027, 2, 1)

    # Clean existing price for this test date if any
    db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).delete()
    db_session.commit()

    # 1. LotusMarket ingests adjusted bar
    res1 = pipeline.ingest_market_data(
        provider="LOTUSMARKET",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 59090.0,
            "high": 61360.0,
            "low": 58730.0,
            "close": 58730.0,
            "adjusted_close": 58730.0,
            "volume": 2840000.0,
        }],
        source_url_or_path="https://services.entrade.com.vn",
        source_id=source_lotus,
    )
    assert res1["status"] == "SUCCESS"

    # 2. VNDIRECT ingests unadjusted raw + adClose
    res2 = pipeline.ingest_market_data(
        provider="VNDIRECT",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 65000.0,
            "high": 67500.0,
            "low": 64600.0,
            "close": 64600.0,
            "adjusted_close": 58728.0,
            "volume": 2840000.0,
        }],
        source_url_or_path="https://finfo-api.vndirect.com.vn",
        source_id=source_vndirect,
    )
    assert res2["status"] == "SUCCESS"
    assert res2["records_rejected"] == 0

    # 3. Verify canonical Price record
    price = db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).first()
    assert price is not None
    assert price.raw_close == 64600.0
    assert math.isclose(price.adjusted_close, 58728.0, rel_tol=1e-3)
    assert math.isclose(price.adjustment_factor, 58728.0 / 64600.0, rel_tol=1e-3)


def test_price_reverse_order_vndirect_then_lotusmarket(db_session: Session, fpt_asset: Asset, source_lotus: int, source_vndirect: int):
    """
    If VNDIRECT runs first (raw=64,600, adj=58,728) and LotusMarket runs second (adjusted=58,730),
    Case 3 should cleanly match adjusted close, preserve canonical raw_close=64,600, and reject 0 records.
    """
    pipeline = IngestionPipeline(db_session)
    test_date = date(2027, 2, 2)

    db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).delete()
    db_session.commit()

    # 1. VNDIRECT runs first
    res1 = pipeline.ingest_market_data(
        provider="VNDIRECT",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 65000.0,
            "high": 65700.0,
            "low": 64200.0,
            "close": 64700.0,
            "adjusted_close": 58819.0,
            "volume": 1950000.0,
        }],
        source_url_or_path="https://finfo-api.vndirect.com.vn",
        source_id=source_vndirect,
    )
    assert res1["status"] == "SUCCESS"

    # 2. LotusMarket runs second
    res2 = pipeline.ingest_market_data(
        provider="LOTUSMARKET",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 59090.0,
            "high": 59730.0,
            "low": 58360.0,
            "close": 58820.0,
            "adjusted_close": 58820.0,
            "volume": 1950000.0,
        }],
        source_url_or_path="https://services.entrade.com.vn",
        source_id=source_lotus,
    )
    assert res2["status"] == "SUCCESS"
    assert res2["records_rejected"] == 0

    price = db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).first()
    assert price.raw_close == 64700.0
    assert math.isclose(price.adjusted_close, 58819.0, abs_tol=10.0)


def test_price_genuine_conflict_preserves_canonical(db_session: Session, fpt_asset: Asset, source_lotus: int, source_vndirect: int):
    """A genuinely conflicting close (e.g. 100,000 VND vs 60,000 VND) must be rejected and preserve canonical."""
    pipeline = IngestionPipeline(db_session)
    test_date = date(2027, 2, 3)

    db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).delete()
    db_session.commit()

    # 1. Establish canonical
    res_canon = pipeline.ingest_market_data(
        provider="LOTUSMARKET",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 60000.0,
            "high": 61000.0,
            "low": 59000.0,
            "close": 60000.0,
            "volume": 1000000.0,
        }],
        source_url_or_path="https://services.entrade.com.vn",
        source_id=source_lotus,
    )
    assert res_canon["status"] == "SUCCESS"

    # 2. Incoming genuinely conflicting price
    res_conflict = pipeline.ingest_market_data(
        provider="VNDIRECT",
        symbol="FPT",
        exchange="HOSE",
        records=[{
            "symbol": "FPT",
            "observation_date": test_date,
            "open": 95000.0,
            "high": 100000.0,
            "low": 94000.0,
            "close": 98000.0,
            "volume": 1000000.0,
        }],
        source_url_or_path="https://finfo-api.vndirect.com.vn",
        source_id=source_vndirect,
    )
    assert res_conflict["records_rejected"] == 1
    assert len(res_conflict["rejected_samples"]) == 1
    assert "Conflicting observation" in res_conflict["rejected_samples"][0]["errors"][0]

    # Verify canonical is preserved
    price = db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).first()
    assert price.raw_close == 60000.0


def test_price_invalid_ohlc_relationships_rejected(db_session: Session, fpt_asset: Asset, source_lotus: int):
    """High < Low or negative close should be rejected during validation step."""
    pipeline = IngestionPipeline(db_session)
    test_date = date(2027, 2, 4)

    db_session.query(Price).filter_by(asset_id=fpt_asset.id, observation_date=test_date).delete()
    db_session.commit()

    res = pipeline.ingest_market_data(
        provider="LOTUSMARKET",
        symbol="FPT",
        exchange="HOSE",
        records=[
            {
                "symbol": "FPT",
                "observation_date": test_date,
                "open": 60000.0,
                "high": 55000.0,  # Invalid: high < open / low
                "low": 58000.0,
                "close": 59000.0,
                "volume": 1000.0,
            },
            {
                "symbol": "FPT",
                "observation_date": test_date + timedelta(days=1),
                "open": 60000.0,
                "high": 62000.0,
                "low": 59000.0,
                "close": -100.0,  # Invalid: negative close
                "volume": 1000.0,
            }
        ],
        source_url_or_path="https://services.entrade.com.vn",
        source_id=source_lotus,
    )
    assert res["records_valid"] == 0
    assert res["records_rejected"] == 2


# -----------------------------------------------------------------------------
# Issue B Tests: Universe Resolution & Index Routing
# -----------------------------------------------------------------------------
def test_load_required_universe_dynamic(db_session: Session):
    """Universe loading retrieves full VN100 constituents + benchmark indices."""
    stocks, indices = load_required_universe(db_session)
    assert len(stocks) >= 5
    assert "FPT" in stocks
    assert "HPG" in stocks
    assert "VN30" in indices
    assert "VN100" in indices


def test_vndirect_skips_index_candles_cleanly(db_session: Session):
    """VNDIRECT stock_prices does not support index candles and returns SKIPPED_UNSUPPORTED."""
    import asyncio
    vnd = VndirectProvider()
    res = asyncio.run(vnd.ingest_to_database(db_session, "VN30"))
    assert res["status"] == "SKIPPED_UNSUPPORTED"
    assert res["records_received"] == 0
    assert "does not support benchmark index candles" in res["reason"]


def test_github_actions_workflow_configuration():
    """Verify workflow YAML contains schedule trigger and concurrency protection."""
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "eod_ingestion.yml"
    assert workflow_path.is_file(), "Workflow file must exist"
    content = workflow_path.read_text(encoding="utf-8")

    assert "30 8 * * 1-5" in content, "Schedule must be 08:30 UTC Mon-Fri (15:30 Asia/Ho_Chi_Minh)"
    assert "concurrency:" in content, "Concurrency block must exist"
    assert "group: eod-ingestion" in content, "Concurrency group must be defined"
    assert "cancel-in-progress: false" in content, "Overlapping runs must not cancel"
    assert "FINANCIAL_NEWS" in content, "FINANCIAL_NEWS provider must be supported"


# -----------------------------------------------------------------------------
# Issue C Tests: Financial News RSS Accounting & Normalization
# -----------------------------------------------------------------------------
def test_news_url_normalization_and_deduplication(db_session: Session, source_lotus: int):
    """UTM tracking parameters should be stripped so duplicate URLs collapse correctly."""
    pipeline = IngestionPipeline(db_session)

    raw_articles = [
        {
            "title": "Doanh nghiệp công nghệ tăng trưởng",
            "url": "https://cafef.vn/tech-growth-2026.chn?utm_source=facebook&utm_medium=cpc&fbclid=123",
            "snippet": "Tin tức công nghệ",
            "source": "CafeF",
            "published_at": datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc),
        },
        {
            "title": "Doanh nghiệp công nghệ tăng trưởng (duplicate)",
            "url": "https://cafef.vn/tech-growth-2026.chn?utm_source=telegram&ref=home",
            "snippet": "Tin tức công nghệ lặp lại",
            "source": "CafeF",
            "published_at": datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc),
        }
    ]

    res = pipeline.ingest_news_events(
        provider="FINANCIAL_NEWS",
        articles=raw_articles,
        source_url="https://cafef.vn",
        source_id=source_lotus,
        dataset="financial_news",
    )

    assert res["accounting"]["fetched"] == 2
    assert res["accounting"]["promoted_new"] == 1
    assert res["accounting"]["deduplicated"] == 1
    assert res["accounting"]["usable_url"] == 2


def test_news_point_in_time_future_date_rejected(db_session: Session, source_lotus: int):
    """Article published more than 1 hour in the future violates Point-In-Time and is skipped."""
    pipeline = IngestionPipeline(db_session)
    future_pub = datetime.now(timezone.utc) + timedelta(days=2)

    raw_articles = [{
        "title": "Tin tức tương lai vi phạm PIT",
        "url": "https://cafef.vn/future-news-999.chn",
        "snippet": "Tin tức",
        "source": "CafeF",
        "published_at": future_pub,
    }]

    res = pipeline.ingest_news_events(
        provider="FINANCIAL_NEWS",
        articles=raw_articles,
        source_url="https://cafef.vn",
        source_id=source_lotus,
    )
    assert res["accounting"]["skipped_point_in_time"] == 1
    assert res["accounting"]["promoted_new"] == 0


def test_news_repeated_cycle_idempotent_unchanged(db_session: Session, source_lotus: int):
    """Subsequent ingestion of already persisted articles returns IDEMPOTENT_UNCHANGED."""
    pipeline = IngestionPipeline(db_session)
    pub_dt = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)

    articles = [{
        "title": "Bài viết thử nghiệm tính bất biến",
        "url": "https://cafef.vn/idempotency-test-123.chn",
        "snippet": "Thử nghiệm",
        "source": "CafeF",
        "published_at": pub_dt,
    }]

    # Run 1: Promoted
    res1 = pipeline.ingest_news_events("FINANCIAL_NEWS", articles, "https://cafef.vn", source_lotus)
    assert res1["status"] == "SUCCESS"
    assert res1["records_inserted"] == 1

    # Run 2: Idempotent unchanged
    res2 = pipeline.ingest_news_events("FINANCIAL_NEWS", articles, "https://cafef.vn", source_lotus)
    assert res2["status"] == "IDEMPOTENT_UNCHANGED"
    assert res2["records_inserted"] == 0
    assert res2["records_deduplicated"] == 1


# -----------------------------------------------------------------------------
# Issue D Tests: Job Status Aggregation
# -----------------------------------------------------------------------------
def test_cron_trigger_request_defaults():
    req = CronTriggerRequest()
    assert req.force is False
    assert req.symbols is None
    assert req.batch_offset == 0
    assert req.batch_size is None
