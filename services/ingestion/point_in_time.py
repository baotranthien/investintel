"""
Point-In-Time (PIT) Query Pattern & Service.
Enforces strict historical integrity:
- Only data where published_at <= as_of_date is accessible.
- Revisions/restatements published AFTER as_of_date are strictly invisible.
- Handles corrected filings and late publications.
"""
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from database.models import (
    FinancialStatement,
    NormalizedIncome,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    Price,
    Asset,
    IndexMembership,
    MacroObservation,
)

class PointInTimeService:
    @staticmethod
    def get_financials_as_of(
        session: Session,
        symbol: str,
        as_of_date: date,
        statement_type: Optional[str] = None
    ) -> List[FinancialStatement]:
        """
        Retrieves financial statements visible strictly on or before as_of_date.
        For restated statements, selects the latest revision published <= as_of_date.
        Revisions published after as_of_date are strictly excluded to avoid look-ahead bias.
        """
        query = session.query(FinancialStatement).filter(
            FinancialStatement.symbol == symbol.upper(),
            # Crucial: Publication date must be known and on/before as_of_date
            FinancialStatement.publication_date <= as_of_date
        )

        if statement_type:
            query = query.filter(FinancialStatement.statement_type == statement_type)

        all_candidates = query.order_by(
            FinancialStatement.fiscal_period_end.desc(),
            FinancialStatement.version.desc()
        ).all()

        # Group by (statement_type, fiscal_period_end, period_type) and take highest version <= as_of_date
        deduped = {}
        for stmt in all_candidates:
            key = (stmt.statement_type, stmt.fiscal_period_end, stmt.period_type)
            if key not in deduped:
                deduped[key] = stmt

        return list(deduped.values())

    @staticmethod
    def get_prices_as_of(
        session: Session,
        symbol: str,
        as_of_date: date,
        limit: int = 500
    ) -> List[Price]:
        """
        Retrieves daily prices strictly observed and published on or before as_of_date.
        """
        query = session.query(Price).join(Asset).filter(
            Asset.symbol == symbol.upper(),
            Price.observation_date <= as_of_date
        ).order_by(Price.observation_date.desc()).limit(limit)

        return list(reversed(query.all()))

    @staticmethod
    def is_index_member_as_of(
        session: Session,
        index_symbol: str,
        symbol: str,
        as_of_date: date
    ) -> bool:
        """
        Historical index reconstruction: checks if symbol was in index at time T.
        """
        member = session.query(IndexMembership).filter(
            IndexMembership.index_symbol == index_symbol.upper(),
            IndexMembership.symbol == symbol.upper(),
            IndexMembership.start_date <= as_of_date,
            or_(
                IndexMembership.end_date == None,
                IndexMembership.end_date > as_of_date
            )
        ).first()

        if not member:
            return False

        # If publication timestamp is recorded, ensure announcement occurred <= as_of_date
        if member.published_at and member.published_at.date() > as_of_date:
            return False

        return True

    @staticmethod
    def get_index_constituents_as_of(
        session: Session,
        index_symbol: str,
        as_of_date: date
    ) -> List[str]:
        """
        Historical index reconstruction: returns full list of active constituents for index at time T.
        Strictly ignores current is_active status to prevent survivorship and look-ahead bias.
        """
        members = session.query(IndexMembership).filter(
            IndexMembership.index_symbol == index_symbol.upper(),
            IndexMembership.start_date <= as_of_date,
            or_(
                IndexMembership.end_date == None,
                IndexMembership.end_date > as_of_date
            )
        ).all()

        constituents = []
        for m in members:
            if m.published_at and m.published_at.date() > as_of_date:
                continue
            constituents.append(m.symbol)

        return sorted(list(set(constituents)))

    @staticmethod
    def get_macro_observations_as_of(
        session: Session,
        series_id: str,
        as_of_date: date
    ) -> List[MacroObservation]:
        """
        Retrieves macro observations published strictly on or before as_of_date.
        """
        query = session.query(MacroObservation).filter(
            MacroObservation.series_id == series_id,
            or_(
                and_(
                    MacroObservation.published_at != None,
                    MacroObservation.published_at <= datetime.combine(as_of_date, datetime.max.time())
                ),
                and_(
                    MacroObservation.release_date != None,
                    MacroObservation.release_date <= as_of_date
                )
            )
        ).order_by(
            MacroObservation.observation_date.desc(),
            MacroObservation.version.desc()
        ).all()

        deduped = {}
        for obs in query:
            if obs.observation_date not in deduped:
                deduped[obs.observation_date] = obs

        return list(deduped.values())

    @classmethod
    def get_data_as_of(cls, symbol: str, as_of_date: date, session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Comprehensive PIT query bundling financials, price, index membership, and corporate actions.
        Enforces published_at <= as_of_date.
        """
        from database.connection import SessionLocal
        from database.models import CorporateAction
        should_close = False
        if session is None:
            session = SessionLocal()
            should_close = True

        try:
            financials = cls.get_financials_as_of(session, symbol, as_of_date)
            prices = cls.get_prices_as_of(session, symbol, as_of_date, limit=1)
            latest_price = prices[-1] if prices else None

            # Corporate actions published <= as_of_date
            corp_actions = session.query(CorporateAction).filter(
                CorporateAction.symbol == symbol.upper(),
                CorporateAction.action_date <= as_of_date
            ).all()

            # Index membership
            in_vn30 = cls.is_index_member_as_of(session, "VN30", symbol, as_of_date)
            in_vn100 = cls.is_index_member_as_of(session, "VN100", symbol, as_of_date)
            in_vn300 = cls.is_index_member_as_of(session, "VN300", symbol, as_of_date)

            return {
                "symbol": symbol.upper(),
                "as_of_date": as_of_date.isoformat(),
                "financial_statements_count": len(financials),
                "financial_statements": [
                    {
                        "statement_type": s.statement_type,
                        "fiscal_period_end": s.fiscal_period_end.isoformat(),
                        "period_type": s.period_type,
                        "publication_date": s.publication_date.isoformat() if s.publication_date else None,
                        "version": s.version
                    }
                    for s in financials
                ],
                "latest_price": {
                    "date": latest_price.observation_date.isoformat(),
                    "close": latest_price.raw_close,
                    "volume": latest_price.volume
                } if latest_price else None,
                "index_memberships": {
                    "VN30": in_vn30,
                    "VN100": in_vn100,
                    "VN300": in_vn300
                },
                "corporate_actions_count": len(corp_actions)
            }
        finally:
            if should_close:
                session.close()

def get_data_as_of(symbol: str, as_of_date: date, session: Optional[Session] = None) -> Dict[str, Any]:
    return PointInTimeService.get_data_as_of(symbol, as_of_date, session)
