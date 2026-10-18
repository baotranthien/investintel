"""Add local personal portfolio, DCA, and watchlist persistence.

Revision ID: 20261001p6d
Revises: 254306c2824e
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001p6d"
down_revision: Union[str, None] = "254306c2824e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personal_portfolios",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_currency", sa.String(), nullable=False),
        sa.Column("single_name_limit", sa.Numeric(8, 6), nullable=True),
        sa.Column("sector_limit", sa.Numeric(8, 6), nullable=True),
        sa.Column("material_change_threshold", sa.Numeric(8, 6), nullable=True),
        sa.Column("core_target", sa.Numeric(8, 6), nullable=True),
        sa.Column("satellite_target", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("single_name_limit IS NULL OR (single_name_limit >= 0 AND single_name_limit <= 1)", name="single_name_limit_range"),
        sa.CheckConstraint("sector_limit IS NULL OR (sector_limit >= 0 AND sector_limit <= 1)", name="sector_limit_range"),
        sa.CheckConstraint("material_change_threshold IS NULL OR (material_change_threshold >= 0 AND material_change_threshold <= 1)", name="material_change_threshold_range"),
        sa.CheckConstraint("core_target IS NULL OR (core_target >= 0 AND core_target <= 1)", name="core_target_range"),
        sa.CheckConstraint("satellite_target IS NULL OR (satellite_target >= 0 AND satellite_target <= 1)", name="satellite_target_range"),
        sa.PrimaryKeyConstraint("id", name="pk_personal_portfolios"),
    )
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(20, 6), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("horizon", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="holding_quantity_positive"),
        sa.CheckConstraint("average_cost > 0", name="holding_average_cost_positive"),
        sa.CheckConstraint("role IN ('CORE', 'SATELLITE', 'UNASSIGNED')", name="holding_role_valid"),
        sa.CheckConstraint("horizon IS NULL OR horizon IN ('MEDIUM_TERM', 'LONG_TERM')", name="holding_horizon_valid"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name="fk_portfolio_holdings_asset_id_assets"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["personal_portfolios.id"], name="fk_portfolio_holdings_portfolio_id_personal_portfolios", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_holdings"),
        sa.UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_holding_asset"),
    )
    op.create_index("ix_portfolio_holdings_id", "portfolio_holdings", ["id"])
    op.create_index("ix_portfolio_holdings_portfolio_id", "portfolio_holdings", ["portfolio_id"])

    op.create_table(
        "manual_portfolio_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("entry_source", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("transaction_type IN ('BUY', 'SELL', 'DIVIDEND', 'FEE')", name="manual_transaction_type_valid"),
        sa.CheckConstraint("quantity > 0", name="manual_transaction_quantity_positive"),
        sa.CheckConstraint("unit_price > 0", name="manual_transaction_price_positive"),
        sa.CheckConstraint("entry_source = 'MANUAL'", name="manual_transaction_source_only"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name="fk_manual_portfolio_transactions_asset_id_assets"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["personal_portfolios.id"], name="fk_manual_portfolio_tx_portfolio", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_manual_portfolio_transactions"),
    )
    op.create_index("ix_manual_portfolio_transactions_id", "manual_portfolio_transactions", ["id"])
    op.create_index("ix_manual_portfolio_transactions_portfolio_id", "manual_portfolio_transactions", ["portfolio_id"])

    op.create_table(
        "portfolio_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("target_weight", sa.Numeric(8, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("target_weight >= 0 AND target_weight <= 1", name="portfolio_target_weight_range"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name="fk_portfolio_targets_asset_id_assets"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["personal_portfolios.id"], name="fk_portfolio_targets_portfolio_id_personal_portfolios", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_targets"),
        sa.UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_target_asset"),
    )
    op.create_index("ix_portfolio_targets_id", "portfolio_targets", ["id"])
    op.create_index("ix_portfolio_targets_portfolio_id", "portfolio_targets", ["portfolio_id"])

    op.create_table(
        "personal_dca_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("monthly_amount", sa.Integer(), nullable=False),
        sa.Column("core_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("satellite_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("monthly_amount >= 300000 AND monthly_amount <= 400000", name="dca_monthly_amount_range"),
        sa.CheckConstraint("core_pct >= 0 AND core_pct <= 1", name="dca_core_pct_range"),
        sa.CheckConstraint("satellite_pct >= 0 AND satellite_pct <= 1", name="dca_satellite_pct_range"),
        sa.CheckConstraint("core_pct + satellite_pct <= 1", name="dca_reserve_nonnegative"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["personal_portfolios.id"], name="fk_personal_dca_plans_portfolio_id_personal_portfolios", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_personal_dca_plans"),
        sa.UniqueConstraint("portfolio_id", name="uq_personal_dca_plans_portfolio_id"),
    )
    op.create_index("ix_personal_dca_plans_id", "personal_dca_plans", ["id"])

    op.create_table(
        "personal_portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["personal_portfolios.id"], name="fk_personal_portfolio_snapshots_portfolio", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_personal_portfolio_snapshots"),
    )
    op.create_index("ix_personal_portfolio_snapshots_id", "personal_portfolio_snapshots", ["id"])
    op.create_index("ix_personal_portfolio_snapshots_portfolio_id", "personal_portfolio_snapshots", ["portfolio_id"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("horizon", sa.String(), nullable=True),
        sa.Column("invalidation", sa.Text(), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("horizon IS NULL OR horizon IN ('MEDIUM_TERM', 'LONG_TERM')", name="watchlist_horizon_valid"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name="fk_watchlist_items_asset_id_assets"),
        sa.PrimaryKeyConstraint("id", name="pk_watchlist_items"),
        sa.UniqueConstraint("asset_id", name="uq_watchlist_items_asset_id"),
    )
    op.create_index("ix_watchlist_items_id", "watchlist_items", ["id"])

    op.create_table(
        "watchlist_thesis_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("previous_thesis", sa.Text(), nullable=True),
        sa.Column("new_thesis", sa.Text(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlist_items.id"], name="fk_watchlist_thesis_revisions_watchlist_id_watchlist_items", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_watchlist_thesis_revisions"),
    )
    op.create_index("ix_watchlist_thesis_revisions_id", "watchlist_thesis_revisions", ["id"])
    op.create_index("ix_watchlist_thesis_revisions_watchlist_id", "watchlist_thesis_revisions", ["watchlist_id"])

    op.create_table(
        "watchlist_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("watchlist_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlist_items.id"], name="fk_watchlist_snapshots_watchlist_id_watchlist_items", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_watchlist_snapshots"),
    )
    op.create_index("ix_watchlist_snapshots_id", "watchlist_snapshots", ["id"])
    op.create_index("ix_watchlist_snapshots_watchlist_id", "watchlist_snapshots", ["watchlist_id"])


def downgrade() -> None:
    op.drop_table("watchlist_snapshots")
    op.drop_table("watchlist_thesis_revisions")
    op.drop_table("watchlist_items")
    op.drop_table("personal_portfolio_snapshots")
    op.drop_table("personal_dca_plans")
    op.drop_table("portfolio_targets")
    op.drop_table("manual_portfolio_transactions")
    op.drop_table("portfolio_holdings")
    op.drop_table("personal_portfolios")
