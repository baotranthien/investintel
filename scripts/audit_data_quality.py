"""
InvestIntel Data Quality Audit CLI.
Read-only data-quality gate over canonical market data (adapted from vnstock-service audit pattern).
Invariants checked:
1. High < Low violations
2. Close outside [Low, High]
3. Negative/Zero prices
4. Negative volume
5. Outstanding Ingestion Failures Ledger

Exit codes:
0: Clean or warnings only
1: FAIL - at least one invariant violated
2: Audit itself could not run
"""
import sys
import os
import argparse
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from services.quality.coverage import DataCoverageService


def main():
    parser = argparse.ArgumentParser(description="InvestIntel Read-Only Data Quality Gate")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    parser.add_argument("--warn-fatal", action="store_true", help="Treat warnings as failures (exit 1)")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        report = DataCoverageService.audit_data_quality_gates(session)

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("=" * 65)
            print("INVESTINTEL DATA QUALITY AUDIT REPORT")
            print("=" * 65)
            print(f"Audit Status: {report['status']}")
            print(f"Timestamp   : {report['timestamp']}")
            print(f"Findings    : {report['findings_count']}")
            print("-" * 65)

            if report["findings"]:
                print(f"{'SEV':<8} | {'CHECK':<30} | {'COUNT':<6} | {'EXAMPLE'}")
                print("-" * 65)
                for f in report["findings"]:
                    print(f"{f['severity']:<8} | {f['check']:<30} | {f['count']:<6} | {f['example']}")
            else:
                print("All canonical price invariants passed (clean).")

            if report.get("failure_ledger"):
                print("\nOutstanding Ingestion Failures Ledger:")
                print("-" * 65)
                for fl in report["failure_ledger"][:5]:
                    print(f"- [{fl['started_at']}] {fl['provider']}/{fl['dataset']}: {fl['error']}")

            print("=" * 65)

        exit_code = report["exit_code"]
        if args.warn_fatal and report["status"] == "WARNING":
            exit_code = 1
        sys.exit(exit_code)

    except Exception as exc:
        print(f"Audit could not execute: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        session.close()


if __name__ == "__main__":
    main()
