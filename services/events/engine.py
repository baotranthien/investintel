from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import NewsEvent, EventImpact
from database.connection import SessionLocal
from database.models import EventRecord

class EventEngine:
    @staticmethod
    def get_recent_events(
        symbol: Optional[str] = None,
        session: Optional[Session] = None,
        as_of: Optional[date] = None
    ) -> List[NewsEvent]:
        """
        Retrieves canonical events from database.
        Translates stored EventRecord into structured NewsEvent.
        If no events exist in database, returns EMPTY list (NO_DATA) — never fabricated fake events.
        If as_of is provided, strictly filters EventRecord.published_at <= as_of to prevent look-ahead bias.
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            query = session.query(EventRecord)
            if as_of:
                from datetime import time
                as_of_dt = datetime.combine(as_of, time.max)
                query = query.filter(EventRecord.published_at <= as_of_dt)

            records = query.order_by(EventRecord.published_at.desc()).all()

            events: List[NewsEvent] = []
            for r in records:
                # If symbol is specified, filter by matching affected symbol or general events
                if symbol:
                    sym_upper = symbol.upper()
                    # Check if symbol matches or affected sectors / entities match
                    aff_sectors = r.affected_sectors or []
                    impacts_data = r.impacts or []
                    has_match = any(
                        imp.get("entity_name", "").upper() == sym_upper for imp in impacts_data
                    ) or sym_upper in str(r.title).upper() or sym_upper in str(r.description).upper()
                    if not has_match and not ("GLOBAL" in str(r.countries).upper() or "ALL" in aff_sectors):
                        continue

                parsed_impacts = [
                    EventImpact(
                        entity_name=imp.get("entity_name", ""),
                        entity_type=imp.get("entity_type", "COMPANY"),
                        direction=imp.get("direction", "NO_MATERIAL_EVIDENCE"),
                        magnitude=imp.get("magnitude", "LOW"),
                        confidence=imp.get("confidence", "LOW"),
                        evidence=imp.get("evidence", "")
                    )
                    for imp in (r.impacts or [])
                ]

                parsed_sources = []
                for s in (r.sources or []):
                    if isinstance(s, dict):
                        parsed_sources.append(str(s.get("name") or s.get("url") or s))
                    else:
                        parsed_sources.append(str(s))

                events.append(
                    NewsEvent(
                        id=r.id,
                        title=r.title,
                        description=r.description,
                        event_type=r.event_type,
                        materiality=r.materiality,
                        severity=r.severity,
                        sentiment=r.sentiment,
                        countries=r.countries or [],
                        affected_sectors=r.affected_sectors or [],
                        impacts=parsed_impacts,
                        sources=parsed_sources,
                        timestamp=r.published_at or datetime.now()
                    )
                )

            return events
        finally:
            if close_session:
                session.close()
