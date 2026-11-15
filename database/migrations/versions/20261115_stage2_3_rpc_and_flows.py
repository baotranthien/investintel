"""Add Stage 2/3 daily foreign flows table and upgrade hybrid pgvector + cross-sectional factor RPCs.

Revision ID: 20261115stage23
Revises: 20261115rpc
Create Date: 2026-11-15
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "20261115stage23"
down_revision: Union[str, None] = "20261115rpc"
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
        DROP FUNCTION IF EXISTS public.rpc_get_cross_sectional_features(date, text);
        DROP FUNCTION IF EXISTS public.rpc_match_document_chunks(text, text, date, integer, boolean, text);
        """,
    )
