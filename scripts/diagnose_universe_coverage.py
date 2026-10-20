"""
InvestIntel Universe & Data Coverage Diagnostic CLI
Audits canonical instruments, coverage of prices, financials, valuation, and events,
and displays readiness tiers across the entire supported stock universe.
"""

import sys
import os
import json
import argparse

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from services.universe.registry import UniverseRegistry
from services.quality.coverage import DataCoverageService


def main():
    parser = argparse.ArgumentParser(description="Diagnose Universe and Market Data Coverage")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    parser.add_argument("--symbol", type=str, default=None, help="Inspect a specific stock symbol")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.symbol:
            rep = DataCoverageService.get_instrument_coverage(session, args.symbol)
            if not rep:
                print(f"Error: Symbol '{args.symbol}' could not be resolved in the canonical universe.")
                sys.exit(1)

            data = rep.to_dict()
            if args.json:
                print(json.dumps(data, indent=2, default=str))
            else:
                print("=" * 65)
                print(f"INSTRUMENT COVERAGE: {rep.canonical_symbol} ({rep.name})")
                print("=" * 65)
                print(f"Exchange        : {rep.exchange}")
                print(f"Asset Type      : {rep.asset_type}")
                print(f"Overall Status  : {rep.overall_status}")
                print(f"Analyst Ready   : {'YES' if rep.analyst_ready else 'NO'}")
                print(f"Eligible Datasets: {rep.eligible_evidence_count} / {len(rep.datasets)}")
                if rep.missing_datasets:
                    print(f"Missing Datasets: {', '.join(rep.missing_datasets)}")
                print("-" * 65)
                print(f"{'Dataset':<15} | {'Status':<18} | {'Records':<8} | {'Latest Date':<12}")
                print("-" * 65)
                for ds_name, ds in rep.datasets.items():
                    print(f"{ds_name:<15} | {ds.status:<18} | {ds.record_count:<8} | {ds.latest_date or 'N/A':<12}")
            return

        universe_audit = UniverseRegistry.audit_universe(session=session)
        coverage_audit = DataCoverageService.audit_universe_coverage(session=session)

        if args.json:
            print(json.dumps({
                "universe": universe_audit,
                "coverage": coverage_audit
            }, indent=2, default=str))
            return

        print("=" * 70)
        print("INVESTINTEL UNIVERSE & DATA COVERAGE DIAGNOSTIC REPORT")
        print("=" * 70)

        print("\n1. CANONICAL UNIVERSE BREAKDOWN")
        print("-" * 55)
        print(f"Total Canonical Instruments : {universe_audit['total_canonical_instruments']}")
        print(f"Expected Constituents Total : {universe_audit['expected_symbols_count']}")
        print(f"Resolved Constituents       : {universe_audit['resolved_count']} (Unresolved: {universe_audit['unresolved_count']})")
        print(f"By Exchange                 : {universe_audit['breakdown_by_exchange']}")
        print(f"By Asset Type               : {universe_audit['breakdown_by_asset_type']}")
        print(f"Active Index Memberships    : VN100={universe_audit['index_membership']['VN100_active_members']}, VN30={universe_audit['index_membership']['VN30_active_members']}")

        print("\n2. DATA COVERAGE SUMMARY")
        print("-" * 55)
        summary = coverage_audit["summary"]
        prices = coverage_audit["dataset_breakdown"]["prices"]
        funds = coverage_audit["dataset_breakdown"]["fundamentals_equities"]
        total = summary["total_canonical_instruments"]

        print(f"Price History (Available)  : {prices['available_count']} / {total} ({prices['coverage_rate_pct']}%)")
        print(f"Price History (Stale)      : {prices['stale_count']}")
        print(f"Price History (Missing)    : {prices['missing_count']}")
        print(f"Fundamentals (Equities)    : {funds['available_count']} active, {funds['missing_or_pending_count']} pending backfill")

        print("\n3. ANALYTICAL & AI ANALYST READINESS")
        print("-" * 55)
        print(f"Full Stack Ready (Deep Analysis)   : {summary['fully_available_for_deep_analysis']} instruments")
        print(f"Partial Ready (Callable w/ bounds) : {summary['partially_available_for_analyst']} instruments")
        print(f"Total Analyst-Callable Universe    : {summary['analyst_callable_universe']} / {total} instruments")
        print(f"Insufficient Data Instruments      : {summary['insufficient_data_instruments']}")

        print("\n4. SAMPLE INSTRUMENT GROUPS")
        print("-" * 55)
        cats = coverage_audit["categorized_instruments"]
        print(f"Full Stack Symbols     : {', '.join(cats['full_stack_symbols'])}")
        print(f"Price-Only Sample (10) : {', '.join(cats['price_only_symbols_sample'][:10])}")

        print("\n5. SYSTEMIC ROOT CAUSE & PIPELINE STATUS")
        print("-" * 55)
        print(coverage_audit["systemic_diagnostics"]["root_cause_for_partial_universe"])
        print("=" * 70)
    finally:
        session.close()


if __name__ == "__main__":
    main()
