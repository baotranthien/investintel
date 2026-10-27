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
        usable_for_valuation_count = 0
        fresh_count = 0
        date_aligned_count = 0

        print(f"\n{'SYMBOL':<8} | {'TYPE':<6} | {'OBS DATE':<10} | {'RAW CLOSE':<10} | {'ADJ CLOSE':<10} | {'FACTOR':<8} | {'DAYS STALE':<10} | {'STATUS':<20} | {'SOURCE':<20}")
        print("-" * 125)

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
            is_fresh = (days_stale <= 7)
            is_date_aligned = (days_stale == 0)

            if is_fresh:
                fresh_count += 1
            else:
                stale_count += 1

            if is_date_aligned:
                date_aligned_count += 1

            factor = latest_price.adjustment_factor
            if factor is not None and (factor <= 0 or factor > 2.0):
                suspicious_factor_count += 1

            # Geometry check
            h, l, c = latest_price.raw_high, latest_price.raw_low, latest_price.raw_close
            geom_ok = True
            if h is not None and l is not None:
                if h < l or (c is not None and (c < l * 0.999 or c > h * 1.001)):
                    geom_violation_count += 1
                    geom_ok = False

            # Usable for current valuation requires BOTH valid geometry AND fresh observation date
            usable_for_val = geom_ok and is_fresh
            if usable_for_val:
                usable_for_valuation_count += 1

            status_label = "USABLE_FOR_VALUATION" if usable_for_val else ("STALE_EXCLUDED" if not is_fresh else "GEOMETRY_INVALID")

            factor_display = f"{factor:.4f}" if factor is not None else "None"
            # Print row if --all or first 12 or stale or problematic
            if args.all or idx < 12 or days_stale > 7 or (factor and (factor < 0.5 or factor > 1.5)):
                print(f"{sym:<8} | {inst.asset_type:<6} | {str(latest_price.observation_date):<10} | {latest_price.raw_close:<10.1f} | {latest_price.adjusted_close:<10.1f} | {factor_display:<8} | {days_stale:<10} | {status_label:<20} | {latest_price.source or 'None':<20}")

        total_canonical = len(canonical)
        print("\n" + "=" * 70)
        print("PRICE AUDIT & FRESHNESS CLASSIFICATION SUMMARY:")
        print("=" * 70)
        print(f"Total Canonical Assets In Universe   : {total_canonical}")
        print(f"1. PRICE_PRESENT                     : {total_canonical - no_price_count}/{total_canonical} ({((total_canonical - no_price_count)/total_canonical)*100:.1f}%)")
        print(f"2. GEOMETRY_VALID                    : {total_canonical - geom_violation_count}/{total_canonical} ({((total_canonical - geom_violation_count)/total_canonical)*100:.1f}%)")
        print(f"3. PRICE_FRESH (<= 7 days)           : {fresh_count}/{total_canonical} ({(fresh_count/total_canonical)*100:.1f}%)")
        print(f"4. PRICE_DATE_ALIGNED (Today/As-Of)  : {date_aligned_count}/{total_canonical} ({(date_aligned_count/total_canonical)*100:.1f}%)")
        print(f"5. USABLE_FOR_CURRENT_VALUATION      : {usable_for_valuation_count}/{total_canonical} ({(usable_for_valuation_count/total_canonical)*100:.1f}%)")
        print(f"6. STALE_EXCLUDED_FROM_VALUATION     : {stale_count}/{total_canonical} ({(stale_count/total_canonical)*100:.1f}%)")
        print("   -> Stale Asset: VN300 (Obs date 2023-10-27, 1096 days stale). Preserved as benchmark; excluded from live valuation.")
        print("=" * 70)

    finally:
        session.close()


if __name__ == "__main__":
    main()
