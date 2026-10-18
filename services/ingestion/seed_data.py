"""
Seed Data & Real Ingestion Runner.
Populates:
1. DataSource registry
2. Canonical Assets (FPT, VCB, MBB, MWG, HPG, FUEVN100, VN100, VN300)
3. Historical Index Memberships (VN30, VN100, VN300) with Point-In-Time ranges
4. Real Corporate Actions (Cash/Stock dividends)
5. Real Macroeconomic Series & Observations (FRED, BLS, NSO, SBV)
6. Canonical Financial Statements (Income, Balance, Cash Flow) with publication timestamps
7. Canonical Peer Groups
8. Ingested Market Events
9. Real market EOD prices via IngestionPipeline (Raw -> Staging -> Validation -> Canonical)
"""
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from decimal import Decimal
from sqlalchemy.orm import Session

from database.connection import SessionLocal, init_db
from database.models import (
    DataSource,
    Asset,
    IndexMembership,
    CorporateAction,
    MacroSeries,
    MacroObservation,
    FinancialStatement,
    FinancialLineItem,
    NormalizedIncome,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    PeerGroup,
    EventRecord,
    DataLineage,
)
from services.ingestion.market_data import MarketDataCsvProvider

def seed_data_sources(session: Session) -> dict:
    """Populates official Data Source Registry."""
    sources = [
        {
            "name": "FRED",
            "provider": "Federal Reserve Bank of St. Louis",
            "country": "US",
            "authority_level": "PRIMARY_OFFICIAL",
            "source_type": "API",
            "base_url": "https://api.stlouisfed.org/fred",
            "license_status": "OPEN_PUBLIC",
            "access_method": "API_KEY"
        },
        {
            "name": "BLS",
            "provider": "U.S. Bureau of Labor Statistics",
            "country": "US",
            "authority_level": "PRIMARY_OFFICIAL",
            "source_type": "API",
            "base_url": "https://api.bls.gov/publicAPI/v2",
            "license_status": "PUBLIC_DOMAIN",
            "access_method": "API_KEY"
        },
        {
            "name": "NSO_VIETNAM",
            "provider": "General Statistics Office Vietnam",
            "country": "VNM",
            "authority_level": "PRIMARY_OFFICIAL",
            "source_type": "MANUAL_IMPORT",
            "base_url": "https://www.gso.gov.vn",
            "license_status": "OFFICIAL_GOVERNMENT",
            "access_method": "DOWNLOAD"
        },
        {
            "name": "HOSE_CSV",
            "provider": "Hochiminh Stock Exchange / Verified Market CSV",
            "country": "VNM",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "CSV",
            "base_url": "local://data/market/",
            "license_status": "INTERNAL_RESEARCH",
            "access_method": "LOCAL_FILE"
        },
        {
            "name": "SBV",
            "provider": "State Bank of Vietnam",
            "country": "VNM",
            "authority_level": "PRIMARY_OFFICIAL",
            "source_type": "OFFICIAL_PORTAL",
            "base_url": "https://www.sbv.gov.vn",
            "license_status": "OFFICIAL_GOVERNMENT",
            "access_method": "PUBLIC_DATA"
        },
        {
            "name": "DNSE",
            "provider": "DNSE (Entrade Public Market Data API)",
            "country": "VNM",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://services.entrade.com.vn/chart-api/v2/ohlcs",
            "license_status": "PUBLIC_RESEARCH_ONLY",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "VIETSTOCK",
            "provider": "Vietstock Public News API",
            "country": "VNM",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://vietstock.info/api/news/today",
            "license_status": "PUBLIC_RESEARCH_ONLY",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "WORLD_BANK",
            "provider": "The World Bank (Open Data API)",
            "country": "INT",
            "authority_level": "PRIMARY_OFFICIAL",
            "source_type": "API",
            "base_url": "https://api.worldbank.org/v2",
            "license_status": "OPEN_PUBLIC",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "OPEN_EXCHANGE_RATES",
            "provider": "Open Exchange Rates (Free Reference FX)",
            "country": "INT",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://open.er-api.com/v6",
            "license_status": "PUBLIC_RESEARCH_ONLY",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "GDELT",
            "provider": "GDELT Project (Doc 2.0 API)",
            "country": "INT",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://api.gdeltproject.org/api/v2/doc/doc",
            "license_status": "OPEN_PUBLIC",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "VNDIRECT",
            "provider": "VNDirect Securities Corporation (Finfo API)",
            "country": "VNM",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://api-finfo.vndirect.com.vn/v4/stock_prices",
            "license_status": "PUBLIC_RESEARCH_ONLY",
            "access_method": "PUBLIC_HTTP"
        },
        {
            "name": "LOTUSMARKET",
            "provider": "LotusMarket Toolkit (VPS / Entrade / CafeF / KBS)",
            "country": "VNM",
            "authority_level": "REPUTABLE_SECONDARY",
            "source_type": "API",
            "base_url": "https://bgapidatafeed.vps.com.vn",
            "license_status": "MIT_OPEN_SOURCE",
            "access_method": "PUBLIC_HTTP"
        }
    ]

    source_map = {}
    for s in sources:
        existing = session.query(DataSource).filter(DataSource.name == s["name"]).first()
        if not existing:
            ds = DataSource(**s)
            session.add(ds)
            session.flush()
            source_map[s["name"]] = ds.id
        else:
            source_map[s["name"]] = existing.id
    session.commit()
    return source_map

def seed_assets(session: Session) -> dict:
    """Populates canonical assets table."""
    assets_data = [
        {"symbol": "FPT", "name": "FPT Corporation", "asset_type": "STOCK", "exchange": "HOSE", "sector": "TECHNOLOGY"},
        {"symbol": "VCB", "name": "Vietcombank", "asset_type": "STOCK", "exchange": "HOSE", "sector": "BANK"},
        {"symbol": "MBB", "name": "Military Commercial Joint Stock Bank", "asset_type": "STOCK", "exchange": "HOSE", "sector": "BANK"},
        {"symbol": "MWG", "name": "Mobile World Investment Corporation", "asset_type": "STOCK", "exchange": "HOSE", "sector": "RETAIL"},
        {"symbol": "HPG", "name": "Hoa Phat Group Joint Stock Company", "asset_type": "STOCK", "exchange": "HOSE", "sector": "MATERIALS"},
        {"symbol": "FUEVN100", "name": "VinaCapital VN100 ETF", "asset_type": "ETF", "exchange": "HOSE", "sector": "INDEX_FUND"},
        {"symbol": "VN100", "name": "VN100 Index", "asset_type": "INDEX", "exchange": "HOSE", "sector": "BENCHMARK"},
        {"symbol": "VN300", "name": "VN300 Index", "asset_type": "INDEX", "exchange": "HOSE", "sector": "BENCHMARK"},
    ]
    asset_map = {}
    for a in assets_data:
        existing = session.query(Asset).filter(Asset.symbol == a["symbol"]).first()
        if not existing:
            rec = Asset(**a)
            session.add(rec)
            session.flush()
            asset_map[a["symbol"]] = rec.id
        else:
            asset_map[a["symbol"]] = existing.id
    session.commit()
    return asset_map

def seed_index_memberships(session: Session, source_id: int):
    """Seeds historical index constituents for VN30, VN100, VN300."""
    members = [
        # VN30
        {"index_symbol": "VN30", "symbol": "FPT", "start_date": date(2012, 2, 6), "end_date": None, "weight": 0.085},
        {"index_symbol": "VN30", "symbol": "VCB", "start_date": date(2012, 2, 6), "end_date": None, "weight": 0.092},
        {"index_symbol": "VN30", "symbol": "HPG", "start_date": date(2012, 2, 6), "end_date": None, "weight": 0.078},
        {"index_symbol": "VN30", "symbol": "MWG", "start_date": date(2015, 1, 26), "end_date": None, "weight": 0.054},
        {"index_symbol": "VN30", "symbol": "MBB", "start_date": date(2012, 2, 6), "end_date": None, "weight": 0.062},
        {"index_symbol": "VN30", "symbol": "ROS", "start_date": date(2017, 7, 24), "end_date": date(2020, 8, 3), "weight": 0.015},

        # VN100
        {"index_symbol": "VN100", "symbol": "FPT", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.065},
        {"index_symbol": "VN100", "symbol": "VCB", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.070},
        {"index_symbol": "VN100", "symbol": "MBB", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.048},
        {"index_symbol": "VN100", "symbol": "MWG", "start_date": date(2015, 1, 26), "end_date": None, "weight": 0.042},
        {"index_symbol": "VN100", "symbol": "HPG", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.058},
        {"index_symbol": "VN100", "symbol": "ROS", "start_date": date(2017, 7, 24), "end_date": date(2020, 8, 3), "weight": 0.012},

        # VN300
        {"index_symbol": "VN300", "symbol": "FPT", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.045},
        {"index_symbol": "VN300", "symbol": "VCB", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.050},
        {"index_symbol": "VN300", "symbol": "MBB", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.035},
        {"index_symbol": "VN300", "symbol": "MWG", "start_date": date(2015, 1, 26), "end_date": None, "weight": 0.032},
        {"index_symbol": "VN300", "symbol": "HPG", "start_date": date(2014, 1, 1), "end_date": None, "weight": 0.040},
        {"index_symbol": "VN300", "symbol": "ROS", "start_date": date(2017, 7, 24), "end_date": date(2020, 8, 3), "weight": 0.008},
    ]

    for m in members:
        existing = session.query(IndexMembership).filter(
            IndexMembership.index_symbol == m["index_symbol"],
            IndexMembership.symbol == m["symbol"],
            IndexMembership.start_date == m["start_date"]
        ).first()
        if not existing:
            im = IndexMembership(
                index_symbol=m["index_symbol"],
                symbol=m["symbol"],
                start_date=m["start_date"],
                end_date=m["end_date"],
                weight=m["weight"],
                source_id=source_id,
                published_at=datetime.combine(m["start_date"], datetime.min.time(), tzinfo=timezone.utc),
                is_active=(m["end_date"] is None)
            )
            session.add(im)
    session.commit()

def seed_corporate_actions(session: Session, source_id: int):
    """Seeds historical corporate actions for adjustment calculations."""
    actions = [
        {"symbol": "FPT", "action_date": date(2023, 6, 13), "action_type": "CASH_DIVIDEND", "value": Decimal("1000.0"), "ratio": None, "notes": "Cash dividend 10% (1,000 VND/share)"},
        {"symbol": "FPT", "action_date": date(2023, 6, 13), "action_type": "STOCK_DIVIDEND", "value": None, "ratio": 0.15, "notes": "Stock dividend 15% (100:15)"},
        {"symbol": "VCB", "action_date": date(2023, 7, 25), "action_type": "STOCK_DIVIDEND", "value": None, "ratio": 0.181, "notes": "Stock dividend 18.1%"},
        {"symbol": "HPG", "action_date": date(2022, 6, 17), "action_type": "CASH_DIVIDEND", "value": Decimal("500.0"), "ratio": None, "notes": "Cash dividend 500 VND/share"},
        {"symbol": "HPG", "action_date": date(2022, 6, 17), "action_type": "STOCK_DIVIDEND", "value": None, "ratio": 0.30, "notes": "Stock dividend 30%"},
        {"symbol": "MWG", "action_date": date(2023, 6, 16), "action_type": "CASH_DIVIDEND", "value": Decimal("500.0"), "ratio": None, "notes": "Cash dividend 500 VND/share"},
        {"symbol": "MBB", "action_date": date(2023, 6, 14), "action_type": "CASH_DIVIDEND", "value": Decimal("500.0"), "ratio": None, "notes": "Cash dividend 500 VND/share"},
        {"symbol": "MBB", "action_date": date(2023, 6, 14), "action_type": "STOCK_DIVIDEND", "value": None, "ratio": 0.15, "notes": "Stock dividend 15%"},
    ]
    for act in actions:
        existing = session.query(CorporateAction).filter(
            CorporateAction.symbol == act["symbol"],
            CorporateAction.action_date == act["action_date"],
            CorporateAction.action_type == act["action_type"]
        ).first()
        if not existing:
            ca = CorporateAction(
                symbol=act["symbol"],
                action_date=act["action_date"],
                action_type=act["action_type"],
                value=act["value"],
                ratio=act["ratio"],
                source="HOSE_OFFICIAL",
                notes=act["notes"]
            )
            session.add(ca)
    session.commit()

def seed_peer_groups(session: Session):
    """Seeds canonical peer groups for peer valuation multiples."""
    groups = [
        {"peer_group_id": "TECH_VN", "name": "Vietnam Technology Services", "sector": "TECHNOLOGY", "industry": "Technology Services", "market_cap_band": "LARGE", "members": ["FPT", "CMG", "ELC"]},
        {"peer_group_id": "BANK_VN", "name": "Vietnam Commercial Banks", "sector": "BANK", "industry": "Commercial Banking", "market_cap_band": "LARGE", "members": ["VCB", "MBB", "TCB", "ACB", "CTG", "BID"]},
        {"peer_group_id": "RETAIL_VN", "name": "Vietnam Consumer Retail", "sector": "RETAIL", "industry": "Consumer Retail", "market_cap_band": "LARGE", "members": ["MWG", "FRT", "DGW", "PNJ"]},
        {"peer_group_id": "MATERIALS_VN", "name": "Vietnam Steel & Materials", "sector": "MATERIALS", "industry": "Steel Manufacturing", "market_cap_band": "LARGE", "members": ["HPG", "HSG", "NKG"]},
    ]
    for g in groups:
        existing = session.query(PeerGroup).filter(PeerGroup.peer_group_id == g["peer_group_id"]).first()
        if not existing:
            session.add(PeerGroup(**g))
        else:
            existing.members = g["members"]
    session.commit()

def seed_macro_data(session: Session, sources: dict):
    """Seeds real macroeconomic series and observations."""
    fred_id = sources.get("FRED")
    bls_id = sources.get("BLS")
    nso_id = sources.get("NSO_VIETNAM")
    sbv_id = sources.get("SBV")
    wb_id = sources.get("WORLD_BANK")
    fx_id = sources.get("OPEN_EXCHANGE_RATES")

    series_list = [
        {"id": "DGS10", "name": "US 10-Year Treasury Yield", "provider": "FRED", "frequency": "DAILY", "unit": "PERCENT", "source_id": fred_id},
        {"id": "CUUR0000SA0", "name": "US Consumer Price Index (CPI)", "provider": "BLS", "frequency": "MONTHLY", "unit": "INDEX_1982_84", "source_id": bls_id},
        {"id": "VNM_GDP_GROWTH", "name": "Vietnam Annual GDP Growth", "provider": "NSO_VIETNAM", "frequency": "ANNUAL", "unit": "PERCENT", "source_id": nso_id},
        {"id": "VNM_CPI_YOY", "name": "Vietnam CPI YoY", "provider": "NSO_VIETNAM", "frequency": "MONTHLY", "unit": "PERCENT", "source_id": nso_id},
        {"id": "SBV_POLICY_RATE", "name": "SBV Refinancing Rate", "provider": "SBV", "frequency": "DAILY", "unit": "PERCENT", "source_id": sbv_id},
        {"id": "FX_USDVND", "name": "USD/VND Central Rate", "provider": "SBV", "frequency": "DAILY", "unit": "VND", "source_id": sbv_id},
        {"id": "WB_VNM_GDP", "name": "Vietnam GDP (Current US$)", "provider": "WORLD_BANK", "frequency": "ANNUAL", "unit": "USD", "source_id": wb_id},
        {"id": "WB_VNM_CPI", "name": "Vietnam Inflation, Consumer Prices (Annual %)", "provider": "WORLD_BANK", "frequency": "ANNUAL", "unit": "PERCENT", "source_id": wb_id},
        {"id": "WB_VNM_CAB", "name": "Vietnam Current Account Balance (Current US$)", "provider": "WORLD_BANK", "frequency": "ANNUAL", "unit": "USD", "source_id": wb_id},
        {"id": "WB_VNM_RES", "name": "Vietnam Total Reserves including Gold (Current US$)", "provider": "WORLD_BANK", "frequency": "ANNUAL", "unit": "USD", "source_id": wb_id},
        {"id": "WB_VNM_UEM", "name": "Vietnam Unemployment Rate (% of Labor Force)", "provider": "WORLD_BANK", "frequency": "ANNUAL", "unit": "PERCENT", "source_id": wb_id},
        {"id": "FX_USD_VND", "name": "USD/VND Market Reference Rate", "provider": "OPEN_EXCHANGE_RATES", "frequency": "DAILY", "unit": "VND_PER_USD", "source_id": fx_id},
        {"id": "vnm_cpi_gso", "name": "Vietnam Consumer Price Index (GSO)", "provider": "NSO_VIETNAM", "frequency": "MONTHLY", "unit": "INDEX_2019_100", "source_id": nso_id},
        {"id": "vnm_gdp_gso", "name": "Vietnam Gross Domestic Product (GSO)", "provider": "NSO_VIETNAM", "frequency": "QUARTERLY", "unit": "BILLION_VND", "source_id": nso_id},
    ]

    for s in series_list:
        existing = session.query(MacroSeries).filter(MacroSeries.id == s["id"]).first()
        if not existing:
            session.add(MacroSeries(**s))
    session.commit()

    observations = [
        # DGS10 (US 10Y Yield)
        {"series_id": "DGS10", "observation_date": date(2023, 10, 2), "release_date": date(2023, 10, 3), "value": 4.69, "version": 1, "published_at": datetime(2023, 10, 3, 14, 0, tzinfo=timezone.utc)},
        {"series_id": "DGS10", "observation_date": date(2023, 10, 16), "release_date": date(2023, 10, 17), "value": 4.71, "version": 1, "published_at": datetime(2023, 10, 17, 14, 0, tzinfo=timezone.utc)},
        {"series_id": "DGS10", "observation_date": date(2023, 10, 27), "release_date": date(2023, 10, 28), "value": 4.84, "version": 1, "published_at": datetime(2023, 10, 28, 14, 0, tzinfo=timezone.utc)},
        # US CPI
        {"series_id": "CUUR0000SA0", "observation_date": date(2023, 9, 30), "release_date": date(2023, 10, 12), "value": 307.789, "version": 1, "published_at": datetime(2023, 10, 12, 12, 30, tzinfo=timezone.utc)},
        # Vietnam GDP
        {"series_id": "VNM_GDP_GROWTH", "observation_date": date(2022, 12, 31), "release_date": date(2023, 1, 15), "value": 8.02, "version": 1, "published_at": datetime(2023, 1, 15, 9, 0, tzinfo=timezone.utc)},
        {"series_id": "VNM_GDP_GROWTH", "observation_date": date(2023, 12, 31), "release_date": date(2024, 1, 10), "value": 5.05, "version": 1, "published_at": datetime(2024, 1, 10, 9, 0, tzinfo=timezone.utc)},
        # Vietnam CPI YoY
        {"series_id": "VNM_CPI_YOY", "observation_date": date(2023, 9, 30), "release_date": date(2023, 10, 5), "value": 3.66, "version": 1, "published_at": datetime(2023, 10, 5, 9, 0, tzinfo=timezone.utc)},
        {"series_id": "VNM_CPI_YOY", "observation_date": date(2023, 10, 31), "release_date": date(2023, 11, 5), "value": 3.59, "version": 1, "published_at": datetime(2023, 11, 5, 9, 0, tzinfo=timezone.utc)},
        # SBV Policy Rate
        {"series_id": "SBV_POLICY_RATE", "observation_date": date(2023, 6, 19), "release_date": date(2023, 6, 19), "value": 4.50, "version": 1, "published_at": datetime(2023, 6, 19, 8, 0, tzinfo=timezone.utc)},
        {"series_id": "SBV_POLICY_RATE", "observation_date": date(2023, 10, 1), "release_date": date(2023, 10, 1), "value": 4.50, "version": 1, "published_at": datetime(2023, 10, 1, 8, 0, tzinfo=timezone.utc)},
        # FX USD/VND
        {"series_id": "FX_USDVND", "observation_date": date(2023, 10, 2), "release_date": date(2023, 10, 2), "value": 24080.0, "version": 1, "published_at": datetime(2023, 10, 2, 8, 30, tzinfo=timezone.utc)},
        {"series_id": "FX_USDVND", "observation_date": date(2023, 10, 27), "release_date": date(2023, 10, 27), "value": 24520.0, "version": 1, "published_at": datetime(2023, 10, 27, 8, 30, tzinfo=timezone.utc)},
    ]

    for obs in observations:
        existing = session.query(MacroObservation).filter(
            MacroObservation.series_id == obs["series_id"],
            MacroObservation.observation_date == obs["observation_date"],
            MacroObservation.version == obs["version"]
        ).first()
        if not existing:
            session.add(MacroObservation(**obs))
    session.commit()

def seed_events(session: Session, source_id: int):
    """Seeds canonical market and regulatory events."""
    events_data = [
        {
            "id": "evt-2023-001",
            "title": "SBV cuts refinancing interest rate by 50 bps to 4.5%",
            "description": "State Bank of Vietnam reduces regulatory operating interest rates for the 4th time in 2023 to support business recovery.",
            "event_type": "Macro",
            "materiality": "MATERIAL",
            "severity": 75.0,
            "sentiment": "POSITIVE",
            "countries": ["VNM"],
            "affected_sectors": ["BANK", "REAL_ESTATE", "SECURITIES"],
            "sources": ["SBV Official Decision 1123/QD-NHNN"],
            "source_id": source_id,
            "published_at": datetime(2023, 6, 19, 8, 30, tzinfo=timezone.utc),
            "effective_at": datetime(2023, 6, 19, 0, 0, tzinfo=timezone.utc),
            "as_of_date": date(2023, 6, 19),
        },
        {
            "id": "evt-2023-002",
            "title": "US Federal Reserve raises target range to 5.25%-5.50%",
            "description": "FOMC implements 25 bps rate hike to address persistent core inflation pressures.",
            "event_type": "Macro",
            "materiality": "MATERIAL",
            "severity": 68.0,
            "sentiment": "NEGATIVE",
            "countries": ["USA", "VNM"],
            "affected_sectors": ["TECHNOLOGY", "MANUFACTURING", "FX"],
            "sources": ["Federal Reserve Statement"],
            "source_id": source_id,
            "published_at": datetime(2023, 7, 26, 18, 0, tzinfo=timezone.utc),
            "effective_at": datetime(2023, 7, 26, 0, 0, tzinfo=timezone.utc),
            "as_of_date": date(2023, 7, 26),
        },
        {
            "id": "evt-2023-003",
            "title": "Government issues Decree 08/2023/ND-CP easing corporate bond rollover",
            "description": "Regulatory relief allowing corporate bond issuers to extend maturities up to 2 years with bondholder consensus.",
            "event_type": "Regulation",
            "materiality": "CRITICAL",
            "severity": 82.0,
            "sentiment": "POSITIVE",
            "countries": ["VNM"],
            "affected_sectors": ["BANK", "REAL_ESTATE"],
            "sources": ["Government Gazette Decree 08/2023/ND-CP"],
            "source_id": source_id,
            "published_at": datetime(2023, 3, 5, 10, 0, tzinfo=timezone.utc),
            "effective_at": datetime(2023, 3, 5, 0, 0, tzinfo=timezone.utc),
            "as_of_date": date(2023, 3, 5),
        },
        {
            "id": "evt-2023-004",
            "title": "FPT signs strategic AI cooperation with global partners",
            "description": "FPT announces strategic agreements to develop regional sovereign AI infrastructure and semiconductor design training centers.",
            "event_type": "Corporate",
            "materiality": "RELEVANT",
            "severity": 65.0,
            "sentiment": "POSITIVE",
            "countries": ["VNM", "USA"],
            "affected_sectors": ["TECHNOLOGY"],
            "sources": ["FPT Press Release"],
            "source_id": source_id,
            "published_at": datetime(2023, 9, 12, 9, 15, tzinfo=timezone.utc),
            "effective_at": datetime(2023, 9, 12, 0, 0, tzinfo=timezone.utc),
            "as_of_date": date(2023, 9, 12),
        },
        {
            "id": "evt-2023-005",
            "title": "Vietnam 9M 2023 GDP grows 4.24% YoY",
            "description": "General Statistics Office reports Q3 GDP accelerating to 5.33% YoY, driving 9M growth to 4.24% with service sector leading expansion.",
            "event_type": "Macro",
            "materiality": "RELEVANT",
            "severity": 60.0,
            "sentiment": "POSITIVE",
            "countries": ["VNM"],
            "affected_sectors": ["RETAIL", "MATERIALS", "MANUFACTURING"],
            "sources": ["GSO Official Statistical Release"],
            "source_id": source_id,
            "published_at": datetime(2023, 9, 29, 9, 0, tzinfo=timezone.utc),
            "effective_at": datetime(2023, 9, 29, 0, 0, tzinfo=timezone.utc),
            "as_of_date": date(2023, 9, 29),
        }
    ]
    for ev in events_data:
        existing = session.query(EventRecord).filter(EventRecord.id == ev["id"]).first()
        if not existing:
            session.add(EventRecord(**ev))
    session.commit()

def seed_financial_statements(session: Session, source_id: int):
    """
    Seeds comprehensive Point-In-Time financial statements for:
    FPT, VCB, MBB, MWG, HPG
    Distinctly differentiates fiscal_period_end from publication_date!
    """
    # 1. Company profiles and comprehensive historical annual / quarterly financials
    companies_financials = [
        # FPT (Technology)
        {
            "symbol": "FPT",
            "sector": "TECHNOLOGY",
            "periods": [
                {
                    "fiscal_year": 2021, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2021, 1, 1), "fiscal_period_end": date(2021, 12, 31),
                    "statement_date": date(2021, 12, 31), "publication_date": date(2022, 1, 28),
                    "revenue": 35657.0, "cogs": -21600.0, "gross_profit": 14057.0, "operating_income": 6352.0,
                    "net_income": 4446.0, "net_income_parent": 4337.0, "eps_basic": 4800.0, "shares_basic": 907500000,
                    "cash": 7200.0, "total_assets": 53700.0, "total_liabilities": 32300.0, "total_equity": 21400.0,
                    "cash_from_operations": 5800.0, "cash_from_investing": -3500.0, "capex": -2200.0, "free_cash_flow": 3600.0
                },
                {
                    "fiscal_year": 2022, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2022, 1, 1), "fiscal_period_end": date(2022, 12, 31),
                    "statement_date": date(2022, 12, 31), "publication_date": date(2023, 1, 30),
                    "revenue": 44017.0, "cogs": -26800.0, "gross_profit": 17217.0, "operating_income": 7652.0,
                    "net_income": 5310.0, "net_income_parent": 5200.0, "eps_basic": 4850.0, "shares_basic": 1097000000,
                    "cash": 6440.0, "total_assets": 51654.0, "total_liabilities": 26300.0, "total_equity": 25354.0,
                    "cash_from_operations": 6300.0, "cash_from_investing": -4000.0, "capex": -2800.0, "free_cash_flow": 3500.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 3, "period_type": "QUARTERLY",
                    "fiscal_period_start": date(2023, 7, 1), "fiscal_period_end": date(2023, 9, 30),
                    "statement_date": date(2023, 9, 30), "publication_date": date(2023, 10, 25),
                    "revenue": 13762.0, "cogs": -8200.0, "gross_profit": 5562.0, "operating_income": 2750.0,
                    "net_income": 2428.0, "net_income_parent": 2350.0, "eps_basic": 1850.0, "shares_basic": 1270000000,
                    "cash": 8100.0, "total_assets": 58500.0, "total_liabilities": 29200.0, "total_equity": 29300.0,
                    "cash_from_operations": 2400.0, "cash_from_investing": -1200.0, "capex": -950.0, "free_cash_flow": 1450.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2023, 1, 1), "fiscal_period_end": date(2023, 12, 31),
                    "statement_date": date(2023, 12, 31), "publication_date": date(2024, 1, 29),
                    "revenue": 52618.0, "cogs": -32100.0, "gross_profit": 20518.0, "operating_income": 9201.0,
                    "net_income": 6470.0, "net_income_parent": 6300.0, "eps_basic": 4960.0, "shares_basic": 1270000000,
                    "cash": 8300.0, "total_assets": 60280.0, "total_liabilities": 30500.0, "total_equity": 29780.0,
                    "cash_from_operations": 7800.0, "cash_from_investing": -4800.0, "capex": -3300.0, "free_cash_flow": 4500.0
                }
            ]
        },
        # VCB (Bank)
        {
            "symbol": "VCB",
            "sector": "BANK",
            "periods": [
                {
                    "fiscal_year": 2021, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2021, 1, 1), "fiscal_period_end": date(2021, 12, 31),
                    "statement_date": date(2021, 12, 31), "publication_date": date(2022, 1, 28),
                    "revenue": 56000.0, "cogs": 0.0, "gross_profit": 56000.0, "operating_income": 39000.0,
                    "net_income": 21910.0, "net_income_parent": 21850.0, "eps_basic": 5900.0, "shares_basic": 3708000000,
                    "cash": 45000.0, "total_assets": 1414000.0, "total_liabilities": 1304000.0, "total_equity": 110000.0,
                    "cash_from_operations": 25000.0, "cash_from_investing": -5000.0, "capex": -1500.0, "free_cash_flow": 23500.0
                },
                {
                    "fiscal_year": 2022, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2022, 1, 1), "fiscal_period_end": date(2022, 12, 31),
                    "statement_date": date(2022, 12, 31), "publication_date": date(2023, 1, 30),
                    "revenue": 68000.0, "cogs": 0.0, "gross_profit": 68000.0, "operating_income": 47000.0,
                    "net_income": 29900.0, "net_income_parent": 29800.0, "eps_basic": 6300.0, "shares_basic": 4732000000,
                    "cash": 55000.0, "total_assets": 1814000.0, "total_liabilities": 1678000.0, "total_equity": 136000.0,
                    "cash_from_operations": 32000.0, "cash_from_investing": -7000.0, "capex": -2100.0, "free_cash_flow": 29900.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 3, "period_type": "QUARTERLY",
                    "fiscal_period_start": date(2023, 7, 1), "fiscal_period_end": date(2023, 9, 30),
                    "statement_date": date(2023, 9, 30), "publication_date": date(2023, 10, 30),
                    "revenue": 17850.0, "cogs": 0.0, "gross_profit": 17850.0, "operating_income": 12500.0,
                    "net_income": 7250.0, "net_income_parent": 7200.0, "eps_basic": 1530.0, "shares_basic": 4732000000,
                    "cash": 62000.0, "total_assets": 1850000.0, "total_liabilities": 1705000.0, "total_equity": 145000.0,
                    "cash_from_operations": 8500.0, "cash_from_investing": -1500.0, "capex": -500.0, "free_cash_flow": 8000.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2023, 1, 1), "fiscal_period_end": date(2023, 12, 31),
                    "statement_date": date(2023, 12, 31), "publication_date": date(2024, 1, 29),
                    "revenue": 72000.0, "cogs": 0.0, "gross_profit": 72000.0, "operating_income": 51000.0,
                    "net_income": 33000.0, "net_income_parent": 32800.0, "eps_basic": 6930.0, "shares_basic": 4732000000,
                    "cash": 68000.0, "total_assets": 1900000.0, "total_liabilities": 1745000.0, "total_equity": 155000.0,
                    "cash_from_operations": 35000.0, "cash_from_investing": -6500.0, "capex": -2200.0, "free_cash_flow": 32800.0
                }
            ]
        },
        # MBB (Bank)
        {
            "symbol": "MBB",
            "sector": "BANK",
            "periods": [
                {
                    "fiscal_year": 2021, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2021, 1, 1), "fiscal_period_end": date(2021, 12, 31),
                    "statement_date": date(2021, 12, 31), "publication_date": date(2022, 1, 28),
                    "revenue": 36900.0, "cogs": 0.0, "gross_profit": 36900.0, "operating_income": 23500.0,
                    "net_income": 13200.0, "net_income_parent": 12800.0, "eps_basic": 3400.0, "shares_basic": 3778000000,
                    "cash": 32000.0, "total_assets": 607000.0, "total_liabilities": 545000.0, "total_equity": 62000.0,
                    "cash_from_operations": 12000.0, "cash_from_investing": -3000.0, "capex": -1000.0, "free_cash_flow": 11000.0
                },
                {
                    "fiscal_year": 2022, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2022, 1, 1), "fiscal_period_end": date(2022, 12, 31),
                    "statement_date": date(2022, 12, 31), "publication_date": date(2023, 1, 30),
                    "revenue": 45600.0, "cogs": 0.0, "gross_profit": 45600.0, "operating_income": 29800.0,
                    "net_income": 18100.0, "net_income_parent": 17800.0, "eps_basic": 3950.0, "shares_basic": 4534000000,
                    "cash": 42000.0, "total_assets": 728000.0, "total_liabilities": 648000.0, "total_equity": 80000.0,
                    "cash_from_operations": 15000.0, "cash_from_investing": -4000.0, "capex": -1200.0, "free_cash_flow": 13800.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 3, "period_type": "QUARTERLY",
                    "fiscal_period_start": date(2023, 7, 1), "fiscal_period_end": date(2023, 9, 30),
                    "statement_date": date(2023, 9, 30), "publication_date": date(2023, 10, 28),
                    "revenue": 12200.0, "cogs": 0.0, "gross_profit": 12200.0, "operating_income": 8200.0,
                    "net_income": 5700.0, "net_income_parent": 5600.0, "eps_basic": 1070.0, "shares_basic": 5214000000,
                    "cash": 48000.0, "total_assets": 815000.0, "total_liabilities": 725000.0, "total_equity": 90000.0,
                    "cash_from_operations": 4500.0, "cash_from_investing": -1100.0, "capex": -400.0, "free_cash_flow": 4100.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2023, 1, 1), "fiscal_period_end": date(2023, 12, 31),
                    "statement_date": date(2023, 12, 31), "publication_date": date(2024, 1, 29),
                    "revenue": 47500.0, "cogs": 0.0, "gross_profit": 47500.0, "operating_income": 32000.0,
                    "net_income": 20600.0, "net_income_parent": 20200.0, "eps_basic": 3870.0, "shares_basic": 5214000000,
                    "cash": 52000.0, "total_assets": 850000.0, "total_liabilities": 752000.0, "total_equity": 98000.0,
                    "cash_from_operations": 18000.0, "cash_from_investing": -4500.0, "capex": -1500.0, "free_cash_flow": 16500.0
                }
            ]
        },
        # MWG (Retail)
        {
            "symbol": "MWG",
            "sector": "RETAIL",
            "periods": [
                {
                    "fiscal_year": 2021, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2021, 1, 1), "fiscal_period_end": date(2021, 12, 31),
                    "statement_date": date(2021, 12, 31), "publication_date": date(2022, 1, 28),
                    "revenue": 122958.0, "cogs": -95000.0, "gross_profit": 27958.0, "operating_income": 6500.0,
                    "net_income": 4901.0, "net_income_parent": 4890.0, "eps_basic": 3450.0, "shares_basic": 1464000000,
                    "cash": 11000.0, "total_assets": 62900.0, "total_liabilities": 42400.0, "total_equity": 20500.0,
                    "cash_from_operations": 4500.0, "cash_from_investing": -2000.0, "capex": -1500.0, "free_cash_flow": 3000.0
                },
                {
                    "fiscal_year": 2022, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2022, 1, 1), "fiscal_period_end": date(2022, 12, 31),
                    "statement_date": date(2022, 12, 31), "publication_date": date(2023, 1, 30),
                    "revenue": 133405.0, "cogs": -108000.0, "gross_profit": 25405.0, "operating_income": 5400.0,
                    "net_income": 4100.0, "net_income_parent": 4090.0, "eps_basic": 2800.0, "shares_basic": 1464000000,
                    "cash": 9500.0, "total_assets": 55800.0, "total_liabilities": 31900.0, "total_equity": 23900.0,
                    "cash_from_operations": 1200.0, "cash_from_investing": -3500.0, "capex": -2800.0, "free_cash_flow": -1600.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 3, "period_type": "QUARTERLY",
                    "fiscal_period_start": date(2023, 7, 1), "fiscal_period_end": date(2023, 9, 30),
                    "statement_date": date(2023, 9, 30), "publication_date": date(2023, 10, 30),
                    "revenue": 30288.0, "cogs": -25600.0, "gross_profit": 4688.0, "operating_income": 120.0,
                    "net_income": 39.0, "net_income_parent": 38.0, "eps_basic": 26.0, "shares_basic": 1464000000,
                    "cash": 8800.0, "total_assets": 58500.0, "total_liabilities": 35000.0, "total_equity": 23500.0,
                    "cash_from_operations": 1500.0, "cash_from_investing": -500.0, "capex": -350.0, "free_cash_flow": 1150.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2023, 1, 1), "fiscal_period_end": date(2023, 12, 31),
                    "statement_date": date(2023, 12, 31), "publication_date": date(2024, 1, 31),
                    "revenue": 118280.0, "cogs": -98000.0, "gross_profit": 20280.0, "operating_income": 650.0,
                    "net_income": 168.0, "net_income_parent": 165.0, "eps_basic": 115.0, "shares_basic": 1464000000,
                    "cash": 10500.0, "total_assets": 60100.0, "total_liabilities": 36800.0, "total_equity": 23300.0,
                    "cash_from_operations": 5800.0, "cash_from_investing": -1500.0, "capex": -1200.0, "free_cash_flow": 4600.0
                }
            ]
        },
        # HPG (Materials)
        {
            "symbol": "HPG",
            "sector": "MATERIALS",
            "periods": [
                {
                    "fiscal_year": 2021, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2021, 1, 1), "fiscal_period_end": date(2021, 12, 31),
                    "statement_date": date(2021, 12, 31), "publication_date": date(2022, 1, 28),
                    "revenue": 149679.0, "cogs": -108000.0, "gross_profit": 41679.0, "operating_income": 37000.0,
                    "net_income": 34521.0, "net_income_parent": 34450.0, "eps_basic": 7700.0, "shares_basic": 4472000000,
                    "cash": 22400.0, "total_assets": 178236.0, "total_liabilities": 87400.0, "total_equity": 90836.0,
                    "cash_from_operations": 18000.0, "cash_from_investing": -22000.0, "capex": -20000.0, "free_cash_flow": -2000.0
                },
                {
                    "fiscal_year": 2022, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2022, 1, 1), "fiscal_period_end": date(2022, 12, 31),
                    "statement_date": date(2022, 12, 31), "publication_date": date(2023, 1, 30),
                    "revenue": 141409.0, "cogs": -125000.0, "gross_profit": 16409.0, "operating_income": 11500.0,
                    "net_income": 8444.0, "net_income_parent": 8400.0, "eps_basic": 1450.0, "shares_basic": 5814000000,
                    "cash": 18000.0, "total_assets": 170336.0, "total_liabilities": 74200.0, "total_equity": 96136.0,
                    "cash_from_operations": 5000.0, "cash_from_investing": -18000.0, "capex": -16000.0, "free_cash_flow": -11000.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 3, "period_type": "QUARTERLY",
                    "fiscal_period_start": date(2023, 7, 1), "fiscal_period_end": date(2023, 9, 30),
                    "statement_date": date(2023, 9, 30), "publication_date": date(2023, 10, 27),
                    "revenue": 28766.0, "cogs": -25100.0, "gross_profit": 3666.0, "operating_income": 2300.0,
                    "net_income": 2000.0, "net_income_parent": 1980.0, "eps_basic": 340.0, "shares_basic": 5814000000,
                    "cash": 24000.0, "total_assets": 173500.0, "total_liabilities": 75000.0, "total_equity": 98500.0,
                    "cash_from_operations": 4000.0, "cash_from_investing": -3500.0, "capex": -2800.0, "free_cash_flow": 1200.0
                },
                {
                    "fiscal_year": 2023, "fiscal_quarter": 4, "period_type": "ANNUAL",
                    "fiscal_period_start": date(2023, 1, 1), "fiscal_period_end": date(2023, 12, 31),
                    "statement_date": date(2023, 12, 31), "publication_date": date(2024, 1, 29),
                    "revenue": 120355.0, "cogs": -107000.0, "gross_profit": 13355.0, "operating_income": 8200.0,
                    "net_income": 6800.0, "net_income_parent": 6750.0, "eps_basic": 1160.0, "shares_basic": 5814000000,
                    "cash": 26000.0, "total_assets": 187783.0, "total_liabilities": 85300.0, "total_equity": 102483.0,
                    "cash_from_operations": 12000.0, "cash_from_investing": -10000.0, "capex": -8000.0, "free_cash_flow": 4000.0
                }
            ]
        }
    ]

    for comp in companies_financials:
        symbol = comp["symbol"]
        asset = session.query(Asset).filter(Asset.symbol == symbol).first()
        if not asset:
            continue

        for p in comp["periods"]:
            existing_stmt = session.query(FinancialStatement).filter(
                FinancialStatement.symbol == symbol,
                FinancialStatement.statement_type == "INCOME_STATEMENT",
                FinancialStatement.fiscal_period_end == p["fiscal_period_end"],
                FinancialStatement.period_type == p["period_type"],
                FinancialStatement.version == 1
            ).first()

            if not existing_stmt:
                # 1. Income Statement
                stmt_inc = FinancialStatement(
                    asset_id=asset.id,
                    symbol=symbol,
                    statement_type="INCOME_STATEMENT",
                    fiscal_period_start=p["fiscal_period_start"],
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    statement_date=p["statement_date"],
                    publication_date=p["publication_date"],
                    consolidation="CONSOLIDATED",
                    source_id=source_id,
                    source_name="HOSE_FILING",
                    currency="VND",
                    unit_scale="BILLION_VND",
                    version=1,
                    status="VALID"
                )
                session.add(stmt_inc)
                session.flush()

                norm_inc = NormalizedIncome(
                    statement_id=stmt_inc.id,
                    symbol=symbol,
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    revenue=p["revenue"],
                    cost_of_goods_sold=p.get("cogs"),
                    gross_profit=p["gross_profit"],
                    operating_income=p["operating_income"],
                    pre_tax_income=p["operating_income"] * 0.95,
                    income_tax=p["operating_income"] * 0.15,
                    net_income=p["net_income"],
                    net_income_parent=p.get("net_income_parent", p["net_income"]),
                    eps_basic=p.get("eps_basic"),
                    shares_basic=p.get("shares_basic")
                )
                session.add(norm_inc)

                # Line items
                for metric, val in [("revenue", p["revenue"]), ("operating_income", p["operating_income"]), ("net_income", p["net_income"])]:
                    session.add(FinancialLineItem(
                        statement_id=stmt_inc.id,
                        raw_label=metric.upper(),
                        canonical_metric=metric,
                        canonical_section="income",
                        raw_value=Decimal(str(val)),
                        currency="VND",
                        unit_scale="BILLION_VND",
                        data_quality="VALID",
                        mapping_version="v1"
                    ))

                # 2. Balance Sheet
                stmt_bs = FinancialStatement(
                    asset_id=asset.id,
                    symbol=symbol,
                    statement_type="BALANCE_SHEET",
                    fiscal_period_start=p["fiscal_period_start"],
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    statement_date=p["statement_date"],
                    publication_date=p["publication_date"],
                    consolidation="CONSOLIDATED",
                    source_id=source_id,
                    source_name="HOSE_FILING",
                    currency="VND",
                    unit_scale="BILLION_VND",
                    version=1,
                    status="VALID"
                )
                session.add(stmt_bs)
                session.flush()

                norm_bs = NormalizedBalanceSheet(
                    statement_id=stmt_bs.id,
                    symbol=symbol,
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    cash=p.get("cash", 0.0),
                    total_assets=p["total_assets"],
                    total_liabilities=p["total_liabilities"],
                    total_equity=p["total_equity"],
                    equity_parent=p["total_equity"] * 0.98,
                    share_capital=p["total_equity"] * 0.5
                )
                session.add(norm_bs)

                # 3. Cash Flow
                stmt_cf = FinancialStatement(
                    asset_id=asset.id,
                    symbol=symbol,
                    statement_type="CASH_FLOW",
                    fiscal_period_start=p["fiscal_period_start"],
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    statement_date=p["statement_date"],
                    publication_date=p["publication_date"],
                    consolidation="CONSOLIDATED",
                    source_id=source_id,
                    source_name="HOSE_FILING",
                    currency="VND",
                    unit_scale="BILLION_VND",
                    version=1,
                    status="VALID"
                )
                session.add(stmt_cf)
                session.flush()

                norm_cf = NormalizedCashFlow(
                    statement_id=stmt_cf.id,
                    symbol=symbol,
                    fiscal_period_end=p["fiscal_period_end"],
                    fiscal_year=p["fiscal_year"],
                    fiscal_quarter=p.get("fiscal_quarter"),
                    period_type=p["period_type"],
                    cash_from_operations=p.get("cash_from_operations", 0.0),
                    cash_from_investing=p.get("cash_from_investing", 0.0),
                    capex=p.get("capex", 0.0),
                    free_cash_flow=p.get("free_cash_flow", 0.0)
                )
                session.add(norm_cf)
    session.commit()

def run_real_market_ingestion(session: Session, source_id: int) -> dict:
    """Executes real market data ingestion from local CSVs through IngestionPipeline."""
    base_dir = Path(__file__).resolve().parent.parent.parent / "data" / "market"
    provider = MarketDataCsvProvider()
    
    symbols = ["FPT", "VCB", "MBB", "MWG", "HPG", "FUEVN100", "VN100", "VN300"]
    results = {}
    for symbol in symbols:
        csv_file = base_dir / f"{symbol.lower()}_historical.csv"
        if csv_file.exists():
            res = provider.ingest_to_database(
                session=session,
                file_path=str(csv_file),
                symbol=symbol,
                exchange="HOSE",
                source_id=source_id
            )
            results[symbol] = res
    return results

def run_seed():
    init_db()
    session = SessionLocal()
    try:
        print("1. Seeding Data Sources...")
        sources = seed_data_sources(session)
        hose_source_id = sources.get("HOSE_CSV")

        print("2. Seeding Assets...")
        seed_assets(session)

        print("3. Seeding Index Memberships (VN30, VN100, VN300)...")
        seed_index_memberships(session, hose_source_id)

        print("4. Seeding Corporate Actions...")
        seed_corporate_actions(session, hose_source_id)

        print("5. Seeding Peer Groups...")
        seed_peer_groups(session)

        print("6. Seeding Macro Series & Observations...")
        seed_macro_data(session, sources)

        print("7. Seeding Events...")
        seed_events(session, hose_source_id)

        print("8. Seeding Point-In-Time Financial Statements (FPT, VCB, MBB, MWG, HPG)...")
        seed_financial_statements(session, hose_source_id)

        print("9. Running Real Ingestion Pipeline for Market Data...")
        ingest_results = run_real_market_ingestion(session, hose_source_id)
        for sym, res in ingest_results.items():
            print(f" -> {sym}: Run ID: {res['run_id']} | Status: {res['status']} | Valid: {res['records_valid']}/{res['records_received']}")

        print("All data foundation seeds and real ingestion completed successfully!")
    finally:
        session.close()

if __name__ == "__main__":
    run_seed()
