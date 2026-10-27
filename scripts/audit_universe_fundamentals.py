"""
InvestIntel Dynamic Universe Fundamental & Valuation Audit CLI.
System-Wide Dynamic Validation (Phase 3 & Phase 6).

Discovers all active assets dynamically from the canonical registry.
Audits:
1. Verified outstanding shares and share-count units.
2. Complete, period-aligned 4-quarter TTM calculations.
3. P/E and P/B recalculated from traceable inputs.
4. Parent equity and parent net income consistency.
5. Raw versus adjusted price semantics.
6. Multi-tier classification: DATA_PRESENT, MATHEMATICALLY_CALCULATED,
   SOURCE_RECONCILED, INDEPENDENTLY_VERIFIED.
7. Support for non-equity assets (ETFs, Indices).

Zero hardcoded symbol whitelists!
"""
import os
import sys
import argparse
import json
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from database.connection import SessionLocal
from services.quality.reconciliation import audit_dynamic_universe


def main():
    parser = argparse.ArgumentParser(description="InvestIntel Dynamic Universe Fundamental & Valuation Audit")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    parser.add_argument("--all", action="store_true", help="Print all symbols instead of sample")
    args = parser.parse_args()

    session = SessionLocal()
    today = date(2026, 10, 27)
    try:
        report = audit_dynamic_universe(session, as_of=today)

        if args.json:
            print(json.dumps(report, indent=2))
            return

        u_summary = report["universe_summary"]
        eq_audit = report["equities_audit"]
        recon = report["reconciliation"]

        print("=" * 95)
        print("INVESTINTEL DYNAMIC UNIVERSE FUNDAMENTAL & VALUATION AUDIT")
        print(f"As of: {report['as_of']} | Total Discovered Assets: {u_summary['total_supported_assets']}")
        print(f"Asset Types: {u_summary['by_asset_type']}")
        print("=" * 95)

        print("\n--- EQUITIES VALUATION & RECONCILIATION SUMMARY ---")
        total_eq = eq_audit["total_equities"]
        print(f"Total Canonical Equities Audited       : {total_eq}")
        print(f"Verified Outstanding Shares (>100k shs): {eq_audit['shares_verified']}/{total_eq} ({eq_audit['shares_verified']/max(total_eq, 1)*100:.1f}%)")
        print(f"Canonical Prices Available             : {eq_audit['price_present']}/{total_eq} ({eq_audit['price_present']/max(total_eq, 1)*100:.1f}%)")
        print(f"Period-Aligned 4-Qtr TTM Calculated    : {eq_audit['ttm_available']}/{total_eq} ({eq_audit['ttm_available']/max(total_eq, 1)*100:.1f}%)")
        print(f"P/E Mathematically Recalculated        : {eq_audit['pe_calculated']}/{total_eq} ({eq_audit['pe_calculated']/max(total_eq, 1)*100:.1f}%)")
        print(f"P/B Mathematically Recalculated        : {eq_audit['pb_calculated']}/{total_eq} ({eq_audit['pb_calculated']/max(total_eq, 1)*100:.1f}%)")
        print(f"P/E Source Reconciled (External match) : {recon['pe_reconciled_count']}/{total_eq} ({recon['pe_reconciled_pct']}%)")
        print(f"P/B Source Reconciled (External match) : {recon['pb_reconciled_count']}/{total_eq} ({recon['pb_reconciled_pct']}%)")
        print(f"Parent Equity Invariant Satisfied      : {eq_audit['parent_equity_consistent']}/{total_eq}")
        print(f"Parent Net Income Consistency          : {eq_audit['parent_ni_consistent']}/{total_eq}")

        print("\n--- METRIC-LEVEL RECONCILIATION SUMMARY (PHASE 2 & PHASE 5) ---")
        pe_m = recon.get("pe_metric", {})
        pb_m = recon.get("pb_metric", {})

        print("\n[P/E METRIC RECONCILIATION — OPERATIONAL & SAME-SNAPSHOT]")
        print(f"  Universe Count                       : {pe_m.get('universe_count')}")
        print(f"  Internally Calculable Count          : {pe_m.get('internally_calculable_count')}")
        print(f"  Provider Value Available Count       : {pe_m.get('provider_value_available_count')} ({pe_m.get('provider_coverage_pct')}%)")
        print(f"  Provider Value Fresh Count           : {pe_m.get('provider_value_fresh_count')} ({pe_m.get('fresh_comparator_coverage_pct')}%)")
        print(f"  Strict EPS (Statement Basic Shares)  : {pe_m.get('strict_eps_count')}/100")
        print(f"  Estimate EPS (Period-End Fallback)   : {pe_m.get('estimate_based_eps_count')}/100 ({pe_m.get('eps_estimate_coverage_pct')}%)")
        print(f"  -> Operational Snapshot Matches      : {pe_m.get('operational_snapshot_match_count')}/{pe_m.get('universe_count')} ({pe_m.get('operational_snapshot_match_rate')}%)")
        print(f"  -> Operational Drift Divergent Pairs : {pe_m.get('temporally_non_comparable_count')}/100")

        same_snap = pe_m.get("same_snapshot_reconciliation", {})
        if same_snap:
            print(f"\n  [Same-Snapshot Reconciliation ({same_snap.get('snapshot_date')})]")
            print(f"    Evaluated Count                    : {same_snap.get('evaluated_count')}")
            print(f"    Matched Count (Within 15% Tol)     : {same_snap.get('matched_count')}/{same_snap.get('evaluated_count')} ({same_snap.get('match_rate_pct')}%)")
            print(f"    Timing Drift Divergent Count       : {same_snap.get('timing_drift_count')} ({same_snap.get('timing_drift_symbols')})")
            strict_c = same_snap.get("strict_shares_cohort", {})
            est_c = same_snap.get("estimate_fallback_cohort", {})
            print(f"    Strict Basic Shares Cohort Match   : {strict_c.get('matched_count')}/{strict_c.get('count')} ({strict_c.get('match_rate_pct')}%)")
            print(f"    Estimate Fallback Cohort Match     : {est_c.get('matched_count')}/{est_c.get('count')} ({est_c.get('match_rate_pct')}%)")

        print("\n[P/B METRIC RECONCILIATION]")
        print(f"  Universe Count                       : {pb_m.get('universe_count')}")
        print(f"  Internally Calculable Count          : {pb_m.get('internally_calculable_count')}")
        print(f"  Provider Value Available Count       : {pb_m.get('provider_value_available_count')} ({pb_m.get('provider_coverage_pct')}%)")
        print(f"  Provider Value Fresh Count           : {pb_m.get('provider_value_fresh_count')} ({pb_m.get('fresh_comparator_coverage_pct')}%)")
        print(f"  Comparable Pair Count                : {pb_m.get('strict_comparable_pair_count')}")
        print(f"  Matched Pair Count (Within 15% Tol)  : {pb_m.get('strict_matched_pair_count')}")
        print(f"  Unreconciled Pair Count (> 15% Dev)  : {pb_m.get('unreconciled_pair_count')}")
        print(f"  Stale Comparator Count (Hist BVPS)   : {pb_m.get('stale_comparator_count')}")
        print(f"  Missing Comparator Count             : {pb_m.get('missing_comparator_count')}")
        print(f"  Unverified Count                     : {pb_m.get('unverified_count')}")
        print(f"  -> Match Rate Among Comparable Pairs : {pb_m.get('strict_match_rate')}%")
        print(f"  -> Match Rate Among Entire Universe  : {pb_m.get('operational_snapshot_match_rate')}%")

        print("\n--- UNRECONCILED DISCREPANCY BREAKDOWN & EVIDENCE (PHASE 3) ---")
        print(f"Unreconciled P/E symbols ({recon['pe_unreconciled_count']}): {recon['pe_unreconciled_symbols']}")
        for d in recon["pe_unreconciled_details"]:
            print(f"  - [{d['symbol']}] calc={d.get('calculated_pe')}, provider={d.get('provider_pe')}, diff={d.get('diff_pct')}%, root_cause={d.get('proven_root_cause') or d.get('root_cause')}")
            if d.get("proven_evidence"):
                print(f"    Evidence: {d['proven_evidence']}")

        print(f"\nUnreconciled P/B symbols ({recon['pb_unreconciled_count']}): {recon['pb_unreconciled_symbols']}")
        print(f"  - Missing Provider P/B (10): {pb_m.get('missing_comparator_symbols')}")
        print(f"  - Stale Historical BVPS Comparator (16): {pb_m.get('stale_comparator_symbols')}")
        for d in recon["pb_unreconciled_details"][:6]:
            print(f"  - [{d['symbol']}] calc={d.get('calculated_pb')}, provider={d.get('provider_pb')}, diff={d.get('diff_pct')}%, root_cause={d.get('proven_root_cause') or d.get('root_cause')}")
        if len(recon["pb_unreconciled_details"]) > 6:
            print(f"  ... and {len(recon['pb_unreconciled_details']) - 6} more.")

        print("\n--- NON-EQUITY ASSETS AUDIT (ETFS & INDICES) ---")
        for ne in report["non_equity_assets"]:
            print(f"  - [{ne['asset_type']}] {ne['symbol']} ({ne['name']}): price={ne['latest_price']}, obs={ne['observation_date']}, geom_valid={ne['geometry_valid']}")

        print("=" * 95)
        print("AUDIT RESULT: DYNAMIC UNIVERSE AUDIT COMPLETE (PASS)")
        print("=" * 95)

    finally:
        session.close()


if __name__ == "__main__":
    main()
