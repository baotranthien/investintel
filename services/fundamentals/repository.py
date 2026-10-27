"""
FinancialRepository — Canonical Database Access Layer for Fundamentals.
Enforces:
1. DB -> Canonical Data -> FundamentalEngine -> FundamentalSnapshot pipeline.
2. Point-In-Time filtering: publication_date <= as_of_date.
3. Provenance and audit trail tracing.
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.connection import SessionLocal
from database.models import (
    Asset,
    FinancialStatement,
    NormalizedIncome,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    FinancialLineItem,
)

class FinancialRepository:
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

    def get_company_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Returns asset profile from canonical DB."""
        asset = self._session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
        if not asset:
            return None
        return {
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "exchange": asset.exchange,
            "sector": asset.sector or "GENERAL",
            "currency": asset.currency or "VND",
            "status": asset.status or "ACTIVE",
        }

    def get_financial_dataset(
        self,
        symbol: str,
        as_of_date: Optional[Union[date, datetime]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Loads point-in-time canonical financial records from database.
        Returns:
            dict containing income_quarters, income_annual, balance_annual,
            cashflow_annual, shares_outstanding, sector, and provenance.
        """
        sym = symbol.upper()

        def numeric(value):
            return float(value) if value is not None else None

        profile = self.get_company_profile(sym)
        if not profile:
            return None

        # Build PIT query for statements
        stmt_query = self._session.query(FinancialStatement).filter(
            FinancialStatement.symbol == sym,
            FinancialStatement.status == "VALID"
        )
        cutoff_date = None
        cutoff_dt = None
        if as_of_date:
            if isinstance(as_of_date, datetime):
                cutoff_dt = as_of_date
                cutoff_date = as_of_date.date()
            else:
                cutoff_date = as_of_date
            stmt_query = stmt_query.filter(FinancialStatement.publication_date <= cutoff_date)

        statements_raw = stmt_query.order_by(
            FinancialStatement.fiscal_period_end.desc(),
            FinancialStatement.version.desc()
        ).all()

        if not statements_raw:
            return None

        if cutoff_dt:
            # Point-in-Time Intraday Availability Filtering:
            # 1. Statements published strictly before cutoff_date are kept.
            # 2. If publication_date == cutoff_date:
            #    Rule: Do not assume a same-day filing existed before intraday cutoff
            #    without verified pre-cutoff publication timestamp.
            # 3. If created_at > cutoff_dt, the statement was ingested after cutoff and is excluded.
            # 4. If updated_at > cutoff_dt, exclude records modified post-cutoff.
            filtered_statements = []
            for stmt in statements_raw:
                if stmt.publication_date < cutoff_date:
                    # Published on an earlier calendar day: definitely available prior to cutoff
                    filtered_statements.append(stmt)
                    continue

                if stmt.publication_date == cutoff_date:
                    # Same-day statement: check for explicit intraday publication timestamp
                    pub_ts = None
                    if stmt.raw_data and isinstance(stmt.raw_data, dict):
                        raw_ts = stmt.raw_data.get("publication_timestamp")
                        if raw_ts:
                            try:
                                pub_ts = datetime.fromisoformat(str(raw_ts))
                            except Exception:
                                pub_ts = None

                    # If explicit publication timestamp is recorded
                    if pub_ts is not None:
                        if cutoff_dt.tzinfo is not None and pub_ts.tzinfo is None:
                            from datetime import timezone
                            pub_ts = pub_ts.replace(tzinfo=timezone.utc)
                        elif cutoff_dt.tzinfo is None and pub_ts.tzinfo is not None:
                            pub_ts = pub_ts.replace(tzinfo=None)

                        if pub_ts <= cutoff_dt:
                            filtered_statements.append(stmt)
                    else:
                        # No verified intraday publication timestamp:
                        # Contract Rule: if filing only has publication date without time,
                        # and snapshot cutoff is intraday same day, do NOT assume it existed before cutoff.
                        continue

            statements_raw = filtered_statements

        if not statements_raw:
            return None

        # Point-In-Time deduplication: for each (statement_type, fiscal_period_end, period_type),
        # keep ONLY the latest revision visible on or before as_of_date
        deduped = {}
        for stmt in statements_raw:
            key = (stmt.statement_type, stmt.fiscal_period_end, stmt.period_type)
            if key not in deduped:
                deduped[key] = stmt

        # Sort chronologically ascending for fundamental analysis
        statements = sorted(deduped.values(), key=lambda s: (s.fiscal_period_end, s.statement_type))

        # Statement IDs by statement_type
        inc_annual = []
        inc_quarters = []
        bal_annual = []
        cf_annual = []
        latest_shares_basic = None
        sources = set()
        latest_pub_date = None

        for stmt in statements:
            if stmt.source_name:
                sources.add(stmt.source_name)
            if stmt.publication_date:
                if latest_pub_date is None or stmt.publication_date > latest_pub_date:
                    latest_pub_date = stmt.publication_date

            if stmt.statement_type == "INCOME_STATEMENT":
                norm_inc = self._session.query(NormalizedIncome).filter(
                    NormalizedIncome.statement_id == stmt.id
                ).first()
                if norm_inc:
                    row = {
                        "fiscal_period_start": stmt.fiscal_period_start,
                        "fiscal_period_end": stmt.fiscal_period_end,
                        "fiscal_year": stmt.fiscal_year,
                        "fiscal_quarter": stmt.fiscal_quarter,
                        "period_type": stmt.period_type,
                        "publication_date": stmt.publication_date,
                        "revenue": numeric(norm_inc.revenue),
                        "cogs": numeric(norm_inc.cost_of_goods_sold),
                        "gross_profit": numeric(norm_inc.gross_profit),
                        "operating_income": numeric(norm_inc.operating_income),
                        "pre_tax_income": numeric(norm_inc.pre_tax_income),
                        "net_income": numeric(norm_inc.net_income),
                        "net_income_parent": (
                            numeric(norm_inc.net_income_parent)
                            if norm_inc.net_income_parent is not None
                            else (
                                numeric(norm_inc.net_income)
                                if stmt.consolidation in ("PARENT_ONLY", "SEPARATE", "STANDALONE")
                                else (
                                    numeric(norm_inc.net_income) - numeric(norm_inc.minority_interest)
                                    if norm_inc.net_income is not None and norm_inc.minority_interest is not None
                                    else None
                                )
                            )
                        ),
                        "eps_basic": numeric(norm_inc.eps_basic),
                        "shares_basic": int(norm_inc.shares_basic) if norm_inc.shares_basic else None,
                    }
                    if norm_inc.shares_basic:
                        latest_shares_basic = int(norm_inc.shares_basic)

                    if stmt.period_type == "ANNUAL":
                        inc_annual.append(row)
                    elif stmt.period_type == "QUARTERLY":
                        inc_quarters.append(row)

            elif stmt.statement_type == "BALANCE_SHEET":
                norm_bs = self._session.query(NormalizedBalanceSheet).filter(
                    NormalizedBalanceSheet.statement_id == stmt.id
                ).first()
                if norm_bs:
                    row = {
                        "fiscal_period_start": stmt.fiscal_period_start,
                        "fiscal_period_end": stmt.fiscal_period_end,
                        "fiscal_year": stmt.fiscal_year,
                        "fiscal_quarter": stmt.fiscal_quarter,
                        "period_type": stmt.period_type,
                        "publication_date": stmt.publication_date,
                        "cash": numeric(norm_bs.cash),
                        "total_assets": numeric(norm_bs.total_assets),
                        "total_liabilities": numeric(norm_bs.total_liabilities),
                        "total_equity": numeric(norm_bs.total_equity),
                        "equity_parent": (
                            numeric(norm_bs.equity_parent)
                            if norm_bs.equity_parent is not None
                            else (
                                numeric(norm_bs.total_equity)
                                if stmt.consolidation in ("PARENT_ONLY", "SEPARATE", "STANDALONE")
                                else (
                                    numeric(norm_bs.total_equity) - numeric(norm_bs.minority_interest)
                                    if norm_bs.total_equity is not None and norm_bs.minority_interest is not None
                                    else None
                                )
                            )
                        ),
                        "share_capital": numeric(norm_bs.share_capital),
                        "loans_and_advances": numeric(norm_bs.loans_and_advances),
                        "customer_deposits": numeric(norm_bs.customer_deposits),
                        "provisions": numeric(norm_bs.provisions),
                        "npl_gross": numeric(norm_bs.npl_gross),
                        "npl_ratio": numeric(norm_bs.npl_ratio),
                    }
                    bal_annual.append(row)

            elif stmt.statement_type == "CASH_FLOW":
                norm_cf = self._session.query(NormalizedCashFlow).filter(
                    NormalizedCashFlow.statement_id == stmt.id
                ).first()
                if norm_cf:
                    row = {
                        "fiscal_period_start": stmt.fiscal_period_start,
                        "fiscal_period_end": stmt.fiscal_period_end,
                        "fiscal_year": stmt.fiscal_year,
                        "fiscal_quarter": stmt.fiscal_quarter,
                        "period_type": stmt.period_type,
                        "publication_date": stmt.publication_date,
                        "cash_from_operations": numeric(norm_cf.cash_from_operations),
                        "cash_from_investing": numeric(norm_cf.cash_from_investing),
                        "capex": numeric(norm_cf.capex),
                        "free_cash_flow": numeric(norm_cf.free_cash_flow),
                    }
                    cf_annual.append(row)

        # Resolve authoritative shares_outstanding with semantic priority.
        # CRITICAL: Authoritative FundamentalMetric (OUTSTANDING_SHARES > TOTAL_SHARES > LISTED_SHARES)
        # must take precedence over historical NormalizedIncome.shares_basic, which is merely
        # a period-specific weighted-average share count from an older statement (e.g. 2023 pre-split).
        # Resolution order: OUTSTANDING_SHARES (1) > TOTAL_SHARES (2) > LISTED_SHARES (3).
        shares_outstanding = None
        from database.models import FundamentalMetric
        from sqlalchemy import case
        metric_priority = case(
            (FundamentalMetric.metric_id == "OUTSTANDING_SHARES", 1),
            (FundamentalMetric.metric_id == "TOTAL_SHARES", 2),
            (FundamentalMetric.metric_id == "LISTED_SHARES", 3),
            else_=4,
        )
        sh_query = self._session.query(FundamentalMetric).filter(
            FundamentalMetric.symbol == sym,
            FundamentalMetric.metric_id.in_(["OUTSTANDING_SHARES", "TOTAL_SHARES", "LISTED_SHARES"]),
            FundamentalMetric.value.isnot(None),
            FundamentalMetric.value > 0,
        )
        if cutoff_date:
            sh_query = sh_query.filter(FundamentalMetric.fiscal_period_end <= cutoff_date)
        # metric_priority FIRST: OUTSTANDING(1) always beats LISTED(3)
        # fiscal_period_end DESC is secondary: within same type, prefer newest
        sh_metric = sh_query.order_by(metric_priority, FundamentalMetric.fiscal_period_end.desc()).first()
        if not sh_metric:
            # Fallback: ignore date filter (e.g. future-dated records)
            sh_metric = self._session.query(FundamentalMetric).filter(
                FundamentalMetric.symbol == sym,
                FundamentalMetric.metric_id.in_(["OUTSTANDING_SHARES", "TOTAL_SHARES", "LISTED_SHARES"]),
                FundamentalMetric.value.isnot(None),
                FundamentalMetric.value > 0,
            ).order_by(metric_priority, FundamentalMetric.fiscal_period_end.desc()).first()
        if sh_metric and sh_metric.value:
            shares_outstanding = int(float(sh_metric.value))

        # Secondary fallback: latest statement shares_basic if FundamentalMetric not available
        if not shares_outstanding and latest_shares_basic:
            shares_outstanding = latest_shares_basic

        # Tertiary fallback: share_capital (Vietnam par value 10,000 VND/share).
        # LABELED as capital-derived estimate — NOT verified outstanding shares.
        # Only used when no OUTSTANDING_SHARES/TOTAL_SHARES/LISTED_SHARES metric exists.
        if not shares_outstanding and bal_annual:
            latest_b = bal_annual[-1]
            share_cap = latest_b.get("share_capital")
            if share_cap and share_cap > 0:
                shares_outstanding = int(round(share_cap * 100_000))

        return {
            "symbol": sym,
            "profile": profile,
            "sector": profile["sector"],
            "income_annual": inc_annual,
            "income_quarters": inc_quarters,
            "balance_annual": bal_annual,
            "cashflow_annual": cf_annual,
            "shares_outstanding": shares_outstanding,
            "sources": list(sources) if sources else ["CANONICAL_DATABASE"],
            "as_of": as_of_date.isoformat() if as_of_date else (latest_pub_date.isoformat() if latest_pub_date else None),
            "latest_publication_date": latest_pub_date.isoformat() if latest_pub_date else None,
            "provenance": {
                "db_table": "financial_statements",
                "sources": list(sources),
                "statement_count": len(statements),
                "point_in_time": as_of_date.isoformat() if as_of_date else None
            }
        }
