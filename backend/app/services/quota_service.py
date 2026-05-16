"""
Quota Service — simple per-user document limit, configured via FREE_DOC_LIMIT env var.

This replaces the previous Stripe-based tiering. There is no payment logic here:
every user has the same configurable document cap. To disable the cap, set
FREE_DOC_LIMIT=0.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import User

settings = get_settings()


async def check_document_limit(user_id: str, db: AsyncSession) -> None:
    """
    Raise ValueError if the user has reached the document cap.

    The cap is `settings.FREE_DOC_LIMIT`. A value of 0 disables the limit.
    """
    if settings.FREE_DOC_LIMIT <= 0:
        return  # Limit disabled

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    doc_count = user.documents_processed or 0
    if doc_count >= settings.FREE_DOC_LIMIT:
        raise ValueError(
            f"Document limit reached: {settings.FREE_DOC_LIMIT} documents per account."
        )
