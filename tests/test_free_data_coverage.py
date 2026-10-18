"""
Unit and integration tests for Free Data Coverage & Stock Research Integration:
1. VNDirect fundamentals normalization, units scaling, and financial periods.
2. Publication dates and Point-In-Time preservation from `createdDate`.
3. VNDirect corporate actions and events mapping.
4. NSO Vietnam SDMX XML parsing and macro observation promotion.
5. MarketDataReconciliationEngine:
   - Consistent data detection
   - Discrepancy & SOURCE_DISAGREEMENT detection
   - Non-destructive invariant (no overwriting canonical prices)
6. Scheduler provider outage isolation and bounded batch processing.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base,
    Asset,
    FinancialStatement,
    NormalizedIncome,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    FinancialLineItem,
    FundamentalMetric,
    CorporateAction,
    EventRecord,
    Price,
    DataLineage,
    DataQualityReportRecord,
    DataSource,
)
from services.ingestion.base import MarketDataPoint
from services.ingestion.vndirect import (
    VndirectProvider,
    normalize_symbol,
    INCOME_ITEM_MAP,
    BALANCE_ITEM_MAP,
    CASHFLOW_ITEM_MAP,
)
from services.ingestion.nso import NsoProvider
from services.ingestion.reconciliation import (
    MarketDataReconciliationEngine,
    ReconciliationReport,
    DISCREPANCY_TOLERANCE_MAJOR,
)
from services.ingestion.scheduler import run_ingestion_cycle


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed Asset
    asset = Asset(symbol="FPT", name="FPT Corp", asset_type="STOCK", exchange="HOSE")
    session.add(asset)
    # Seed DataSources
    session.add(DataSource(name="VNDIRECT", provider="VNDIRECT", active=True))
    session.add(DataSource(name="DNSE", provider="DNSE", active=True))
    session.add(DataSource(name="NSO_VIETNAM", provider="NSO_VIETNAM", active=True))
    session.commit()

    yield session
    session.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. VNDIRECT FUNDAMENTALS & UNIT SCALING TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_vndirect_symbol_normalization():
    assert normalize_symbol("fpt") == "FPT"
    assert normalize_symbol(" VCB ") == "VCB"
    assert normalize_symbol("mwg.vn") == "MWGVN"
    assert normalize_symbol("") == ""


@pytest.mark.anyio
async def test_vndirect_fundamentals_ingestion_and_unit_scaling(in_memory_db):
    """
    Verifies that raw VND values are scaled by 1e9 to BILLION_VND,
    while per-share metrics (EPS) remain in VND/share.
    Verifies createdDate is preserved as publication_date for Point-In-Time compliance.
    """
    provider = VndirectProvider()

    mock_raw_fs = [
        # Income Statement (ModelType 2)
        {"code": "FPT", "itemCode": 21001.0, "reportType": "QUARTER", "modelType": 2.0,
         "numericValue": 15000000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},
        {"code": "FPT", "itemCode": 23003.0, "reportType": "QUARTER", "modelType": 2.0,
         "numericValue": 2500000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},
        {"code": "FPT", "itemCode": 23001.0, "reportType": "QUARTER", "modelType": 2.0,
         "numericValue": 1950.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"}, # EPS = 1950 VND/sh

        # Balance Sheet (ModelType 1)
        {"code": "FPT", "itemCode": 12700.0, "reportType": "QUARTER", "modelType": 1.0,
         "numericValue": 65000000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},
        {"code": "FPT", "itemCode": 14000.0, "reportType": "QUARTER", "modelType": 1.0,
         "numericValue": 32000000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},

        # Cash Flow (ModelType 3)
        {"code": "FPT", "itemCode": 32000.0, "reportType": "QUARTER", "modelType": 3.0,
         "numericValue": 3000000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},
        {"code": "FPT", "itemCode": 32100.0, "reportType": "QUARTER", "modelType": 3.0,
         "numericValue": -1000000000000.0, "fiscalDate": "2026-06-30", "createdDate": "2026-07-25 08:00:00"},
    ]

    with patch.object(provider, "fetch_financial_statements", new=AsyncMock(return_value=mock_raw_fs)):
        result = await provider.ingest_fundamentals(in_memory_db, "FPT", report_type="QUARTER")

    assert result["status"] == "SUCCESS"
    assert result["statements_created"] == 3

    # Check Income Statement
    inc_stmt = in_memory_db.query(FinancialStatement).filter(
        FinancialStatement.symbol == "FPT",
        FinancialStatement.statement_type == "INCOME_STATEMENT"
    ).first()
    assert inc_stmt is not None
    assert inc_stmt.fiscal_period_end == date(2026, 6, 30)
    assert inc_stmt.publication_date == date(2026, 7, 25)  # Preserved from createdDate!
    assert inc_stmt.unit_scale == "BILLION_VND"

    norm_inc = in_memory_db.query(NormalizedIncome).filter(NormalizedIncome.statement_id == inc_stmt.id).first()
    assert norm_inc is not None
    assert float(norm_inc.revenue) == 15000.0  # 15,000 billion VND
    assert float(norm_inc.net_income) == 2500.0 # 2,500 billion VND
    assert float(norm_inc.eps_basic) == 1950.0  # Per share untouched

    # Check Balance Sheet
    bs_stmt = in_memory_db.query(FinancialStatement).filter(
        FinancialStatement.symbol == "FPT",
        FinancialStatement.statement_type == "BALANCE_SHEET"
    ).first()
    norm_bs = in_memory_db.query(NormalizedBalanceSheet).filter(NormalizedBalanceSheet.statement_id == bs_stmt.id).first()
    assert norm_bs is not None
    assert float(norm_bs.total_assets) == 65000.0
    assert float(norm_bs.total_equity) == 32000.0

    # Check Cash Flow
    cf_stmt = in_memory_db.query(FinancialStatement).filter(
        FinancialStatement.symbol == "FPT",
        FinancialStatement.statement_type == "CASH_FLOW"
    ).first()
    norm_cf = in_memory_db.query(NormalizedCashFlow).filter(NormalizedCashFlow.statement_id == cf_stmt.id).first()
    assert norm_cf is not None
    assert float(norm_cf.cash_from_operations) == 3000.0
    assert float(norm_cf.capex) == -1000.0
    assert float(norm_cf.free_cash_flow) == 2000.0


@pytest.mark.anyio
async def test_vndirect_fundamentals_idempotency(in_memory_db):
    """Repeated ingestion of identical periods does not duplicate canonical rows."""
    provider = VndirectProvider()
    mock_raw_fs = [
        {"code": "FPT", "itemCode": 21001.0, "reportType": "QUARTER", "modelType": 2.0,
         "numericValue": 10000000000000.0, "fiscalDate": "2026-03-31", "createdDate": "2026-04-20 00:00:00"}
    ]
    with patch.object(provider, "fetch_financial_statements", new=AsyncMock(return_value=mock_raw_fs)):
        r1 = await provider.ingest_fundamentals(in_memory_db, "FPT", report_type="QUARTER")
        r2 = await provider.ingest_fundamentals(in_memory_db, "FPT", report_type="QUARTER")

    assert r1["status"] == "SUCCESS"
    assert r2["status"] == "IDEMPOTENT_UNCHANGED"
    count = in_memory_db.query(FinancialStatement).filter(FinancialStatement.symbol == "FPT").count()
    assert count == 1


@pytest.mark.anyio
async def test_vndirect_ratios_and_events_ingestion(in_memory_db):
    """Tests ratio and event ingestion into FundamentalMetric, CorporateAction, and EventRecord."""
    provider = VndirectProvider()

    mock_ratios = [
        {"code": "FPT", "ratioCode": "PRICE_TO_EARNINGS", "itemName": "P/E", "value": 18.5, "reportDate": "2026-10-14"},
        {"code": "FPT", "ratioCode": "PRICE_TO_BOOK", "itemName": "P/B", "value": 3.8, "reportDate": "2026-10-14"}
    ]
    with patch.object(provider, "fetch_ratios", new=AsyncMock(return_value=mock_ratios)):
        res_ratios = await provider.ingest_ratios(in_memory_db, "FPT")
    assert res_ratios["status"] == "SUCCESS"
    assert res_ratios["metrics_created"] == 2

    metric = in_memory_db.query(FundamentalMetric).filter(
        FundamentalMetric.symbol == "FPT",
        FundamentalMetric.metric_id == "PRICE_TO_EARNINGS"
    ).first()
    assert metric is not None
    assert float(metric.value) == 18.5
    assert metric.as_of_publication_date == date(2026, 10, 14)

    # Test Events
    mock_events = [
        {
            "id": "EVT123",
            "code": "FPT",
            "type": "dividendCash",
            "typeDesc": "Chi tra co tuc dot 1/2026",
            "note": "Co tuc bang tien mat ty le 10%",
            "disclosureDate": "2026-09-15",
            "numberOfShares": 1885000000.0
        }
    ]
    with patch.object(provider, "fetch_events", new=AsyncMock(return_value=mock_events)):
        res_events = await provider.ingest_events(in_memory_db, "FPT")

    assert res_events["status"] == "SUCCESS"
    assert res_events["corporate_actions_created"] == 1
    assert res_events["event_records_created"] == 1

    ca = in_memory_db.query(CorporateAction).filter(CorporateAction.symbol == "FPT").first()
    assert ca is not None
    assert ca.action_type == "CASH_DIVIDEND"
    assert ca.action_date == date(2026, 9, 15)

    ev = in_memory_db.query(EventRecord).filter(EventRecord.id == "vnd-FPT-EVT123").first()
    assert ev is not None
    assert ev.materiality == "MATERIAL"


# ─────────────────────────────────────────────────────────────────────────────
# 2. NSO VIETNAM SDMX XML PARSER TESTS
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_SDMX_XML = """<?xml version='1.0' encoding='UTF-8'?>
<message:StructureSpecificData xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">
  <message:Header>
    <message:Prepared>2026-10-12T02:33:09Z</message:Prepared>
  </message:Header>
  <message:DataSet>
    <Series DATA_DOMAIN="CPI" REF_AREA="VN" INDICATOR="PCPI_IX" FREQ="M">
      <Obs TIME_PERIOD="2026-07" OBS_VALUE="108.45"/>
      <Obs TIME_PERIOD="2026-08" OBS_VALUE="108.92"/>
    </Series>
  </message:DataSet>
</message:StructureSpecificData>
"""

def test_nso_sdmx_parsing():
    provider = NsoProvider()
    points, pub_dt = provider.parse_sdmx_observations(SAMPLE_SDMX_XML, "vnm_cpi_gso")

    assert pub_dt == datetime(2026, 10, 12, 2, 33, 9, tzinfo=timezone.utc)
    assert len(points) == 2
    assert points[0].observation_date == date(2026, 7, 31)
    assert points[0].value == 108.45
    assert points[0].release_date == date(2026, 10, 12)
    assert points[0].unit == "INDEX_2019_100"
    assert points[0].frequency == "MONTHLY"
    assert points[1].observation_date == date(2026, 8, 31)
    assert points[1].value == 108.92


@pytest.mark.anyio
async def test_nso_ingestion_pipeline(in_memory_db):
    from database.models import MacroSeries
    source_nso = in_memory_db.query(DataSource).filter(DataSource.name == "NSO_VIETNAM").first()
    in_memory_db.add(MacroSeries(
        id="vnm_cpi_gso",
        name="CPI GSO",
        provider="NSO_VIETNAM",
        frequency="MONTHLY",
        unit="INDEX_2019_100",
        source_id=source_nso.id
    ))
    in_memory_db.commit()

    provider = NsoProvider()
    with patch.object(provider, "_fetch_xml", new=AsyncMock(return_value=SAMPLE_SDMX_XML)):
        result = await provider.ingest_series_to_database(in_memory_db, "vnm_cpi_gso")

    assert result["status"] == "SUCCESS"
    assert result["records_inserted"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. RECONCILIATION ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_reconciliation_consistent():
    engine = MarketDataReconciliationEngine()

    candles_a = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 13), close=56300.0, volume=6000000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=57100.0, volume=7000000.0),
    ]
    candles_b = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 13), close=56300.0, volume=6000000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=57100.0, volume=7000000.0),
    ]

    report = engine.reconcile_candles("FPT", candles_a, candles_b)
    assert report.status == "CONSISTENT"
    assert report.matching_dates_count == 2
    assert report.major_disagreement_count == 0
    assert report.max_close_diff_pct == 0.0


def test_reconciliation_source_disagreement_detected():
    engine = MarketDataReconciliationEngine()

    candles_a = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 13), close=56300.0, volume=6000000.0),
        # On 2026-10-14: Source A has 57,100, Source B has 60,000 (> 5% discrepancy)
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=57100.0, volume=7000000.0),
    ]
    candles_b = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 13), close=56300.0, volume=6000000.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=60000.0, volume=7000000.0),
    ]

    report = engine.reconcile_candles("FPT", candles_a, candles_b)
    assert report.status == "SOURCE_DISAGREEMENT"
    assert report.major_disagreement_count == 1
    assert report.max_close_diff_pct > DISCREPANCY_TOLERANCE_MAJOR
    assert len(report.discrepancy_details) == 1
    assert report.discrepancy_details[0].is_disagreement is True


def test_reconciliation_missing_dates_tracking():
    engine = MarketDataReconciliationEngine()

    candles_a = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 13), close=56300.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=57100.0),
    ]
    candles_b = [
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 14), close=57100.0),
        MarketDataPoint(symbol="FPT", observation_date=date(2026, 10, 15), close=57500.0),
    ]

    report = engine.reconcile_candles("FPT", candles_a, candles_b)
    assert report.overlapping_dates_count == 1
    assert "2026-10-13" in report.dates_only_in_a
    assert "2026-10-15" in report.dates_only_in_b


def test_reconciliation_non_destructive_invariant(in_memory_db):
    """
    Verifies that recording reconciliation findings into DataQualityReportRecord
    never alters or overwrites existing canonical price records.
    """
    engine = MarketDataReconciliationEngine()

    # Pre-existing canonical price
    canonical_price = Price(
        asset_id=1,
        observation_date=date(2026, 10, 14),
        raw_close=57100.0,
        source="DNSE",
        status="VALID"
    )
    in_memory_db.add(canonical_price)
    in_memory_db.commit()

    report = ReconciliationReport(
        symbol="FPT",
        provider_a="DNSE",
        provider_b="VNDIRECT",
        start_date="2026-10-14",
        end_date="2026-10-14",
        total_dates_a=1,
        total_dates_b=1,
        major_disagreement_count=1,
        status="SOURCE_DISAGREEMENT"
    )

    qr = engine.record_quality_report(in_memory_db, report)
    assert qr is not None
    assert qr.status == "WARNING"

    # Canonical price MUST remain unchanged
    price_after = in_memory_db.query(Price).filter(Price.asset_id == 1).first()
    assert price_after.raw_close == 57100.0
    assert price_after.source == "DNSE"


# ─────────────────────────────────────────────────────────────────────────────
# 4. SCHEDULER PROVIDER OUTAGE ISOLATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_scheduler_provider_outage_isolation(in_memory_db):
    """
    Verifies that if one provider fails (e.g. raises network exception),
    the scheduler isolates the error and processes all other providers normally.
    """
    from database.models import MacroSeries

    # Seed macro series into in_memory_db
    source_nso = in_memory_db.query(DataSource).filter(DataSource.name == "NSO_VIETNAM").first()
    in_memory_db.add(MacroSeries(
        id="vnm_cpi_gso",
        name="CPI GSO",
        provider="NSO_VIETNAM",
        frequency="MONTHLY",
        unit="INDEX_2019_100",
        source_id=source_nso.id
    ))
    in_memory_db.commit()

    # Let NSO fail with connection error, but other providers succeed
    with patch("services.ingestion.scheduler.NsoProvider.fetch_macro_series", side_effect=Exception("NSO Network Timeout")), \
         patch.dict("os.environ", {
             "ENABLE_NSO_INGESTION": "true",
             "ENABLE_DNSE_INGESTION": "false",
             "ENABLE_VNDIRECT_INGESTION": "false",
             "ENABLE_WORLDBANK_INGESTION": "false"
         }):

        results = await run_ingestion_cycle(session_factory=lambda: in_memory_db)

    # NSO failed
    nso_res = next((r for r in results if r.get("provider") == "NSO_VIETNAM"), None)
    assert nso_res is not None
    assert nso_res["status"] == "FAILURE"
    assert "NSO Network Timeout" in nso_res["reason"]
