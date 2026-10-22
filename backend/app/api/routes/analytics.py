"""
Analytics API Routes
GET /api/v1/analytics/me      — personal usage stats
GET /api/v1/analytics/admin   — system-wide stats (admin only)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import get_current_admin, get_current_user
from app.db.database import get_db
from app.models.models import Document, QueryHistory, User
from app.schemas.schemas import AdminStats, BenchmarkSummary, UserStats
from app.services.cache_service import get_cache_stats

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = get_logger(__name__)


@router.get("/eval", response_model=BenchmarkSummary)
async def get_eval_benchmark():
    """
    Returns the latest stored benchmark artifact. Legacy artifacts are explicitly
    marked unvalidated when they predate the current metric methodology.
    Serves cached benchmark report without recomputing live. Returns 404 if not found.
    """
    import json
    from pathlib import Path

    from app.eval.evaluator import REPORT_FILE

    candidate_paths = [
        REPORT_FILE,
        Path(__file__).parents[3] / "docs" / "benchmark_report.json",
    ]

    for p in candidate_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                return BenchmarkSummary(**data)
            except Exception as exc:
                logger.warning(
                    "benchmark_report_parse_error",
                    path=str(p),
                    error_type=type(exc).__name__,
                )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Benchmark report not found. Please run the evaluation suite first.",
    )


@router.get("/me", response_model=UserStats)
async def get_my_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Personal usage statistics for the authenticated user."""
    from uuid import UUID
    user_id = UUID(current_user["sub"])

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    # Compute average query latency
    latency_result = await db.execute(
        select(func.avg(QueryHistory.latency_ms))
        .where(QueryHistory.user_id == user_id, QueryHistory.from_cache.is_(False))
    )
    avg_latency = latency_result.scalar()

    # Compute personal cache hit rate
    total_queries = user.queries_made or 0
    cached_result = await db.execute(
        select(func.count(QueryHistory.id))
        .where(QueryHistory.user_id == user_id, QueryHistory.from_cache.is_(True))
    )
    cached_count = cached_result.scalar() or 0
    cache_hit_rate = round(cached_count / max(total_queries, 1), 3)

    return UserStats(
        documents_uploaded=user.documents_processed or 0,
        queries_made=user.queries_made or 0,
        ai_tokens_used=user.ai_tokens_used or 0,
        avg_query_latency_ms=round(avg_latency, 1) if avg_latency else None,
        cache_hit_rate=cache_hit_rate,
    )


@router.get("/admin", response_model=AdminStats)
async def get_admin_stats(
    current_user: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """System-wide analytics. Admin only."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_documents = (await db.execute(select(func.count(Document.id)))).scalar()
    total_queries = (await db.execute(select(func.count(QueryHistory.id)))).scalar()
    total_tokens = (await db.execute(select(func.sum(User.ai_tokens_used)))).scalar() or 0

    docs_today = (
        await db.execute(
            select(func.count(Document.id)).where(Document.created_at >= today_start)
        )
    ).scalar()

    queries_today = (
        await db.execute(
            select(func.count(QueryHistory.id)).where(QueryHistory.created_at >= today_start)
        )
    ).scalar()

    cache_stats = await get_cache_stats()
    logger.info("admin_stats_fetched", cache_backend=cache_stats.get("backend"))

    return AdminStats(
        total_users=total_users,
        total_documents=total_documents,
        total_queries=total_queries,
        total_tokens_used=total_tokens,
        documents_today=docs_today,
        queries_today=queries_today,
    )
