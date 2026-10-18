"""Add persisted asset decision snapshots.

Revision ID: 20261001p6e
Revises: 20261001p6d
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001p6e"
down_revision: Union[str, None] = "20261001p6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asset_decision_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_decision_snapshots_id", "asset_decision_snapshots", ["id"])
    op.create_index("ix_asset_decision_snapshots_asset_id", "asset_decision_snapshots", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_decision_snapshots_asset_id", table_name="asset_decision_snapshots")
    op.drop_index("ix_asset_decision_snapshots_id", table_name="asset_decision_snapshots")
    op.drop_table("asset_decision_snapshots")