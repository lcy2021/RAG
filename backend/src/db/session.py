"""Async SQLAlchemy engine. Schema is applied by Alembic (see db.migrate)."""

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from configs.settings import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Commit on success. HTTPException still commits so failed runs can be recorded."""
    if not get_settings().database_enabled:
        raise HTTPException(status_code=503, detail="database is disabled")
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise


async def get_optional_session() -> AsyncIterator[AsyncSession | None]:
    if not get_settings().database_enabled:
        yield None
        return
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise
