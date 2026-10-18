"""Persist analyst briefs, scheduled jobs, and evidence-backed alerts.

Revision ID: 20261001p6h
Revises: 20261001p6e
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001p6h"
down_revision: Union[str, None] = "20261001p6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_briefs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brief_type", sa.String(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_analyst_briefs"),
        sa.UniqueConstraint("idempotency_key", name="uq_analyst_briefs_idempotency_key"),
    )
    op.create_index("ix_analyst_briefs_id", "analyst_briefs", ["id"])
    op.create_index("ix_analyst_briefs_brief_type", "analyst_briefs", ["brief_type"])
    op.create_index("ix_analyst_briefs_as_of_date", "analyst_briefs", ["as_of_date"])

    op.create_table(
        "analyst_automation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_key", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_analyst_automation_jobs"),
        sa.UniqueConstraint("job_key", name="uq_analyst_automation_jobs_job_key"),
    )
    op.create_index("ix_analyst_automation_jobs_id", "analyst_automation_jobs", ["id"])
    op.create_index("ix_analyst_automation_jobs_job_type", "analyst_automation_jobs", ["job_type"])

    op.create_table(
        "analyst_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_analyst_alerts"),
        sa.UniqueConstraint("alert_id", name="uq_analyst_alerts_alert_id"),
    )
    op.create_index("ix_analyst_alerts_id", "analyst_alerts", ["id"])
    op.create_index("ix_analyst_alerts_symbol", "analyst_alerts", ["symbol"])
    op.create_index("ix_analyst_alerts_kind", "analyst_alerts", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_analyst_alerts_kind", table_name="analyst_alerts")
    op.drop_index("ix_analyst_alerts_symbol", table_name="analyst_alerts")
    op.drop_index("ix_analyst_alerts_id", table_name="analyst_alerts")
    op.drop_table("analyst_alerts")
    op.drop_index("ix_analyst_automation_jobs_job_type", table_name="analyst_automation_jobs")
    op.drop_index("ix_analyst_automation_jobs_id", table_name="analyst_automation_jobs")
    op.drop_table("analyst_automation_jobs")
    op.drop_index("ix_analyst_briefs_as_of_date", table_name="analyst_briefs")
    op.drop_index("ix_analyst_briefs_brief_type", table_name="analyst_briefs")
    op.drop_index("ix_analyst_briefs_id", table_name="analyst_briefs")
    op.drop_table("analyst_briefs")