"""
DocuMind FastAPI Application — main entrypoint.

Responsibilities:
- Register all routers
- Configure CORS, rate limiting, error handlers
- Lifespan hooks (database initialization and Redis connectivity)
- Health check endpoint
"""
import asyncio
from contextlib import asynccontextmanager, suppress

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import analytics, auth, billing, documents, query, ws
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.db.database import (
    check_database_health,
    close_db,
    init_db,
    retry_database_connection,
)

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


# ─── Sentry (error tracking in production) ───────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", app=settings.APP_NAME, env=settings.ENVIRONMENT)
    retry_task: asyncio.Task | None = None
    database_connected = await init_db()
    if not database_connected:
        retry_task = asyncio.create_task(retry_database_connection())

    vector_engine = "sqlite-lexical" if settings.DATABASE_URL.startswith("sqlite") else "pgvector"
    logger.info("vector_store_active", engine=vector_engine, table="document_chunks")

    try:
        yield
    finally:
        if retry_task is not None:
            retry_task.cancel()
            with suppress(asyncio.CancelledError):
                await retry_task
        await close_db()
        logger.info("shutdown")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DocuMind API",
    description="AI-powered document intelligence platform. RAG, entity extraction, summarization.",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global error handlers ────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Our team has been notified."},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(query.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(billing.router, prefix=API_PREFIX)
app.include_router(ws.router, prefix=API_PREFIX)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    """Dependency health used by local diagnostics and uptime monitors."""
    if not await check_database_health():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "db": "unreachable"},
        )
    return {"status": "healthy", "db": "connected"}


@app.get("/ready", tags=["Health"])
async def ready():
    """Cloud Run readiness probe; traffic is accepted only with a working DB."""
    return await health()


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "docs": "/api/docs",
        "health": "/health",
    }
