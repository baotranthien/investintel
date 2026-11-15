"""Supabase / PostgreSQL native RPC invocation helpers.

All callers stay dual-path compatible: on PostgreSQL (Supabase), analytics and
audit endpoints call server-side SQL/PLpgSQL RPC functions (`public.rpc_*`) to
eliminate N+1 network round-trips over WAN. On local SQLite (unit tests and
offline desktop builds), `is_postgres_session(session)` returns False and
services seamlessly execute their in-process SQLAlchemy fallback.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_ALLOWED_RPCS: frozenset[str] = frozenset({
    "rpc_get_instrument_coverage",
    "rpc_get_universe_coverage_audit",
    "rpc_get_screener_rows",
    "rpc_get_watchlist_snapshot",
    "rpc_get_portfolio_snapshot",
    "rpc_get_system_observability",
    "rpc_get_universe_overview",
    "rpc_match_document_chunks",
    "rpc_get_pit_fundamentals_batch",
    "rpc_get_cross_sectional_features",
    "rpc_refresh_analytics_views",
})

_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def is_postgres_session(session: Session | None) -> bool:
    """Return True if the SQLAlchemy session is bound to PostgreSQL."""
    if session is None:
        return False
    try:
        bind = session.get_bind()
        if bind is None:
            return False
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
        return str(dialect_name).lower().startswith("postgresql")
    except Exception:
        return False


def _coerce_pg_param(value: Any) -> tuple[Any, str]:
    """Return (bound_value, sql_cast_expr) for Postgres parameter binding."""
    if isinstance(value, datetime):
        return value.date(), "CAST(:{name} AS date)"
    if isinstance(value, date):
        return value, "CAST(:{name} AS date)"
    if isinstance(value, bool):
        return value, "CAST(:{name} AS boolean)"
    if isinstance(value, int):
        return value, "CAST(:{name} AS integer)"
    if isinstance(value, float):
        return value, "CAST(:{name} AS double precision)"
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value], "CAST(:{name} AS text[])"
    if value is None:
        return None, ":{name}"
    return str(value), "CAST(:{name} AS text)"


def call_pg_rpc(
    session: Session | None,
    func_name: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Execute `SELECT public.<func_name>(...)` on PostgreSQL and decode JSON.

    Returns `None` when not running on PostgreSQL or if the RPC cannot be
    executed (allowing callers to fall back to standard SQLAlchemy logic).
    """
    if not is_postgres_session(session):
        return None
    if func_name not in _ALLOWED_RPCS or not _IDENT_RE.match(func_name):
        raise ValueError(f"Disallowed or invalid PostgreSQL RPC name: {func_name!r}")

    bound_params: dict[str, Any] = {}
    arg_clauses: list[str] = []
    for raw_key, raw_val in (params or {}).items():
        if not _IDENT_RE.match(raw_key):
            raise ValueError(f"Invalid RPC parameter name: {raw_key!r}")
        if raw_val is None:
            # Omit None arguments so Postgres default parameter values apply cleanly
            continue
        coerced, cast_tmpl = _coerce_pg_param(raw_val)
        bound_params[raw_key] = coerced
        arg_clauses.append(f"{raw_key} => {cast_tmpl.format(name=raw_key)}")

    sql_str = f"SELECT public.{func_name}({', '.join(arg_clauses)}) AS payload"
    try:
        assert session is not None
        row = session.execute(text(sql_str), bound_params).fetchone()
        if not row:
            return None
        payload = row[0]
        if isinstance(payload, (dict, list)):
            return payload
        if isinstance(payload, str):
            return json.loads(payload)
        return payload
    except Exception as exc:
        logger.warning("Supabase RPC %s failed, using ORM fallback: %s", func_name, exc)
        try:
            assert session is not None
            session.rollback()
        except Exception:
            pass
        return None


def refresh_screener_materialized_view(session: Session | None) -> dict[str, Any] | None:
    """Refresh `mv_daily_screener_metrics` via Supabase RPC after ingestion."""
    if not is_postgres_session(session):
        return None
    result = call_pg_rpc(session, "rpc_refresh_analytics_views")
    if isinstance(result, dict):
        try:
            assert session is not None
            session.commit()
        except Exception:
            try:
                assert session is not None
                session.rollback()
            except Exception:
                pass
        return result
    return None
