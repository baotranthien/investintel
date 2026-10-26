import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sqlalchemy import desc
from database.connection import SessionLocal
from database.models import Asset, Price, DataLineage

symbols = ["HPG", "FPT", "ACB", "VCB", "MBB", "MWG", "VNM", "SSI"]

session = SessionLocal()
try:
    print("=== CHECKING SYMBOLS ===")
    for sym in symbols:
        asset = session.query(Asset).filter_by(symbol=sym).first()
        if not asset:
            print(f"{sym}: NOT FOUND")
            continue
        print(f"\n--- {sym} (asset_id={asset.id}) ---")
        # Get last 5 prices
        prices = session.query(Price).filter_by(asset_id=asset.id).order_by(desc(Price.observation_date)).limit(5).all()
        for p in prices:
            print(f"Date: {p.observation_date} | Raw Close: {p.raw_close} | Adj Close: {p.adjusted_close} | Factor: {p.adjustment_factor} | Src: {p.source} | Status: {p.status}")
            
        # Check lineage for latest price
        if prices:
            latest = prices[0]
            lineage = session.query(DataLineage).filter_by(record_table="prices", record_id=str(latest.id)).first()
            if lineage:
                print(f"  Lineage: raw_source={lineage.raw_source}, url={lineage.url}, retrieved_at={lineage.retrieved_at}")
            else:
                print("  Lineage: NONE")
finally:
    session.close()
