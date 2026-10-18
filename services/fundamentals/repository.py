"""
FinancialRepository — Canonical Database Access Layer for Fundamentals.
Enforces:
1. DB -> Canonical Data -> FundamentalEngine -> FundamentalSnapshot pipeline.
2. Point-In-Time filtering: publication_date <= as_of_date.
3. Provenance and audit trail tracing.
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List
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
        as_of_date: Optional[date] = None
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
        if as_of_date:
            stmt_query = stmt_query.filter(FinancialStatement.publication_date <= as_of_date)

        statements_raw = stmt_query.order_by(
            FinancialStatement.fiscal_period_end.desc(),
            FinancialStatement.version.desc()
        ).all()

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
        shares_outstanding = None
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
                        "net_income_parent": numeric(
                            norm_inc.net_income_parent
                            if norm_inc.net_income_parent is not None
                            else norm_inc.net_income
                        ),
                        "eps_basic": numeric(norm_inc.eps_basic),
                        "shares_basic": int(norm_inc.shares_basic) if norm_inc.shares_basic else None,
                    }
                    if norm_inc.shares_basic:
                        shares_outstanding = int(norm_inc.shares_basic)

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
                        "equity_parent": numeric(
                            norm_bs.equity_parent
                            if norm_bs.equity_parent is not None
                            else norm_bs.total_equity
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
