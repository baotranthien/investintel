"""
Historical Replay & Point-In-Time Integrity Audit Engine.

Guarantees and verifies:
1. Strict Point-in-Time (PIT) integrity across multi-period backtest windows:
   publication_date <= as_of_date for all statements and filings.
2. Revision & restatement handling:
   - Before restatement publication date: selects version 1 (version 2 strictly invisible).
   - After restatement publication date: selects version 2 (with supersedes_id and reason).
3. Historical index membership reconstruction:
   - Ignores current is_active status to prevent survivorship bias.
   - Reconstructs accurate constituent lists as of any date T.
4. Downstream deterministic engine execution:
   - Replays Fundamentals -> Valuation -> Macro -> Regime -> Risk -> Opportunity -> Events.
   - Verifies 100% determinism across identical replays.
5. Automated detection and reporting of any look-ahead violation.
"""
import logging
from datetime import date, datetime, time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.connection import SessionLocal
from database.models import (
    Asset,
    FinancialStatement,
    Price,
    IndexMembership,
    MacroObservation,
    EventRecord,
)
from services.ingestion.point_in_time import PointInTimeService
from services.fundamentals.repository import FinancialRepository
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.valuation.builder import ValuationSnapshotBuilder
from services.macro.engine import MacroEngine, MarketRegimeEngine
from services.risk.engine import RiskEngine
from services.opportunity.engine import OpportunityEngine
from services.events.engine import EventEngine

logger = logging.getLogger(__name__)


class PITViolationError(Exception):
    """Raised when a look-ahead or future publication leak is detected."""
    pass


class HistoricalReplayRunner:
    """
    Executes historical replay across dates and audits point-in-time compliance.
    """

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._owns_session = False
        if self._session is None:
            self._session = SessionLocal()
            self._owns_session = True

    def close(self):
        if self._owns_session and self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def audit_statement_pit(self, symbol: str, as_of_date: date) -> List[Dict[str, Any]]:
        """
        Audits all financial statements visible as of as_of_date for future leakage.
        Returns list of violations.
        """
        violations = []
        financials = PointInTimeService.get_financials_as_of(self._session, symbol, as_of_date)
        for s in financials:
            if s.publication_date and s.publication_date > as_of_date:
                violations.append({
                    "type": "FUTURE_STATEMENT_LEAK",
                    "symbol": symbol,
                    "statement_id": s.id,
                    "statement_type": s.statement_type,
                    "fiscal_period_end": s.fiscal_period_end.isoformat(),
                    "publication_date": s.publication_date.isoformat(),
                    "as_of_date": as_of_date.isoformat(),
                    "severity": "CRITICAL",
                })
        return violations

    def audit_macro_pit(self, as_of_date: date) -> List[Dict[str, Any]]:
        """
        Audits macro dashboard variables as of as_of_date for future leakage.
        """
        violations = []
        dash = MacroEngine.get_dashboard(as_of_date, session=self._session)
        for var in dash.variables:
            if var.as_of and var.as_of > as_of_date:
                violations.append({
                    "type": "FUTURE_MACRO_LEAK",
                    "variable_name": var.name,
                    "variable_as_of": var.as_of.isoformat(),
                    "as_of_date": as_of_date.isoformat(),
                    "severity": "HIGH",
                })
        return violations

    def audit_events_pit(self, as_of_date: date) -> List[Dict[str, Any]]:
        """
        Audits events returned as of as_of_date for future publication timestamps.
        """
        violations = []
        events = EventEngine.get_recent_events(session=self._session, as_of=as_of_date)
        as_of_dt = datetime.combine(as_of_date, time.max)
        for ev in events:
            # If event has timezone-aware timestamp, convert as_of_dt to aware or compare date
            ev_date = ev.timestamp.date() if isinstance(ev.timestamp, (datetime, date)) else None
            if ev_date and ev_date > as_of_date:
                violations.append({
                    "type": "FUTURE_EVENT_LEAK",
                    "event_id": ev.id,
                    "event_title": ev.title,
                    "event_date": ev_date.isoformat(),
                    "as_of_date": as_of_date.isoformat(),
                    "severity": "MEDIUM",
                })
        return violations

    def verify_restatement_transition(
        self,
        symbol: str = "REV_TEST",
        pre_restatement_date: date = date(2023, 5, 1),
        post_restatement_date: date = date(2023, 9, 1),
    ) -> Dict[str, Any]:
        """
        Verifies restatement / revision transition behavior:
        - Before v2 publication: returns v1, v2 is strictly invisible.
        - After v2 publication: returns v2, supersedes_id linked to v1.
        """
        # 1. Pre-restatement check
        pre_stmts = PointInTimeService.get_financials_as_of(self._session, symbol, pre_restatement_date)
        v1_match = [s for s in pre_stmts if s.fiscal_period_end == date(2022, 12, 31)]
        pre_ok = len(v1_match) == 1 and v1_match[0].version == 1

        # Check that no version > 1 is visible
        has_future_revision = any(s.version > 1 for s in pre_stmts)

        # 2. Post-restatement check
        post_stmts = PointInTimeService.get_financials_as_of(self._session, symbol, post_restatement_date)
        v2_match = [s for s in post_stmts if s.fiscal_period_end == date(2022, 12, 31)]
        post_ok = (
            len(v2_match) == 1
            and v2_match[0].version == 2
            and v2_match[0].supersedes_id is not None
        )

        return {
            "symbol": symbol,
            "pre_restatement_date": pre_restatement_date.isoformat(),
            "pre_restatement_passed": pre_ok and not has_future_revision,
            "pre_selected_version": v1_match[0].version if v1_match else None,
            "post_restatement_date": post_restatement_date.isoformat(),
            "post_restatement_passed": post_ok,
            "post_selected_version": v2_match[0].version if v2_match else None,
            "supersedes_id": v2_match[0].supersedes_id if v2_match else None,
            "restatement_reason": v2_match[0].restatement_reason if v2_match else None,
            "passed": pre_ok and post_ok and not has_future_revision,
        }

    def verify_historical_index_membership(self) -> Dict[str, Any]:
        """
        Verifies historical index reconstruction without relying on current membership.
        Tests:
        - ROS in VN30 as of 2019-01-01 -> True (historical constituent)
        - ROS in VN30 as of 2022-01-01 -> False (exited 2020-08-03)
        - FPT in VN30 as of 2023-01-01 -> True
        - MWG in VN30 as of 2014-01-01 -> False (joined 2015-01-26)
        - MWG in VN30 as of 2016-01-01 -> True
        """
        t1_ros_2019 = PointInTimeService.is_index_member_as_of(self._session, "VN30", "ROS", date(2019, 1, 1))
        t2_ros_2022 = PointInTimeService.is_index_member_as_of(self._session, "VN30", "ROS", date(2022, 1, 1))
        t3_fpt_2023 = PointInTimeService.is_index_member_as_of(self._session, "VN30", "FPT", date(2023, 1, 1))
        t4_mwg_2014 = PointInTimeService.is_index_member_as_of(self._session, "VN30", "MWG", date(2014, 1, 1))
        t5_mwg_2016 = PointInTimeService.is_index_member_as_of(self._session, "VN30", "MWG", date(2016, 1, 1))

        constituents_2019 = PointInTimeService.get_index_constituents_as_of(self._session, "VN30", date(2019, 1, 1))
        constituents_2022 = PointInTimeService.get_index_constituents_as_of(self._session, "VN30", date(2022, 1, 1))

        passed = (
            t1_ros_2019 is True
            and t2_ros_2022 is False
            and t3_fpt_2023 is True
            and t4_mwg_2014 is False
            and t5_mwg_2016 is True
            and "ROS" in constituents_2019
            and "ROS" not in constituents_2022
        )

        return {
            "ros_in_vn30_2019": t1_ros_2019,
            "ros_in_vn30_2022": t2_ros_2022,
            "fpt_in_vn30_2023": t3_fpt_2023,
            "mwg_in_vn30_2014": t4_mwg_2014,
            "mwg_in_vn30_2016": t5_mwg_2016,
            "vn30_constituents_2019": constituents_2019,
            "vn30_constituents_2022": constituents_2022,
            "survivorship_bias_prevented": passed,
            "passed": passed,
        }

    def replay_date(self, symbol: str, as_of_date: date) -> Dict[str, Any]:
        """
        Executes a complete end-to-end replay snapshot at a given historical date.
        Audits all layers for look-ahead violations.
        """
        violations = []

        # 1. Statement audit
        violations.extend(self.audit_statement_pit(symbol, as_of_date))

        # 2. Macro audit
        violations.extend(self.audit_macro_pit(as_of_date))

        # 3. Events audit
        violations.extend(self.audit_events_pit(as_of_date))

        # 4. Ingest financial dataset as of date
        repo = FinancialRepository(self._session)
        dataset = repo.get_financial_dataset(symbol, as_of_date)

        # 5. Prices as of date
        prices = PointInTimeService.get_prices_as_of(self._session, symbol, as_of_date, limit=1)
        latest_price = prices[-1].raw_close if prices else 100000.0

        # Check price observation date <= as_of_date
        if prices and prices[-1].observation_date > as_of_date:
            violations.append({
                "type": "FUTURE_PRICE_LEAK",
                "symbol": symbol,
                "price_date": prices[-1].observation_date.isoformat(),
                "as_of_date": as_of_date.isoformat(),
                "severity": "CRITICAL",
            })

        # 6. Fundamental Snapshot
        fund_snapshot = None
        if dataset:
            builder = FundamentalSnapshotBuilder(symbol, dataset["sector"])
            fund_snapshot = builder.build_snapshot(
                income_quarters=dataset["income_quarters"],
                income_annual=dataset["income_annual"],
                balance_annual=dataset["balance_annual"],
                cashflow_annual=dataset["cashflow_annual"],
                as_of_date=as_of_date,
                shares_outstanding=dataset["shares_outstanding"],
                sources=dataset["sources"],
            )

        # 7. Valuation Snapshot
        val_builder = ValuationSnapshotBuilder(symbol, dataset["sector"] if dataset else "TECHNOLOGY")
        rev_val = None
        if dataset and dataset.get("income_annual"):
            rev_val = dataset["income_annual"][-1].get("revenue")
        elif dataset and dataset.get("income_quarters"):
            rev_val = sum(q.get("revenue", 0.0) for q in dataset["income_quarters"][-4:])

        val_input = {
            "eps_ttm": fund_snapshot["per_share"]["eps_ttm"] if fund_snapshot else None,
            "bvps": fund_snapshot["per_share"]["bvps"] if fund_snapshot else None,
            "shares_outstanding": dataset["shares_outstanding"] if dataset else 1_000_000_000,
            "revenue_ttm": rev_val,
            "net_debt": fund_snapshot["balance_sheet"]["net_debt"] if fund_snapshot else 0.0,
        }
        val_snapshot = val_builder.build(val_input, latest_price, as_of=as_of_date)

        # 8. Macro & Market Regime
        macro_dash = MacroEngine.get_dashboard(as_of_date, session=self._session)
        market_regime = MarketRegimeEngine.determine_regime(as_of_date, session=self._session)

        # 9. Events
        events = EventEngine.get_recent_events(symbol=symbol, session=self._session, as_of=as_of_date)

        # 10. Risk Profile
        risk_input = {
            "de_ratio": fund_snapshot["balance_sheet"]["de_ratio"]["value"] if fund_snapshot else None,
            "current_ratio": fund_snapshot["balance_sheet"]["current_ratio"]["value"] if fund_snapshot else None,
        }
        val_risk_input = {
            "margin_of_safety": val_snapshot.margin_of_safety
        }
        risk_profile = RiskEngine.calculate_profile(symbol, risk_input, val_risk_input, as_of=as_of_date)

        # 11. Opportunity Score
        roe_val = fund_snapshot["profitability"]["roe"]["value"] if fund_snapshot else None
        growth_val = fund_snapshot["growth"]["net_income_yoy"]["value"] if fund_snapshot else None
        de_val = fund_snapshot["balance_sheet"]["de_ratio"]["value"] if fund_snapshot else None
        opp_fund_input = {
            "roe": roe_val,
            "profit_growth_yoy": growth_val,
            "de_ratio": de_val,
        }
        opp_score = OpportunityEngine.calculate_medium_term(
            symbol,
            opp_fund_input,
            val_risk_input,
            risk_profile,
            macro_dash,
            events,
            as_of_date,
        )

        return {
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "latest_price": latest_price,
            "statements_visible": dataset["provenance"]["statement_count"] if dataset else 0,
            "valuation_base": val_snapshot.composite_fair_value.range.base,
            "market_regime": market_regime.regime,
            "risk_score": risk_profile.total_risk_score,
            "opportunity_score": opp_score.opportunity_score,
            "opportunity_confidence": opp_score.confidence,
            "events_count": len(events),
            "violations_detected": len(violations),
            "violations": violations,
        }

    def run_replay_suite(
        self,
        symbols: List[str] = ["FPT", "VCB", "HPG"],
        test_dates: List[date] = [
            date(2023, 1, 15),
            date(2023, 5, 1),
            date(2023, 8, 15),
            date(2023, 8, 25),
            date(2023, 10, 24),
            date(2023, 10, 26),
        ]
    ) -> Dict[str, Any]:
        """
        Runs comprehensive multi-date historical replay across symbols and dates.
        """
        results = []
        total_violations = 0

        # 1. Historical Index Membership Audit
        index_audit = self.verify_historical_index_membership()
        if not index_audit["passed"]:
            total_violations += 1

        # 2. Restatement / Revision Transition Audit
        restatement_audit = self.verify_restatement_transition()
        if not restatement_audit["passed"]:
            total_violations += 1

        # 3. Multi-Date Replay Across Symbols
        for dt in test_dates:
            for sym in symbols:
                res = self.replay_date(sym, dt)
                results.append(res)
                total_violations += res["violations_detected"]

        # 4. Determinism Audit: replay same date twice and assert exact equivalence
        det1 = self.replay_date(symbols[0], test_dates[0])
        det2 = self.replay_date(symbols[0], test_dates[0])
        deterministic = (
            det1["opportunity_score"] == det2["opportunity_score"]
            and det1["risk_score"] == det2["risk_score"]
            and det1["valuation_base"] == det2["valuation_base"]
        )
        if not deterministic:
            total_violations += 1

        passed = total_violations == 0

        return {
            "status": "PASS" if passed else "FAIL",
            "total_replay_points": len(results),
            "total_violations": total_violations,
            "index_membership_audit": index_audit,
            "restatement_audit": restatement_audit,
            "deterministic_replay": deterministic,
            "replay_details": results,
            "summary": (
                f"Historical Replay PASSED: {len(results)} replay points audited with 0 look-ahead violations."
                if passed else
                f"Historical Replay FAILED: {total_violations} look-ahead or determinism violations detected."
            )
        }
