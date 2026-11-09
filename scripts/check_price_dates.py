import sys, os
sys.path.insert(0, os.path.abspath("."))
from database.connection import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Checking prices > 2026-11-10:")
    gt10 = conn.execute(text("SELECT count(*) FROM prices WHERE observation_date > '2026-11-10';")).scalar()
    print("Prices > 2026-11-10:", gt10)
    
    print("Checking macro_observations on or after 2026-11-10:")
    m10 = conn.execute(text("SELECT count(*) FROM macro_observations WHERE observation_date >= '2026-11-10';")).scalar()
    print("Macro >= 2026-11-10:", m10)

    print("Checking staging_records on or after 2026-11-10:")
    s10 = conn.execute(text("SELECT count(*) FROM staging_records WHERE created_at >= '2026-11-10';")).scalar()
    print("Staging created >= 2026-11-10:", s10)
