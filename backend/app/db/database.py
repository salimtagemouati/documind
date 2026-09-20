"""Async database lifecycle, availability state, and Supabase clients."""
import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from supabase import Client, create_client

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

def validate_database_url(database_url: str) -> None:
    """Reject obvious template hosts before DNS resolution or connection attempts."""
    try:
        parsed = make_url(database_url)
    except Exception as exc:
        raise ValueError(
            "DATABASE_URL is not configured; see docs/LOCAL_DEV.md"
        ) from exc

    if parsed.drivername.startswith("sqlite"):
        return

    host = (parsed.host or "").lower()
    placeholder_parts = ("your-project", "replace_me", "replace-me", "example")
    if not host or host == "host" or host.endswith(".invalid") or any(
        part in host for part in placeholder_parts
    ):
        raise ValueError("DATABASE_URL is not configured; see docs/LOCAL_DEV.md")


def _engine_kwargs(database_url: str) -> dict:
    parsed = make_url(database_url)
    kwargs: dict = {
        "pool_recycle": 1800,
        "pool_pre_ping": True,
        "echo": settings.DEBUG,
    }
    if not parsed.drivername.startswith("sqlite"):
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        if parsed.port == 6543:
            kwargs["connect_args"] = {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            }
    return kwargs

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs(settings.DATABASE_URL),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # Keep objects usable after commit
    autoflush=False,
)


_database_available = False
_database_error_type: str | None = None


def set_database_status(available: bool, *, error_type: str | None = None) -> None:
    global _database_available, _database_error_type
    _database_available = available
    _database_error_type = None if available else error_type


def is_database_available() -> bool:
    return _database_available


def database_retry_delays() -> Generator[int, None, None]:
    """Five bounded exponential delays, followed by 30-second recovery probes."""
    yield from (1, 2, 4, 8, 16)
    while True:
        yield 30


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session and ensures cleanup."""
    if not is_database_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry shortly.",
        )

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except (SQLAlchemyError, OSError) as exc:
            await session.rollback()
            set_database_status(False, error_type=type(exc).__name__)
            logger.warning("database_request_failed", error_type=type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please retry shortly.",
            ) from None
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
async def init_db(*, db_engine=None, database_url: str | None = None) -> bool:
    """Initialize SQLite tables or verify the configured PostgreSQL connection."""
    active_engine = db_engine or engine
    active_url = database_url or settings.DATABASE_URL
    try:
        validate_database_url(active_url)
        parsed = make_url(active_url)
        if parsed.drivername.startswith("sqlite"):
            from app.models.models import Base

            async with active_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        async with active_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        set_database_status(True)
        logger.info(
            "database_connected",
            driver=parsed.drivername,
            host=parsed.host or "local",
        )
        return True
    except ValueError as exc:
        set_database_status(False, error_type="configuration")
        logger.error("database_configuration_invalid", reason=str(exc))
    except Exception as exc:
        set_database_status(False, error_type=type(exc).__name__)
        logger.error("database_connection_failed", error_type=type(exc).__name__)
    return False


async def check_database_health() -> bool:
    """Probe the primary engine and refresh availability state."""
    try:
        validate_database_url(settings.DATABASE_URL)
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        set_database_status(True)
        return True
    except Exception as exc:
        set_database_status(False, error_type=type(exc).__name__)
        return False


async def retry_database_connection(stop_event: asyncio.Event | None = None) -> None:
    """Retry a failed startup without preventing the API process from serving probes."""
    for delay_seconds in database_retry_delays():
        if stop_event is None:
            await asyncio.sleep(delay_seconds)
        else:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
            if stop_event.is_set():
                return

        if await init_db():
            logger.info("database_reconnected")
            return


async def close_db() -> None:
    """Called at app shutdown — disposes the connection pool cleanly."""
    await engine.dispose()
    logger.info("database_pool_closed")
