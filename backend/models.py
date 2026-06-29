"""
SafeWatch — Database Models (SQLAlchemy 2.x + async)
Two-table multi-tenant schema: users → stats (CASCADE)
"""

import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey,
    UniqueConstraint, Index, event
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 1 — users  (one row per facility / account)
# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    email         : Mapped[str]             = mapped_column(String(255), nullable=False)
    password_hash : Mapped[str]             = mapped_column(Text,        nullable=False)
    facility_name : Mapped[str]             = mapped_column(String(255), nullable=False)
    ward_unit     : Mapped[Optional[str]]   = mapped_column(String(128), nullable=True)
    # 32-byte hex token; edge devices authenticate via X-API-KEY header
    api_token     : Mapped[str]             = mapped_column(String(64),  nullable=False)
    created_at    : Mapped[datetime]        = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # One-to-many: one facility → many incident events
    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("email",     name="uq_users_email"),
        UniqueConstraint("api_token", name="uq_users_api_token"),
    )

    @staticmethod
    def generate_api_token() -> str:
        """Cryptographically secure 32-byte hex token."""
        return secrets.token_hex(32)

    def __repr__(self) -> str:
        return f"<User id={self.id} facility={self.facility_name!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 2 — stats  (incident event log, fully isolated per user_id)
# ─────────────────────────────────────────────────────────────────────────────
class Event(Base):
    __tablename__ = "stats"

    id                 : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    # FK → users.id; CASCADE ensures deletion of user wipes all their events
    user_id            : Mapped[int]           = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    room_number        : Mapped[str]           = mapped_column(String(32),  nullable=False)
    patient_track_id   : Mapped[int]           = mapped_column(Integer,     nullable=False)
    # "FLOOR_FALL" | "BED_EXIT"
    event_type         : Mapped[str]           = mapped_column(String(32),  nullable=False)
    # e.g. "Vertical Collapse (Fainting/Slipping)"
    kinematics         : Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    # e.g. "Left Hip"
    primary_impact     : Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)
    # "🔴 HIGH RISK" | "🟢 Low Risk" | null for bed-exit events
    head_strike_risk   : Mapped[Optional[str]] = mapped_column(String(32),  nullable=True)
    # URL of annotated JPEG stored in object storage (S3-compatible)
    image_url          : Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    timestamp          : Mapped[datetime]      = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="events")

    __table_args__ = (
        # Fast tenant-scoped queries and dashboard aggregations
        Index("ix_stats_user_id",   "user_id"),
        Index("ix_stats_timestamp", "timestamp"),
        Index("ix_stats_event_type","event_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event id={self.id} type={self.event_type!r} "
            f"room={self.room_number!r} ts={self.timestamp}>"
        )
