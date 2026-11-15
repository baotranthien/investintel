"""Add additive Supabase covering indexes, materialized view, pgvector/FTS columns, and RPC functions.

Revision ID: 20261115rpc
Revises: 20261028bm
Create Date: 2026-11-15
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "20261115rpc"
down_revision: Union[str, None] = "20261028bm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_PATH = Path(__file__).resolve().parents[2] / "supabase_rpc.sql"


def _exec_raw_sql(bind, sql_text: str) -> None:
    """Execute raw multi-statement PostgreSQL script directly via DBAPI cursor without % param parsing."""
    raw_conn = bind.connection.driver_connection
    cur = raw_conn.cursor()
    try:
        cur.execute(sql_text)
    finally:
        cur.close()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite unit/local mode retains existing SQLAlchemy code paths without Postgres-specific RPCs.
        return

    sql_text = _SQL_PATH.read_text(encoding="utf-8")
    _exec_raw_sql(bind, sql_text)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _exec_raw_sql(
        bind,
        """
            DROP FUNCTION IF EXISTS public.rpc_refresh_analytics_views();
            DROP FUNCTION IF EXISTS public.rpc_get_pit_fundamentals_batch(text[], date);
            DROP FUNCTION IF EXISTS public.rpc_match_document_chunks(text, text, date, integer, boolean);
            DROP FUNCTION IF EXISTS public.rpc_get_universe_overview();
            DROP FUNCTION IF EXISTS public.rpc_get_system_observability();
            DROP FUNCTION IF EXISTS public.rpc_get_portfolio_snapshot(text, date);
            DROP FUNCTION IF EXISTS public.rpc_get_watchlist_snapshot(date, integer, integer);
            DROP FUNCTION IF EXISTS public.rpc_get_screener_rows(text, text, integer);
            DROP FUNCTION IF EXISTS public.rpc_get_universe_coverage_audit(date);
            DROP FUNCTION IF EXISTS public.rpc_get_instrument_coverage(text, date);
            DROP FUNCTION IF EXISTS public._fn_instrument_coverage_rows(date, text);
            DROP MATERIALIZED VIEW IF EXISTS public.mv_daily_screener_metrics;
            """
    )
