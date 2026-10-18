"""
Historical Price Ingestion Script.
Fetches daily OHLCV bars from 2020-01-01 to 2026-10-18 using FallbackMarketDataProvider
(DNSE -> VNDirect -> local CSV) for core symbols (FPT, VCB, MBB, MWG, HPG) and syncs
canonical EOD CSV backups to data/market/<symbol>_historical.csv.

Maintains Point-In-Time integrity and non-destructive conflict protection.
"""
import sys
import os
import asyncio
import logging
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from database.models import Asset, DataSource
from services.ingestion.market_data import FallbackMarketDataProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_prices")


async def main():
    symbols = ["FPT", "VCB", "MBB", "MWG", "HPG"]
    start_date = date(2020, 1, 1)
    end_date = date(2026, 10, 18)

    provider = FallbackMarketDataProvider(dnse_timeout=20.0, vndirect_timeout=20.0)

    db = SessionLocal()
    try:
        # Pre-resolve source IDs
        sources = {s.name: s.id for s in db.query(DataSource).all()}
        logger.info("Starting historical price ingestion (2020-2026) for %s", symbols)

        for sym in symbols:
            logger.info("--- Ingesting %s ---", sym)
            res = await provider.ingest_to_database(
                session=db,
                symbol=sym,
                start_date=start_date,
                end_date=end_date,
                exchange="HOSE",
                source_ids=sources,
                save_eod_csv=True
            )
            db.commit()
            logger.info("[%s] Result: status=%s, provider=%s, valid=%s, rejected=%s",
                        sym, res.get("status"), res.get("provider_used"),
                        res.get("records_valid"), res.get("records_rejected"))

        logger.info("Price ingestion completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Error during price ingestion: %s", e, exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
