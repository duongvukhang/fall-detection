"""
SafeWatch — Alembic initial migration
Creates the `users` and `stats` tables.
Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",            sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column("email",         sa.String(255),   nullable=False),
        sa.Column("password_hash", sa.Text(),        nullable=False),
        sa.Column("facility_name", sa.String(255),   nullable=False),
        sa.Column("ward_unit",     sa.String(128),   nullable=True),
        sa.Column("api_token",     sa.String(64),    nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_users_email",     "users", ["email"],     unique=True)
    op.create_index("uq_users_api_token", "users", ["api_token"], unique=True)

    op.create_table(
        "stats",
        sa.Column("id",               sa.Integer(),              primary_key=True, autoincrement=True),
        sa.Column("user_id",          sa.Integer(),              sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_number",      sa.String(32),             nullable=False),
        sa.Column("patient_track_id", sa.Integer(),              nullable=False),
        sa.Column("event_type",       sa.String(32),             nullable=False),
        sa.Column("kinematics",       sa.Text(),                 nullable=True),
        sa.Column("primary_impact",   sa.String(64),             nullable=True),
        sa.Column("head_strike_risk", sa.String(32),             nullable=True),
        sa.Column("image_url",        sa.Text(),                 nullable=True),
        sa.Column("timestamp",        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stats_user_id",    "stats", ["user_id"])
    op.create_index("ix_stats_timestamp",  "stats", ["timestamp"])
    op.create_index("ix_stats_event_type", "stats", ["event_type"])


def downgrade() -> None:
    op.drop_table("stats")
    op.drop_table("users")
