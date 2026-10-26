import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import date, timedelta
from database.connection import SessionLocal
from database.models import Asset, Price, CorporateAction, DataLineage
from services.universe.registry import UniverseRegistry

session = SessionLocal()
try:
    canonical = UniverseRegistry.get_canonical_universe(session)
    equities = [item for item in canonical if item.asset_type == "STOCK"]
    print(f"Auditing {len(equities)} canonical equities...\n")
    
    stale_count = 0
    adj_discrepancy_count = 0
    no_price_count = 0
    suspicious_factor_count = 0
    
    today = date(2026, 10, 27)
    
    print(f"{'SYMBOL':<8} | {'OBS DATE':<10} | {'RAW CLOSE':<10} | {'ADJ CLOSE':<10} | {'FACTOR':<8} | {'DAYS STALE':<10} | {'SOURCE':<30}")
    print("-" * 100)
    
    for eq in equities:
        asset = session.query(Asset).filter_by(symbol=eq.symbol).first()
        if not asset:
            print(f"{eq.symbol:<8} | NOT FOUND IN ASSETS TABLE")
            no_price_count += 1
            continue
            
        latest_price = session.query(Price).filter_by(asset_id=asset.id).order_by(Price.observation_date.desc()).first()
        if not latest_price:
            print(f"{eq.symbol:<8} | NO PRICES RECORDED")
            no_price_count += 1
            continue
            
        days_stale = (today - latest_price.observation_date).days
        if days_stale > 7:
            stale_count += 1
            
        factor = latest_price.adjustment_factor
        if factor is not None and (factor <= 0 or factor > 2.0):
            suspicious_factor_count += 1
            
        # Check if symbol has corporate actions but adjustment_factor == 1.0
        actions = session.query(CorporateAction).filter_by(symbol=eq.symbol).all()
        has_div_split = any(a.action_type in ("STOCK_DIVIDEND", "STOCK_SPLIT", "RIGHTS_ISSUE") for a in actions)
        
        # Check if raw == adj
        raw_eq_adj = (latest_price.raw_close == latest_price.adjusted_close)
        
        if eq.symbol in ["ACB", "FPT", "HPG", "VCB", "MBB", "MWG", "VNM", "SSI"] or days_stale > 7 or (factor and (factor < 0.5 or factor > 1.5)):
            print(f"{eq.symbol:<8} | {str(latest_price.observation_date):<10} | {latest_price.raw_close:<10.1f} | {latest_price.adjusted_close:<10.1f} | {factor or 1.0:<8.4f} | {days_stale:<10} | {latest_price.source or 'None':<30}")

    print("\n--- AUDIT SUMMARY ---")
    print(f"Total canonical equities: {len(equities)}")
    print(f"Equities with missing prices: {no_price_count}")
    print(f"Equities with stale prices (>7 days): {stale_count}")
    print(f"Equities with suspicious adjustment factors: {suspicious_factor_count}")
finally:
    session.close()
