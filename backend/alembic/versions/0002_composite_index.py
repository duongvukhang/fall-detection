"""Add composite index for dashboard KPI/aggregation queries

Every dashboard load filters `stats` by (user_id, event_type, timestamp)
together (see routes.dashboard_kpi / dashboard_aggregations). The original
schema only had three separate single-column indexes, forcing the planner to
intersect them instead of doing one covering scan. This is additive and
non-breaking — safe to run on an existing DB.

Revision ID: 0002_composite_index
Revises: 0001_initial
Create Date: audit-hardening pass
"""
from alembic import op

revision = "0002_composite_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_stats_user_type_ts",
        "stats",
        ["user_id", "event_type", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_stats_user_type_ts", table_name="stats")