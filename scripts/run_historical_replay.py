"""
CLI Runner for Historical Replay & Point-In-Time Integrity Audit.

Usage:
    python scripts/run_historical_replay.py
"""
import sys
import os
import json
from datetime import date

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import SessionLocal, init_db
from database.models import Asset, FinancialStatement
from services.ingestion.historical_replay import HistoricalReplayRunner


def setup_revision_fixture(session):
    """
    Ensures canonical revision test fixture (REV_TEST) exists for restatement audit.
    v1: published 2023-03-15
    v2: restatement published 2023-08-20, supersedes v1
    """
    asset = session.query(Asset).filter(Asset.symbol == "REV_TEST").first()
    if not asset:
        asset = Asset(
            symbol="REV_TEST",
            name="Revision Test Corp",
            asset_type="STOCK",
            exchange="HOSE",
            sector="TECHNOLOGY",
            status="ACTIVE"
        )
        session.add(asset)
        session.flush()

    # Check v1
    stmt_v1 = session.query(FinancialStatement).filter(
        FinancialStatement.symbol == "REV_TEST",
        FinancialStatement.statement_type == "INCOME_STATEMENT",
        FinancialStatement.fiscal_period_end == date(2022, 12, 31),
        FinancialStatement.version == 1
    ).first()
    if not stmt_v1:
        stmt_v1 = FinancialStatement(
            asset_id=asset.id,
            symbol="REV_TEST",
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=date(2022, 12, 31),
            fiscal_year=2022,
            period_type="ANNUAL",
            publication_date=date(2023, 3, 15),
            version=1,
            is_superseded=True,
            status="VALID"
        )
        session.add(stmt_v1)
        session.flush()

    # Check v2
    stmt_v2 = session.query(FinancialStatement).filter(
        FinancialStatement.symbol == "REV_TEST",
        FinancialStatement.statement_type == "INCOME_STATEMENT",
        FinancialStatement.fiscal_period_end == date(2022, 12, 31),
        FinancialStatement.version == 2
    ).first()
    if not stmt_v2:
        stmt_v2 = FinancialStatement(
            asset_id=asset.id,
            symbol="REV_TEST",
            statement_type="INCOME_STATEMENT",
            fiscal_period_end=date(2022, 12, 31),
            fiscal_year=2022,
            period_type="ANNUAL",
            publication_date=date(2023, 8, 20),
            version=2,
            supersedes_id=stmt_v1.id,
            restatement_reason="Audit adjustment",
            is_superseded=False,
            status="VALID"
        )
        session.add(stmt_v2)
        session.flush()

    session.commit()


def main():
    print("=" * 80)
    print("HISTORICAL REPLAY & POINT-IN-TIME (PIT) INTEGRITY AUDIT")
    print("=" * 80)

    init_db()
    session = SessionLocal()

    try:
        # Setup test fixture for restatement transition audit
        setup_revision_fixture(session)

        runner = HistoricalReplayRunner(session=session)

        symbols = ["FPT", "VCB", "HPG"]
        test_dates = [
            date(2023, 1, 15),
            date(2023, 5, 1),
            date(2023, 8, 15),  # Before v2 restatement (2023-08-20)
            date(2023, 8, 25),  # After v2 restatement (2023-08-20)
            date(2023, 10, 24), # Before FPT Q3 2023 pub (2023-10-25)
            date(2023, 10, 26), # After FPT Q3 2023 pub (2023-10-25)
        ]

        print(f"\n1. Executing Replay across {len(symbols)} symbols and {len(test_dates)} dates...")
        report = runner.run_replay_suite(symbols=symbols, test_dates=test_dates)

        # Print Section 1: Index Membership
        idx = report["index_membership_audit"]
        print("\n" + "-" * 80)
        print("A. HISTORICAL INDEX MEMBERSHIP AUDIT (SURVIVORSHIP BIAS PREVENTION)")
        print("-" * 80)
        print(f"  * ROS in VN30 as of 2019-01-01 (Historical Constituent): {idx['ros_in_vn30_2019']} (Expected: True)")
        print(f"  * ROS in VN30 as of 2022-01-01 (After 2020 Exit):        {idx['ros_in_vn30_2022']} (Expected: False)")
        print(f"  * FPT in VN30 as of 2023-01-01 (Active Member):          {idx['fpt_in_vn30_2023']} (Expected: True)")
        print(f"  * MWG in VN30 as of 2014-01-01 (Before 2015 Entry):     {idx['mwg_in_vn30_2014']} (Expected: False)")
        print(f"  * MWG in VN30 as of 2016-01-01 (After 2015 Entry):      {idx['mwg_in_vn30_2016']} (Expected: True)")
        print(f"  * VN30 Constituents (2019-01-01): {idx['vn30_constituents_2019']}")
        print(f"  * VN30 Constituents (2022-01-01): {idx['vn30_constituents_2022']}")
        print(f"  -> Index Membership PIT Audit: {'PASSED' if idx['passed'] else 'FAILED'}")

        # Print Section 2: Restatement & Revision Transition
        rst = report["restatement_audit"]
        print("\n" + "-" * 80)
        print("B. RESTATEMENT & REVISION TRANSITION AUDIT (LOOK-AHEAD LEAK PREVENTION)")
        print("-" * 80)
        print(f"  * Pre-Restatement Date:  {rst['pre_restatement_date']} (Before v2 pub on 2023-08-20)")
        print(f"    - Version Selected:    v{rst['pre_selected_version']} (Expected: v1)")
        print(f"    - Pre-Restatement OK:  {rst['pre_restatement_passed']}")
        print(f"  * Post-Restatement Date: {rst['post_restatement_date']} (After v2 pub on 2023-08-20)")
        print(f"    - Version Selected:    v{rst['post_selected_version']} (Expected: v2)")
        print(f"    - Supersedes ID:       {rst['supersedes_id']}")
        print(f"    - Restatement Reason:  {rst['restatement_reason']}")
        print(f"    - Post-Restatement OK: {rst['post_restatement_passed']}")
        print(f"  -> Restatement Transition Audit: {'PASSED' if rst['passed'] else 'FAILED'}")

        # Print Section 3: Deterministic Downstream Replay Details
        print("\n" + "-" * 80)
        print("C. MULTI-PERIOD REPLAY AUDIT & LOOK-AHEAD VERIFICATION")
        print("-" * 80)
        print(f"{'Date':<12} | {'Symbol':<6} | {'Price':<10} | {'Stmts':<5} | {'Regime':<10} | {'Risk':<6} | {'Opp Score':<10} | {'Violations'}")
        print("-" * 80)
        for d in report["replay_details"]:
            print(
                f"{d['as_of_date']:<12} | {d['symbol']:<6} | {d['latest_price']:<10.1f} | "
                f"{d['statements_visible']:<5} | {d['market_regime']:<10} | {d['risk_score']:<6.1f} | "
                f"{d['opportunity_score']:<10.1f} | {d['violations_detected']}"
            )

        print("-" * 80)
        print(f"Deterministic Replay (same inputs produce identical outputs): {report['deterministic_replay']}")
        print(f"Total Replay Points:     {report['total_replay_points']}")
        print(f"Total PIT Violations:    {report['total_violations']}")
        print(f"Final Status:            {report['status']}")
        print("=" * 80)

        if report["status"] != "PASS":
            sys.exit(1)
        print("\n[SUCCESS] Historical replay completed with 0 look-ahead violations!")

    finally:
        session.close()


if __name__ == "__main__":
    main()
