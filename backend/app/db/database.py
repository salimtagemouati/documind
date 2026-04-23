"""
Database layer — async SQLAlchemy engine + Supabase client.
Uses connection pooling for production-grade throughput.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from supabase import Client, create_client

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# ─── Async SQLAlchemy engine ─────────────────────────────────────────────────
# Pool settings tuned for a small SaaS: max 10 connections, recycle after 30 min
engine_kwargs = {
    "pool_recycle": 1800,
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # Keep objects usable after commit
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session and ensures cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Supabase client ─────────────────────────────────────────────────────────
# Two clients: anon (user-facing) and service (admin bypass RLS)
_supabase_client: Client | None = None
_supabase_admin: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
        )
    return _supabase_client


def get_supabase_admin() -> Client:
    """Service role client — bypasses RLS. Use only in trusted server code."""
    global _supabase_admin
    if _supabase_admin is None:
        _supabase_admin = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
        )
    return _supabase_admin


# ─── Startup/shutdown hooks ──────────────────────────────────────────────────
async def init_db() -> None:
    """Called at app startup — verifies DB connectivity."""
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected", url=settings.DATABASE_URL.split("@")[-1])
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise


async def close_db() -> None:
    """Called at app shutdown — disposes the connection pool cleanly."""
    await engine.dispose()
    logger.info("database_pool_closed")
