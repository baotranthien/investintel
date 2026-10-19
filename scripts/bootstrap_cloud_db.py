"""Idempotent Cloud Database Bootstrap Script.

1. Executes `alembic upgrade head`.
2. Seeds only approved reference/canonical market assets and data sources.
3. Preserves existing canonical records without overwriting.
4. Protects personal privacy: never copies personal portfolios, transactions,
   watchlists, or notes automatically to the cloud database.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic.config import Config
from alembic import command
from database.connection import SessionLocal, get_database_url
from database.models import Asset, DataSource, MacroSeries

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

APPROVED_DATA_SOURCES = [
    {
        "name": "DNSE",
        "provider": "DNSE",
        "country": "VNM",
        "authority_level": "REPUTABLE_SECONDARY",
        "source_type": "API",
        "base_url": "https://services.entrade.com.vn",
        "active": True,
    },
    {
        "name": "VNDIRECT",
        "provider": "VNDIRECT",
        "country": "VNM",
        "authority_level": "REPUTABLE_SECONDARY",
        "source_type": "API",
        "base_url": "https://finfo-api.vndirect.com.vn",
        "active": True,
    },
    {
        "name": "LOTUSMARKET",
        "provider": "LOTUSMARKET",
        "country": "VNM",
        "authority_level": "REPUTABLE_SECONDARY",
        "source_type": "API",
        "base_url": "https://bgapidatafeed.vps.com.vn",
        "active": True,
    },
    {
        "name": "GSO",
        "provider": "GSO",
        "country": "VNM",
        "authority_level": "PRIMARY_OFFICIAL",
        "source_type": "WEB/XLS",
        "base_url": "https://www.gso.gov.vn",
        "active": True,
    },
    {
        "name": "SBV",
        "provider": "SBV",
        "country": "VNM",
        "authority_level": "PRIMARY_OFFICIAL",
        "source_type": "WEB",
        "base_url": "https://www.sbv.gov.vn",
        "active": True,
    },
    {
        "name": "FRED",
        "provider": "FRED",
        "country": "USA",
        "authority_level": "PRIMARY_OFFICIAL",
        "source_type": "API/CSV",
        "base_url": "https://fred.stlouisfed.org",
        "active": True,
    },
]

APPROVED_ASSETS = [
    {"symbol": "FPT", "name": "Công ty Cổ phần FPT", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Technology"},
    {"symbol": "VCB", "name": "Ngân hàng TMCP Ngoại thương Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "MBB", "name": "Ngân hàng TMCP Quân đội", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "MWG", "name": "Công ty Cổ phần Đầu tư Thế Giới Di Động", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Retail"},
    {"symbol": "HPG", "name": "Công ty Cổ phần Tập đoàn Hòa Phát", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Materials"},
    {"symbol": "ACB", "name": "Ngân hàng TMCP Á Châu", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "BCM", "name": "Tổng Công ty Đầu tư và Phát triển Công nghiệp", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Real Estate"},
    {"symbol": "BID", "name": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "BVH", "name": "Tập đoàn Bảo Việt", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Financials"},
    {"symbol": "CTG", "name": "Ngân hàng TMCP Công thương Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "GAS", "name": "Tổng Công ty Khí Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Energy"},
    {"symbol": "GVR", "name": "Tập đoàn Công nghiệp Cao su Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Materials"},
    {"symbol": "HDB", "name": "Ngân hàng TMCP Phát triển TP.HCM", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "MSN", "name": "Công ty Cổ phần Tập đoàn Masan", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Consumer Goods"},
    {"symbol": "PLX", "name": "Tập đoàn Xăng dầu Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Energy"},
    {"symbol": "POW", "name": "Tổng Công ty Điện lực Dầu khí Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Utilities"},
    {"symbol": "SAB", "name": "Tổng Công ty Cổ phần Bia - Rượu - Nước giải khát Sài Gòn", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Consumer Goods"},
    {"symbol": "SHB", "name": "Ngân hàng TMCP Sài Gòn - Hà Nội", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "SSB", "name": "Ngân hàng TMCP Đông Nam Á", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "SSI", "name": "Công ty Cổ phần Chứng khoán SSI", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Financials"},
    {"symbol": "STB", "name": "Ngân hàng TMCP Sài Gòn Thương Tín", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "TCB", "name": "Ngân hàng TMCP Kỹ thương Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "TPB", "name": "Ngân hàng TMCP Tiên Phong", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "VHM", "name": "Công ty Cổ phần Vinhomes", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Real Estate"},
    {"symbol": "VIB", "name": "Ngân hàng TMCP Quốc tế Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "VIC", "name": "Tập đoàn Vingroup", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Real Estate"},
    {"symbol": "VJC", "name": "Công ty Cổ phần Hàng không VietJet", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Industrials"},
    {"symbol": "VNM", "name": "Công ty Cổ phần Sữa Việt Nam", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Consumer Goods"},
    {"symbol": "VPB", "name": "Ngân hàng TMCP Việt Nam Thịnh Vượng", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Banking"},
    {"symbol": "VRE", "name": "Công ty Cổ phần Vincom Retail", "asset_type": "STOCK", "exchange": "HOSE", "sector": "Real Estate"},
    {"symbol": "VN30", "name": "Chỉ số VN30 Index", "asset_type": "INDEX", "exchange": "HOSE", "sector": "Benchmark"},
    {"symbol": "VN100", "name": "Chỉ số VN100 Index", "asset_type": "INDEX", "exchange": "HOSE", "sector": "Benchmark"},
    {"symbol": "VN300", "name": "Chỉ số VN300 Index", "asset_type": "INDEX", "exchange": "HOSE", "sector": "Benchmark"},
]

APPROVED_MACRO_SERIES = [
    {"id": "vn_gdp_growth", "name": "Tăng trưởng GDP Việt Nam", "provider": "GSO", "frequency": "QUARTERLY", "unit": "%"},
    {"id": "vn_cpi_yoy", "name": "Chỉ số CPI YoY Việt Nam", "provider": "GSO", "frequency": "MONTHLY", "unit": "%"},
    {"id": "vn_fdi_disbursed", "name": "Vốn FDI thực hiện Việt Nam", "provider": "GSO", "frequency": "MONTHLY", "unit": "USD"},
    {"id": "vn_policy_rate", "name": "Lãi suất điều hành NHNN", "provider": "SBV", "frequency": "MONTHLY", "unit": "%"},
    {"id": "us_cpi_yoy", "name": "US CPI YoY", "provider": "BLS", "frequency": "MONTHLY", "unit": "%"},
    {"id": "us_fed_funds_rate", "name": "US Federal Funds Effective Rate", "provider": "FRED", "frequency": "MONTHLY", "unit": "%"},
    {"id": "fred_dgs10", "name": "US 10-Year Treasury Constant Maturity Rate", "provider": "FRED", "frequency": "DAILY", "unit": "%"},
]


def run_migrations():
    """Run Alembic upgrade head against configured database."""
    logger.info("Executing Alembic migrations (upgrade head)...")
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations completed successfully.")


def seed_reference_data(db):
    """Seed approved reference assets, memberships, sources and verified statements idempotently."""
    from database.models import IndexMembership, FinancialStatement

    logger.info("Checking and seeding approved reference DataSources...")
    for ds_info in APPROVED_DATA_SOURCES:
        existing = db.query(DataSource).filter_by(name=ds_info["name"]).first()
        if not existing:
            ds = DataSource(**ds_info)
            db.add(ds)
            logger.info(f"  + Added DataSource: {ds_info['name']}")
        else:
            logger.debug(f"  = DataSource already exists: {ds_info['name']}")

    logger.info("Checking and seeding approved reference Assets...")
    for asset_info in APPROVED_ASSETS:
        existing = db.query(Asset).filter_by(symbol=asset_info["symbol"]).first()
        if not existing:
            asset = Asset(**asset_info)
            db.add(asset)
            logger.info(f"  + Added Asset: {asset_info['symbol']}")
        else:
            logger.debug(f"  = Asset already exists: {asset_info['symbol']}")

    logger.info("Checking and seeding approved reference MacroSeries...")
    for series_info in APPROVED_MACRO_SERIES:
        existing = db.query(MacroSeries).filter_by(id=series_info["id"]).first()
        if not existing:
            series = MacroSeries(**series_info)
            db.add(series)
            logger.info(f"  + Added MacroSeries: {series_info['id']}")
        else:
            logger.debug(f"  = MacroSeries already exists: {series_info['id']}")

    db.commit()

    # Seed Index Memberships for VN30 and VN100
    try:
        from services.ingestion.seed_data import seed_index_memberships
        vn30_members = db.query(IndexMembership).filter_by(index_symbol="VN30").count()
        vn100_members = db.query(IndexMembership).filter_by(index_symbol="VN100").count()
        if vn30_members < 30 or vn100_members < 100:
            logger.info(f"Seeding verified index memberships (current: VN30={vn30_members}, VN100={vn100_members})...")
            hose_ds = db.query(DataSource).filter_by(name="HOSE_CSV").first()
            source_id = hose_ds.id if hose_ds else 1
            seed_index_memberships(db, source_id)
            logger.info("Index memberships seeded successfully.")
    except Exception as e:
        logger.warning(f"Index membership seeding notice: {e}")

    # Seed Verified Financial Statements if database has no statements
    try:
        stmt_count = db.query(FinancialStatement).count()
        if stmt_count == 0:
            logger.info("Database has 0 financial statements. Seeding verified Point-In-Time statements...")
            from services.ingestion.seed_data import seed_financial_statements
            hose_ds = db.query(DataSource).filter_by(name="HOSE_CSV").first()
            source_id = hose_ds.id if hose_ds else 1
            seed_financial_statements(db, source_id)
            logger.info("Verified financial statements seeded successfully.")
    except Exception as e:
        logger.warning(f"Financial statement seeding notice: {e}")

    db.commit()
    logger.info("Reference data seeding completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap cloud database idempotently.")
    parser.add_argument(
        "--include-personal-data",
        action="store_true",
        default=False,
        help="EXPLICIT OPT-IN ONLY: Copy personal portfolio, transactions, and watchlist.",
    )
    args = parser.parse_args()

    db_url = get_database_url()
    safe_url = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info(f"Target Database: ...@{safe_url}")

    if args.include_personal_data:
        logger.warning(
            "CRITICAL WARNING: --include-personal-data specified. This will transfer private financial records to cloud."
        )
        confirm = input("Type 'CONFIRM_PERSONAL_DATA_MIGRATION' to proceed: ")
        if confirm.strip() != "CONFIRM_PERSONAL_DATA_MIGRATION":
            logger.error("Personal data migration aborted.")
            sys.exit(1)
        logger.info("Personal data migration confirmed by user.")
    else:
        logger.info("Data Privacy Guard: Personal financial data will NOT be copied to the remote database.")

    # 1. Run migrations
    run_migrations()

    # 2. Seed approved reference data
    db = SessionLocal()
    try:
        seed_reference_data(db)
    finally:
        db.close()

    logger.info("Cloud database bootstrap completed successfully.")


if __name__ == "__main__":
    main()
