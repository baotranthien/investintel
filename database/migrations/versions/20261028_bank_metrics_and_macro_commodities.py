"""Add bank_metrics and macro_commodities tables for deep banking & commodity intelligence.

Revision ID: 20261028bm
Revises: 20261002p6g
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261028bm"
down_revision: Union[str, None] = "20261002p6g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. bank_metrics table
    op.create_table(
        "bank_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_date", sa.Date(), nullable=False),
        sa.Column("fiscal_period", sa.String(), nullable=False),
        sa.Column("credit_growth", sa.Float(), nullable=True),
        sa.Column("nim", sa.Float(), nullable=True),
        sa.Column("casa_ratio", sa.Float(), nullable=True),
        sa.Column("npl_ratio", sa.Float(), nullable=True),
        sa.Column("llr_ratio", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=True, server_default="CANONICAL_FINANCIAL_STATEMENTS"),
        sa.Column("status", sa.String(), nullable=True, server_default="AVAILABLE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name=op.f("fk_bank_metrics_asset_id_assets")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_metrics")),
        sa.UniqueConstraint("asset_id", "fiscal_period", name="uq_bank_metrics_asset_period"),
    )
    op.create_index(op.f("ix_bank_metrics_asset_id"), "bank_metrics", ["asset_id"], unique=False)
    op.create_index(op.f("ix_bank_metrics_fiscal_date"), "bank_metrics", ["fiscal_date"], unique=False)
    op.create_index(op.f("ix_bank_metrics_id"), "bank_metrics", ["id"], unique=False)

    # 2. macro_commodities table
    op.create_table(
        "macro_commodities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commodity_code", sa.String(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True, server_default="USD/barrel"),
        sa.Column("source", sa.String(), nullable=True, server_default="PUBLIC_COMMODITY_FEED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_macro_commodities")),
        sa.UniqueConstraint("commodity_code", "observation_date", name="uq_commodity_code_date"),
    )
    op.create_index(op.f("ix_macro_commodities_commodity_code"), "macro_commodities", ["commodity_code"], unique=False)
    op.create_index(op.f("ix_macro_commodities_id"), "macro_commodities", ["id"], unique=False)
    op.create_index(op.f("ix_macro_commodities_observation_date"), "macro_commodities", ["observation_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_macro_commodities_observation_date"), table_name="macro_commodities")
    op.drop_index(op.f("ix_macro_commodities_id"), table_name="macro_commodities")
    op.drop_index(op.f("ix_macro_commodities_commodity_code"), table_name="macro_commodities")
    op.drop_table("macro_commodities")

    op.drop_index(op.f("ix_bank_metrics_id"), table_name="bank_metrics")
    op.drop_index(op.f("ix_bank_metrics_fiscal_date"), table_name="bank_metrics")
    op.drop_index(op.f("ix_bank_metrics_asset_id"), table_name="bank_metrics")
    op.drop_table("bank_metrics")
