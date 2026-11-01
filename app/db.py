"""Async database engine and session dependency."""

from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings


def build_engine(url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    url = url or settings.async_database_url
    connect_args: dict = {}
    if url.startswith("postgresql+asyncpg://"):
        # Supabase's pooler (Supavisor) may run in transaction mode, which does not support
        # server-side prepared statements across connections. Disabling the cache is safe in both modes.
        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        }
        if not settings.database_is_local:
            connect_args["ssl"] = "require"
        return create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)
    # SQLite (local development and tests): no pooling, so connections never outlive an event loop.
    return create_async_engine(url, poolclass=NullPool)


engine = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
