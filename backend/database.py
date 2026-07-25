"""
The AI Guards — Database Engine & Session Management
Async SQLAlchemy 2.x with SQLite (dev) / PostgreSQL (prod) support.
Switch DATABASE_URL in .env to move between environments.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models import Base

# ─────────────────────────────────────────────────────────────────────────────
# Engine
# ─────────────────────────────────────────────────────────────────────────────
def normalize_database_url(url: str) -> str:
    """Accept common hosted Postgres URLs and force the asyncpg SQLAlchemy driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Dev default: SQLite async   -> sqlite+aiosqlite:///./the_ai_guards.db
# Prod:        Postgres async -> postgresql+asyncpg://user:pass@host/db
DATABASE_URL: str = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./the_ai_guards.db")
)

# echo=False in production; flip to True for SQL debug logging
engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", False)),
    pool_pre_ping=True,
    # PostgreSQL-specific tuning (ignored by SQLite):
    connect_args={"server_settings": {"jit": "off"}}
    if DATABASE_URL.startswith("postgresql")
    else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ─────────────────────────────────────────────────────────────────────────────
# Table creation (called once at startup)
# ─────────────────────────────────────────────────────────────────────────────
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency — yields a managed async session per request
# ─────────────────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
