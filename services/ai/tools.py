from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Asset, AssetDecisionSnapshot, WatchlistItem
from services.decision.engine import build_decision_context
from services.events.engine import EventEngine
from services.macro.observations import get_latest_macro_series
from services.market.dashboard import build_market_dashboard
from services.portfolio.engine import portfolio_dashboard, portfolio_fit
from services.research.rag import DocumentRAGService


TOOL_NAMES = (
    "asset",
    "fundamentals",
    "valuation",
    "factors",
    "risk",
    "macro",
    "regime",
    "events",
    "opportunity",
    "portfolio",
    "watchlist",
    "historical_snapshot",
    "evidence",
    "document_retrieval",
)


def _status(data: Any) -> str:
    if data is None:
        return "INSUFFICIENT_DATA"
    if isinstance(data, dict):
        status = data.get("status")
        if isinstance(status, str):
            return status
        return "AVAILABLE" if data else "INSUFFICIENT_DATA"
    if isinstance(data, list):
        return "AVAILABLE" if data else "INSUFFICIENT_DATA"
    return "AVAILABLE"


class AITools:
    """Whitelisted read-only data tools; quantitative scores are never computed here."""

    @staticmethod
    def get_stock_snapshot(
        symbol: str,
        as_of: Optional[date] = None,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        close_session = session is None
        db = session or SessionLocal()
        from services.universe.registry import UniverseRegistry
        resolved = UniverseRegistry.resolve_instrument(db, symbol) if symbol else None
        normalized = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(symbol) or symbol.upper())
        requested_date = as_of or date.today()
        try:
            asset = db.query(Asset).filter(Asset.symbol == normalized).first()
            if asset is None:
                return {
                    "symbol": normalized,
                    "as_of": requested_date.isoformat(),
                    "status": "INSUFFICIENT_DATA",
                    "opportunity_score": None,
                    "risk_score": None,
                    "confidence": "INSUFFICIENT",
                    "why_now": [],
                    "why_not_now": [{
                        "claim_type": "UNCERTAINTY",
                        "text": "Asset is not present in the canonical registry.",
                    }],
                    "what_could_go_wrong": [],
                    "signal_conflict": "INSUFFICIENT_DATA",
                }

            context = build_decision_context(db, normalized, requested_date)
            modules = context.get("snapshot", {}).get("modules", {})
            opportunity = modules.get("opportunity", {})
            risk = modules.get("risk", {})
            return {
                "symbol": normalized,
                "as_of": context["as_of_date"],
                "status": context["decision_state"],
                "opportunity_score": opportunity.get("score"),
                "risk_score": risk.get("overall_score"),
                "confidence": opportunity.get("confidence", "INSUFFICIENT"),
                "why_now": context.get("why_now", []),
                "why_not_now": context.get("why_not_now", []),
                "what_could_go_wrong": context.get("what_would_make_me_wrong", []),
                "signal_conflict": "INSUFFICIENT_DATA",
                "explainability": context.get("explainability", {}),
                "evidence": context.get("evidence", []),
            }
        finally:
            if close_session:
                db.close()

    @staticmethod
    def get_market_context(session: Optional[Session] = None, as_of: Optional[date] = None) -> dict[str, Any]:
        close_session = session is None
        db = session or SessionLocal()
        requested_date = as_of or date.today()
        try:
            market = build_market_dashboard(db, requested_date).model_dump(mode="json")
            macro = get_latest_macro_series(db, requested_date).model_dump(mode="json")
            regime = market.get("market_regime", {})
            return {
                "status": market.get("status", "INSUFFICIENT_DATA"),
                "as_of_date": requested_date.isoformat(),
                "market_regime": regime.get("regime", "INSUFFICIENT_DATA"),
                "regime_confidence": regime.get("confidence"),
                "macro_growth": "INSUFFICIENT_DATA",
                "macro_liquidity": "INSUFFICIENT_DATA",
                "macro_rates": "INSUFFICIENT_DATA",
                "market": market,
                "macro": macro,
            }
        finally:
            if close_session:
                db.close()

    @staticmethod
    def get_recent_events(
        symbol: Optional[str] = None,
        session: Optional[Session] = None,
        as_of: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        events = EventEngine.get_recent_events(
            symbol=symbol,
            session=session,
            as_of=as_of or date.today(),
        )
        return [event.model_dump(mode="json") for event in events]

    @staticmethod
    def get_context(
        symbol: Optional[str | list[str]],
        as_of: date,
        tool_names: Optional[list[str]] = None,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        requested = tool_names or list(TOOL_NAMES)
        unknown = sorted(set(requested) - set(TOOL_NAMES))
        if unknown:
            raise ValueError(f"Unsupported AI tools: {', '.join(unknown)}")

        as_of = as_of or date.today()
        close_session = session is None
        db = session or SessionLocal()
        try:
            from services.universe.registry import UniverseRegistry
            
            # Normalize to list of symbols
            raw_symbols = [symbol] if isinstance(symbol, str) else (symbol or [])
            norm_symbols: list[str] = []
            for s in raw_symbols:
                if not s:
                    continue
                resolved = UniverseRegistry.resolve_instrument(db, s)
                norm = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(s) or s.upper())
                if norm and norm not in norm_symbols:
                    norm_symbols.append(norm)

            market_context = AITools.get_market_context(session=db, as_of=as_of)

            # If multi-ticker comparison requested
            if len(norm_symbols) > 1:
                combined_evidence: list[dict[str, Any]] = []
                assets_info = []
                primary_decision_state = "INSUFFICIENT_DATA"

                for sym in norm_symbols:
                    asset = db.query(Asset).filter(Asset.symbol == sym).first()
                    if asset:
                        assets_info.append({
                            "symbol": asset.symbol,
                            "name": asset.name,
                            "asset_type": asset.asset_type,
                            "exchange": asset.exchange,
                            "sector": asset.sector,
                            "registry_status": asset.status,
                        })
                        decision = build_decision_context(db, sym, as_of)
                        sym_evidence = decision.get("evidence", []) if decision else []
                        for ev in sym_evidence:
                            ev_copy = dict(ev)
                            ev_copy["symbol"] = sym
                            combined_evidence.append(ev_copy)
                        if decision and decision.get("decision_state") == "AVAILABLE":
                            primary_decision_state = "AVAILABLE"
                    else:
                        combined_evidence.append({
                            "claim_type": "UNCERTAINTY",
                            "responsible_module": "asset",
                            "metric": "asset_registry",
                            "symbol": sym,
                            "source": "asset_registry",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "INSUFFICIENT_DATA",
                            "note": f"Mã cổ phiếu {sym} không có trong cơ sở dữ liệu kiểm chứng của hệ thống.",
                        })

                # Append market context evidence
                for ev in market_context.get("market", {}).get("evidence", []):
                    ev_copy = dict(ev)
                    ev_copy.setdefault("symbol", "VN100")
                    combined_evidence.append(ev_copy)

                results = []
                for name in requested:
                    if name == "asset":
                        results.append({"name": name, "status": "AVAILABLE" if assets_info else "INSUFFICIENT_DATA", "data": assets_info})
                    elif name == "macro":
                        results.append({"name": name, "status": _status(market_context.get("macro")), "data": market_context.get("macro")})
                    elif name == "regime":
                        results.append({"name": name, "status": _status(market_context.get("market", {}).get("market_regime")), "data": market_context.get("market", {}).get("market_regime")})
                    elif name == "evidence":
                        results.append({"name": name, "status": "AVAILABLE" if combined_evidence else "INSUFFICIENT_DATA", "data": combined_evidence})
                    else:
                        results.append({"name": name, "status": "INSUFFICIENT_DATA", "data": None})

                return {
                    "symbol": ", ".join(norm_symbols),
                    "symbols": norm_symbols,
                    "as_of_date": as_of.isoformat(),
                    "decision_state": primary_decision_state,
                    "tools": results,
                    "evidence": combined_evidence,
                }

            # Single symbol path (or no symbol)
            normalized = norm_symbols[0] if norm_symbols else None
            asset = db.query(Asset).filter(Asset.symbol == normalized).first() if normalized else None
            decision = build_decision_context(db, normalized, as_of) if normalized else None
            modules = decision.get("snapshot", {}).get("modules", {}) if decision else {}
            events = AITools.get_recent_events(symbol=normalized, session=db, as_of=as_of)
            watchlist = db.query(WatchlistItem).filter(WatchlistItem.asset_id == asset.id).first() if asset else None
            watchlist_data = ({
                "thesis": watchlist.thesis,
                "horizon": watchlist.horizon,
                "invalidation": watchlist.invalidation,
                "last_reviewed_at": watchlist.last_reviewed_at.isoformat() if watchlist.last_reviewed_at else None,
            } if watchlist else None)
            snapshots = db.query(AssetDecisionSnapshot).filter(
                AssetDecisionSnapshot.asset_id == asset.id
            ).order_by(AssetDecisionSnapshot.id.desc()).limit(100).all() if asset else []
            historical = next((
                row.snapshot_data
                for row in snapshots
                if (row.snapshot_data.get("facts", {}).get("as_of_date") or "") <= as_of.isoformat()
            ), None)
            portfolio_data = {
                "portfolio": portfolio_dashboard(db, as_of),
                "portfolio_fit": portfolio_fit(db, as_of),
            }
            evidence = decision.get("evidence", []) if decision else []
            if normalized:
                for ev in evidence:
                    ev.setdefault("symbol", normalized)

            rag_service = DocumentRAGService(session=db)
            rag_docs = rag_service.retrieve_documents(
                query=normalized if normalized else "corporate update",
                ticker=normalized,
                as_of_date=as_of,
                limit=5,
            )
            document_payload = rag_docs if rag_docs["status"] == "AVAILABLE" else {
                "status": "INSUFFICIENT_DATA",
                "documents": [],
                "embedding_provider": rag_docs.get("embedding_provider", {"status": "NOT_CONFIGURED"}),
                "note": "No local document index is currently available; retrieval remains insufficient until a local corpus is indexed.",
            }
            tool_data: dict[str, Any] = {
                "asset": ({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_type": asset.asset_type,
                    "exchange": asset.exchange,
                    "sector": asset.sector,
                    "registry_status": asset.status,
                } if asset else None),
                "fundamentals": modules.get("fundamentals"),
                "valuation": modules.get("valuation"),
                "factors": modules.get("factors"),
                "risk": modules.get("risk"),
                "macro": modules.get("macro") if decision else market_context.get("macro"),
                "regime": modules.get("regime") if decision else market_context.get("market", {}).get("market_regime"),
                "events": modules.get("events") if decision else events,
                "opportunity": modules.get("opportunity"),
                "portfolio": portfolio_data,
                "watchlist": watchlist_data,
                "historical_snapshot": historical,
                "evidence": evidence or None,
                "document_retrieval": document_payload,
            }
            results = []
            for name in requested:
                data = tool_data.get(name)
                state = _status(data)
                if name == "document_retrieval":
                    state = "INSUFFICIENT_DATA"
                results.append({"name": name, "status": state, "data": data})

            return {
                "symbol": normalized,
                "symbols": norm_symbols,
                "as_of_date": as_of.isoformat(),
                "decision_state": decision.get("decision_state") if decision else market_context.get("status", "INSUFFICIENT_DATA"),
                "tools": results,
                "evidence": evidence,
            }
        finally:
            if close_session:
                db.close()