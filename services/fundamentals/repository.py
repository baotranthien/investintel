"""
FinancialRepository — Canonical Database Access Layer for Fundamentals.
Enforces:
1. DB -> Canonical Data -> FundamentalEngine -> FundamentalSnapshot pipeline.
2. Point-In-Time filtering: publication_date <= as_of_date.
3. Provenance and audit trail tracing.
"""
from datetime import date, datetime, timezone
from typing import Optional, Dict, Any, List, Union, Iterable
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.connection import SessionLocal
from database.models import (
    Asset,
    CorporateAction,
    FinancialStatement,
    FundamentalMetric,
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

    def get_company_profile(self, symbol: str, asset: Optional[Asset] = None) -> Optional[Dict[str, Any]]:
        """Returns asset profile from canonical DB."""
        if asset is None:
            asset = self._session.query(Asset).filter(Asset.symbol == symbol.upper()).first()
        if not asset:
            return None
        from services.fundamentals.sector_models import get_sector_for_symbol
        return {
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "exchange": asset.exchange,
            "sector": get_sector_for_symbol(symbol, asset.sector),
            "currency": asset.currency or "VND",
            "status": asset.status or "ACTIVE",
        }

    def get_financial_dataset(
        self,
        symbol: str,
        as_of_date: Optional[Union[date, datetime]] = None,
        asset: Optional[Asset] = None,
    ) -> Optional[Dict[str, Any]]:
        """Loads point-in-time canonical financial records from database for one symbol."""
        sym = symbol.upper()
        assets_by_symbol = {sym: asset} if asset is not None else None
        return self.get_financial_datasets_batch(
            [sym],
            as_of_date=as_of_date,
            assets_by_symbol=assets_by_symbol,
        ).get(sym)

    @staticmethod
    def _chunked(items: List[Any], chunk_size: int = 3000) -> Iterable[List[Any]]:
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]

    @staticmethod
    def _filter_statements_pit(
        statements_raw: List[FinancialStatement],
        cutoff_date: date,
        cutoff_dt: datetime,
    ) -> List[FinancialStatement]:
        """Point-in-time intraday availability filtering for filings matching cutoff_date."""
        filtered_statements: List[FinancialStatement] = []
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
        return filtered_statements

    def get_financial_datasets_batch(
        self,
        symbols: Iterable[str],
        as_of_date: Optional[Union[date, datetime]] = None,
        assets_by_symbol: Optional[Dict[str, Asset]] = None,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Batch-loads point-in-time financial datasets across many symbols in constant query count."""
        norm_syms = list(dict.fromkeys(s.upper() for s in symbols if s))
        if not norm_syms:
            return {}

        results: Dict[str, Optional[Dict[str, Any]]] = {sym: None for sym in norm_syms}
        asset_map: Dict[str, Asset] = {
            k.upper(): v for k, v in (assets_by_symbol or {}).items() if k and v is not None
        }
        missing_asset_syms = [s for s in norm_syms if s not in asset_map]
        if missing_asset_syms:
            for chunk in self._chunked(missing_asset_syms):
                for asset_row in self._session.query(Asset).filter(Asset.symbol.in_(chunk)).all():
                    if asset_row.symbol:
                        asset_map[asset_row.symbol.upper()] = asset_row

        profiles: Dict[str, Dict[str, Any]] = {}
        for sym in norm_syms:
            profile = self.get_company_profile(sym, asset=asset_map.get(sym))
            if profile:
                profiles[sym] = profile

        active_syms = list(profiles.keys())
        if not active_syms:
            return results

        cutoff_date: Optional[date] = None
        cutoff_dt: Optional[datetime] = None
        if as_of_date:
            if isinstance(as_of_date, datetime):
                cutoff_dt = as_of_date
                cutoff_date = as_of_date.date()
            else:
                cutoff_date = as_of_date

        statements_raw: List[FinancialStatement] = []
        for chunk in self._chunked(active_syms):
            stmt_query = self._session.query(FinancialStatement).filter(
                FinancialStatement.symbol.in_(chunk),
                FinancialStatement.status == "VALID",
            )
            if cutoff_date:
                stmt_query = stmt_query.filter(FinancialStatement.publication_date <= cutoff_date)
            statements_raw.extend(
                stmt_query.order_by(
                    FinancialStatement.fiscal_period_end.desc(),
                    FinancialStatement.version.desc(),
                ).all()
            )

        if not statements_raw:
            return results

        if cutoff_dt and cutoff_date is not None:
            statements_raw = self._filter_statements_pit(statements_raw, cutoff_date, cutoff_dt)
            if not statements_raw:
                return results

        deduped_by_sym: Dict[str, Dict[tuple, FinancialStatement]] = {}
        for stmt in statements_raw:
            sym = stmt.symbol.upper()
            sym_dedup = deduped_by_sym.setdefault(sym, {})
            key = (stmt.statement_type, stmt.fiscal_period_end, stmt.period_type)
            if key not in sym_dedup:
                sym_dedup[key] = stmt

        stmts_by_sym: Dict[str, List[FinancialStatement]] = {
            sym: sorted(sym_dedup.values(), key=lambda s: (s.fiscal_period_end, s.statement_type))
            for sym, sym_dedup in deduped_by_sym.items()
            if sym_dedup
        }
        syms_with_stmts = list(stmts_by_sym.keys())
        if not syms_with_stmts:
            return results

        all_stmt_ids = [s.id for sym_stmts in stmts_by_sym.values() for s in sym_stmts]
        inc_by_stmt: Dict[Any, NormalizedIncome] = {}
        bal_by_stmt: Dict[Any, NormalizedBalanceSheet] = {}
        cf_by_stmt: Dict[Any, NormalizedCashFlow] = {}
        for chunk in self._chunked(all_stmt_ids):
            for row in self._session.query(NormalizedIncome).filter(NormalizedIncome.statement_id.in_(chunk)).all():
                inc_by_stmt[row.statement_id] = row
            for row in self._session.query(NormalizedBalanceSheet).filter(NormalizedBalanceSheet.statement_id.in_(chunk)).all():
                bal_by_stmt[row.statement_id] = row
            for row in self._session.query(NormalizedCashFlow).filter(NormalizedCashFlow.statement_id.in_(chunk)).all():
                cf_by_stmt[row.statement_id] = row

        sh_rows_by_sym: Dict[str, List[FundamentalMetric]] = {}
        for chunk in self._chunked(syms_with_stmts):
            for m in (
                self._session.query(FundamentalMetric)
                .filter(
                    FundamentalMetric.symbol.in_(chunk),
                    FundamentalMetric.metric_id.in_(["OUTSTANDING_SHARES", "TOTAL_SHARES", "LISTED_SHARES"]),
                    FundamentalMetric.value.isnot(None),
                    FundamentalMetric.value > 0,
                )
                .all()
            ):
                if m.symbol:
                    sh_rows_by_sym.setdefault(m.symbol.upper(), []).append(m)

        ca_rows_by_sym: Dict[str, List[CorporateAction]] = {}
        for chunk in self._chunked(syms_with_stmts):
            ca_query = self._session.query(CorporateAction).filter(CorporateAction.symbol.in_(chunk))
            if cutoff_date:
                ca_query = ca_query.filter(func.coalesce(CorporateAction.ex_date, CorporateAction.action_date) <= cutoff_date)
            for ca in ca_query.order_by(func.coalesce(CorporateAction.ex_date, CorporateAction.action_date).asc()).all():
                if ca.symbol:
                    ca_rows_by_sym.setdefault(ca.symbol.upper(), []).append(ca)

        for sym in syms_with_stmts:
            results[sym] = self._assemble_financial_dataset(
                sym=sym,
                profile=profiles[sym],
                statements=stmts_by_sym[sym],
                inc_by_stmt=inc_by_stmt,
                bal_by_stmt=bal_by_stmt,
                cf_by_stmt=cf_by_stmt,
                sh_rows=sh_rows_by_sym.get(sym, []),
                ca_rows=ca_rows_by_sym.get(sym, []),
                cutoff_date=cutoff_date,
                as_of_date=as_of_date,
            )
        return results

    @staticmethod
    def _assemble_financial_dataset(
        sym: str,
        profile: Dict[str, Any],
        statements: List[FinancialStatement],
        inc_by_stmt: Dict[Any, NormalizedIncome],
        bal_by_stmt: Dict[Any, NormalizedBalanceSheet],
        cf_by_stmt: Dict[Any, NormalizedCashFlow],
        sh_rows: List[FundamentalMetric],
        ca_rows: List[CorporateAction],
        cutoff_date: Optional[date],
        as_of_date: Optional[Union[date, datetime]],
    ) -> Dict[str, Any]:
        """Assemble normalized statements, share count, and corporate actions for one symbol."""

        def numeric(value):
            return float(value) if value is not None else None

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
                norm_inc = inc_by_stmt.get(stmt.id)
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
                        "cost_of_goods_sold": numeric(norm_inc.cost_of_goods_sold),
                        "gross_profit": numeric(norm_inc.gross_profit),
                        "selling_expense": numeric(norm_inc.selling_expense),
                        "general_admin_expense": numeric(norm_inc.general_admin_expense),
                        "operating_expense": numeric(norm_inc.operating_expense),
                        "operating_income": numeric(norm_inc.operating_income),
                        "ebit": numeric(norm_inc.ebit) if norm_inc.ebit is not None else numeric(norm_inc.operating_income),
                        "ebitda": numeric(norm_inc.ebitda),
                        "interest_income": numeric(norm_inc.interest_income),
                        "interest_expense": numeric(norm_inc.interest_expense),
                        "other_income": numeric(norm_inc.other_income),
                        "other_expense": numeric(norm_inc.other_expense),
                        "pre_tax_income": numeric(norm_inc.pre_tax_income),
                        "income_tax": numeric(norm_inc.income_tax),
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
                        "minority_interest": numeric(norm_inc.minority_interest),
                        "eps_basic": numeric(norm_inc.eps_basic),
                        "eps_diluted": numeric(norm_inc.eps_diluted),
                        "shares_basic": int(norm_inc.shares_basic) if norm_inc.shares_basic else None,
                        "shares_diluted": int(norm_inc.shares_diluted) if norm_inc.shares_diluted else None,
                    }
                    if norm_inc.shares_basic:
                        latest_shares_basic = int(norm_inc.shares_basic)

                    if stmt.period_type == "ANNUAL":
                        inc_annual.append(row)
                    elif stmt.period_type == "QUARTERLY":
                        inc_quarters.append(row)

            elif stmt.statement_type == "BALANCE_SHEET":
                norm_bs = bal_by_stmt.get(stmt.id)
                if norm_bs:
                    row = {
                        "fiscal_period_start": stmt.fiscal_period_start,
                        "fiscal_period_end": stmt.fiscal_period_end,
                        "fiscal_year": stmt.fiscal_year,
                        "fiscal_quarter": stmt.fiscal_quarter,
                        "period_type": stmt.period_type,
                        "publication_date": stmt.publication_date,
                        "cash": numeric(norm_bs.cash),
                        "short_term_investments": numeric(norm_bs.short_term_investments),
                        "accounts_receivable": numeric(norm_bs.accounts_receivable),
                        "inventory": numeric(norm_bs.inventory),
                        "other_current_assets": numeric(norm_bs.other_current_assets),
                        "total_current_assets": numeric(norm_bs.total_current_assets),
                        "ppe": numeric(norm_bs.ppe),
                        "intangibles": numeric(norm_bs.intangibles),
                        "long_term_investments": numeric(norm_bs.long_term_investments),
                        "other_non_current_assets": numeric(norm_bs.other_non_current_assets),
                        "total_assets": numeric(norm_bs.total_assets),
                        "accounts_payable": numeric(norm_bs.accounts_payable),
                        "short_term_debt": numeric(norm_bs.short_term_debt),
                        "other_current_liabilities": numeric(norm_bs.other_current_liabilities),
                        "total_current_liabilities": numeric(norm_bs.total_current_liabilities),
                        "long_term_debt": numeric(norm_bs.long_term_debt),
                        "other_non_current_liabilities": numeric(norm_bs.other_non_current_liabilities),
                        "total_liabilities": numeric(norm_bs.total_liabilities),
                        "share_capital": numeric(norm_bs.share_capital),
                        "retained_earnings": numeric(norm_bs.retained_earnings),
                        "other_equity": numeric(norm_bs.other_equity),
                        "minority_interest": numeric(norm_bs.minority_interest),
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
                                    else numeric(norm_bs.total_equity)
                                )
                            )
                        ),
                        "loans_and_advances": numeric(norm_bs.loans_and_advances),
                        "customer_deposits": numeric(norm_bs.customer_deposits),
                        "provisions": numeric(norm_bs.provisions),
                        "npl_gross": numeric(norm_bs.npl_gross),
                        "npl_ratio": numeric(norm_bs.npl_ratio),
                    }
                    bal_annual.append(row)

            elif stmt.statement_type == "CASH_FLOW":
                norm_cf = cf_by_stmt.get(stmt.id)
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
                        "cash_from_financing": numeric(norm_cf.cash_from_financing),
                        "capex": numeric(norm_cf.capex),
                        "dividends_paid": numeric(norm_cf.dividends_paid),
                        "debt_issued": numeric(norm_cf.debt_issued),
                        "debt_repaid": numeric(norm_cf.debt_repaid),
                        "share_issuance": numeric(norm_cf.share_issuance),
                        "share_buyback": numeric(norm_cf.share_buyback),
                        "depreciation_amortization": numeric(norm_cf.depreciation_amortization),
                        "free_cash_flow": numeric(norm_cf.free_cash_flow),
                    }
                    cf_annual.append(row)

        # Resolve authoritative shares_outstanding with semantic priority.
        # CRITICAL: Authoritative FundamentalMetric (OUTSTANDING_SHARES > TOTAL_SHARES > LISTED_SHARES)
        # must take precedence over historical NormalizedIncome.shares_basic, which is merely
        # a period-specific weighted-average share count from an older statement (e.g. 2023 pre-split).
        # Resolution order: OUTSTANDING_SHARES (1) > TOTAL_SHARES (2) > LISTED_SHARES (3).
        shares_outstanding = None
        priority_map = {
            "OUTSTANDING_SHARES": 1,
            "TOTAL_SHARES": 2,
            "LISTED_SHARES": 3,
        }
        pit_sh_rows = [
            m
            for m in sh_rows
            if not cutoff_date or (m.fiscal_period_end is not None and m.fiscal_period_end <= cutoff_date)
        ]
        candidate_rows = pit_sh_rows if pit_sh_rows else sh_rows
        sh_metric = (
            min(
                candidate_rows,
                key=lambda m: (
                    priority_map.get(m.metric_id, 4),
                    -(m.fiscal_period_end.toordinal() if m.fiscal_period_end else 0),
                ),
            )
            if candidate_rows
            else None
        )
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

        # Preloaded Point-in-Time CorporateActions and historical share checkpoints for IAS 33 weighted shares
        corporate_actions = [
            {
                "action_date": ca.action_date,
                "ex_date": ca.ex_date,
                "payment_date": ca.payment_date,
                "action_type": ca.action_type,
                "ratio": float(ca.ratio) if ca.ratio is not None else None,
                "value": float(ca.value) if ca.value is not None else None,
                "notes": ca.notes,
                "source": ca.source,
            }
            for ca in ca_rows
        ]

        sh_history_rows = sorted(
            pit_sh_rows,
            key=lambda m: (m.fiscal_period_end or date.min),
        )
        shares_history = [
            {
                "metric_id": m.metric_id,
                "fiscal_period_end": m.fiscal_period_end,
                "effective_date": m.as_of_publication_date or m.fiscal_period_end,
                "value": float(m.value),
            }
            for m in sh_history_rows
            if m.value is not None and float(m.value) > 0
        ]

        return {
            "symbol": sym,
            "profile": profile,
            "sector": profile["sector"],
            "income_annual": inc_annual,
            "income_quarters": inc_quarters,
            "balance_annual": bal_annual,
            "cashflow_annual": cf_annual,
            "shares_outstanding": shares_outstanding,
            "corporate_actions": corporate_actions,
            "shares_history": shares_history,
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
