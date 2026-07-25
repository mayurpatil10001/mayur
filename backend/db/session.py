"""
backend/db/session.py
=====================
SQLAlchemy async session factory, engine, and health check.
Supports SQLite (development) and PostgreSQL (production) via DATABASE_URL.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ── Engine factory ────────────────────────────────────────────────────────────

def _build_engine() -> AsyncEngine:
    kwargs: dict = {
        "echo": settings.DB_ECHO,
        "future": True,
    }

    if settings.is_sqlite:
        # SQLite-specific: single connection with WAL mode
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL connection pool settings
        kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_pre_ping": True,
                "pool_recycle": 3600,  # Recycle connections every hour
            }
        )

    engine = create_async_engine(settings.DATABASE_URL, **kwargs)

    # Enable WAL mode for SQLite (better concurrent read performance)
    if settings.is_sqlite:
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):  # type: ignore
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA cache_size=-64000")   # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

    return engine


# Module-level engine and session factory (initialized once)
engine: AsyncEngine = _build_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Session dependency (FastAPI) ──────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context manager (for scripts and background tasks) ────────────────────────

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for use outside of FastAPI request scope.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health check ──────────────────────────────────────────────────────────────

async def check_db_health() -> dict:
    """Return database health status. Used by /api/v1/health endpoint."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return {"status": "healthy", "database_url": _sanitize_url(settings.DATABASE_URL)}
    except Exception as e:
        logger.error("Database health check failed", exc_info=True)
        return {"status": "unhealthy", "error": str(e)}


def _sanitize_url(url: str) -> str:
    """Remove credentials from DB URL for safe logging."""
    import re
    return re.sub(r"://[^@]+@", "://<credentials>@", url)


# ── Cleanup ───────────────────────────────────────────────────────────────────

async def close_db() -> None:
    """Dispose the engine connection pool. Called on app shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed.")
