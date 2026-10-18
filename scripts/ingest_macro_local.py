"""
Parser and Ingestion Script for Local Macroeconomic Datasets (GSO & SBV).
Reads normalized CSV from data/macro/vnm_macro_indicators.csv and pushes records
into PostgreSQL via IngestionPipeline.

Strictly preserves:
- Point-In-Time publication_date and release_date (vintage alignment).
- Lineage checksums (SHA-256) and audit logging.
- SQL NULL vs 0.0 distinction.
"""
import sys
import os
import csv
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from database.models import MacroSeries, DataSource
from services.ingestion.base import MacroDataPoint
from services.ingestion.pipeline import IngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_macro_local")


def ingest_local_macro_indicators(csv_path: str = "data/macro/vnm_macro_indicators.csv"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Macro dataset not found at {csv_path}")

    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db)
        sources = {s.name.upper(): s.id for s in db.query(DataSource).all()}

        # Group data by series_id
        grouped: dict[str, list[dict]] = {}
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["series_id"].strip()
                if sid not in grouped:
                    grouped[sid] = []
                grouped[sid].append(row)

        logger.info("Found %d distinct macro series in %s", len(grouped), csv_path)

        for sid, rows in grouped.items():
            first_row = rows[0]
            prov = first_row["provider"].strip().upper()
            sname = first_row["series_name"].strip()
            unit = first_row["unit"].strip()
            freq = first_row["frequency"].strip()

            source_id = sources.get(prov)
            # Ensure MacroSeries exists in DB
            m_series = db.query(MacroSeries).filter(MacroSeries.id == sid).first()
            if not m_series:
                m_series = MacroSeries(
                    id=sid,
                    name=sname,
                    provider=prov,
                    frequency=freq,
                    unit=unit,
                    currency="VND" if "VND" in unit else "PERCENT",
                    scale=1.0,
                    source_id=source_id
                )
                db.add(m_series)
                db.flush()

            # Build MacroDataPoint records
            records = []
            for r in rows:
                obs_d = datetime.strptime(r["observation_date"].strip(), "%Y-%m-%d").date()
                pub_d = datetime.strptime(r["publication_date"].strip(), "%Y-%m-%d").date()
                val = float(r["value"].strip())
                records.append(MacroDataPoint(
                    series_id=sid,
                    observation_date=obs_d,
                    release_date=pub_d,
                    value=val,
                    unit=unit,
                    frequency=freq
                ))

            res = pipeline.ingest_macro_series(
                provider=prov,
                series_id=sid,
                records=records,
                source_url=f"file://{os.path.abspath(csv_path)}",
                source_id=source_id
            )
            db.commit()
            logger.info("[%s/%s] Result: status=%s, received=%s, inserted=%s, updated=%s",
                        prov, sid, res.get("status"), res.get("records_received"),
                        res.get("records_inserted"), res.get("records_updated"))

        logger.info("Local macro ingestion finished successfully.")
    except Exception as e:
        db.rollback()
        logger.error("Failed to ingest local macro data: %s", e, exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/macro/vnm_macro_indicators.csv"
    ingest_local_macro_indicators(path)
