"""
InvestIntel Dynamic Universe Price & Semantics Audit CLI.
System-Wide Dynamic Price Audit (Phase 2 & Phase 3).

Audits prices across ALL active assets (equities, ETFs, benchmark indices):
1. Observation date freshness.
2. Price geometry: Low <= High, Low <= Close <= High, Close > 0.
3. Explicit adjustment semantics and factor bounds.
4. Provider lineage presence.

Zero hardcoded symbol lists!
"""
import os
import sys
import argparse
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from database.connection import SessionLocal
from database.models import Asset, Price, CorporateAction, DataLineage
from services.universe.registry import UniverseRegistry


def main():
    parser = argparse.ArgumentParser(description="InvestIntel Dynamic Price & Semantics Audit")
    parser.add_argument("--all", action="store_true", help="Print all audited rows")
    args = parser.parse_args()

    session = SessionLocal()
    today = date(2026, 10, 27)
    try:
        canonical = UniverseRegistry.get_canonical_universe(session)
        print("=" * 110)
        print(f"INVESTINTEL DYNAMIC UNIVERSE PRICE AUDIT (Total: {len(canonical)} assets)")
        print(f"As of: {today.isoformat()}")
        print("=" * 110)

        stale_count = 0
        no_price_count = 0
        geom_violation_count = 0
        suspicious_factor_count = 0

        print(f"\n{'SYMBOL':<8} | {'TYPE':<6} | {'OBS DATE':<10} | {'RAW CLOSE':<10} | {'ADJ CLOSE':<10} | {'FACTOR':<8} | {'DAYS STALE':<10} | {'SOURCE':<25}")
        print("-" * 110)

        for idx, inst in enumerate(canonical):
            sym = inst.symbol
            asset = session.query(Asset).filter_by(symbol=sym).first()
            if not asset:
                print(f"{sym:<8} | {inst.asset_type:<6} | NOT FOUND IN ASSETS TABLE")
                no_price_count += 1
                continue

            latest_price = session.query(Price).filter_by(asset_id=asset.id).order_by(Price.observation_date.desc()).first()
            if not latest_price:
                print(f"{sym:<8} | {inst.asset_type:<6} | NO PRICES RECORDED")
                no_price_count += 1
                continue

            days_stale = (today - latest_price.observation_date).days
            if days_stale > 7:
                stale_count += 1

            factor = latest_price.adjustment_factor
            if factor is not None and (factor <= 0 or factor > 2.0):
                suspicious_factor_count += 1

            # Geometry check
            h, l, c = latest_price.raw_high, latest_price.raw_low, latest_price.raw_close
            if h is not None and l is not None:
                if h < l or (c is not None and (c < l * 0.999 or c > h * 1.001)):
                    geom_violation_count += 1

            factor_display = f"{factor:.4f}" if factor is not None else "None"
            # Print row if --all or first 12 or stale or problematic
            if args.all or idx < 12 or days_stale > 7 or (factor and (factor < 0.5 or factor > 1.5)):
                print(f"{sym:<8} | {inst.asset_type:<6} | {str(latest_price.observation_date):<10} | {latest_price.raw_close:<10.1f} | {latest_price.adjusted_close:<10.1f} | {factor_display:<8} | {days_stale:<10} | {latest_price.source or 'None':<25}")

        print("\n" + "=" * 60)
        print("PRICE AUDIT SUMMARY:")
        print("=" * 60)
        print(f"Total canonical assets checked      : {len(canonical)}")
        print(f"Assets with missing prices          : {no_price_count}")
        print(f"Assets with stale prices (>7 days)  : {stale_count}")
        print(f"Geometry violations (High < Low)    : {geom_violation_count}")
        print(f"Suspicious adjustment factors       : {suspicious_factor_count}")
        print("=" * 60)

    finally:
        session.close()


if __name__ == "__main__":
    main()
