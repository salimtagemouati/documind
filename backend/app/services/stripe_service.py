"""
Stripe Billing Service — handles checkout sessions, webhooks, and subscription management.

Integration flow:
1. User clicks "Upgrade to Pro" → create_checkout_session() → redirect to Stripe
2. Stripe processes payment → sends webhook → handle_webhook() updates user
3. Frontend checks subscription status via get_subscription_status()

Webhook events handled:
- checkout.session.completed: new subscription created
- customer.subscription.updated: plan change, renewal
- customer.subscription.deleted: cancellation
- invoice.payment_failed: payment issue
"""
import stripe
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import User

settings = get_settings()
logger = get_logger(__name__)

# Configure Stripe SDK
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = "2026-03-25.dahlia"


async def create_checkout_session(
    user_id: str,
    user_email: str,
    db: AsyncSession,
) -> str:
    """
    Create a Stripe Checkout session for Pro subscription.
    Returns the checkout URL to redirect the user to.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY in environment.")

    # Get or create Stripe customer
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    customer_id = user.stripe_customer_id

    if not customer_id:
        # Create a new Stripe customer
        customer = stripe.Customer.create(
            email=user_email,
            metadata={"documind_user_id": user_id},
        )
        customer_id = customer.id
        user.stripe_customer_id = customer_id
        await db.commit()
        logger.info("stripe_customer_created", user_id=user_id, customer_id=customer_id)

    # Create checkout session (payment method types omitted to use dashboard configured dynamic payment methods)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{
            "price": settings.STRIPE_PRICE_ID_PRO,
            "quantity": 1,
        }],
        success_url=f"{settings.FRONTEND_URL}/billing?status=success",
        cancel_url=f"{settings.FRONTEND_URL}/billing?status=canceled",
        metadata={"documind_user_id": user_id},
        subscription_data={
            "metadata": {"documind_user_id": user_id},
        },
    )

    logger.info("checkout_session_created", user_id=user_id, session_id=session.id)
    return session.url


async def handle_webhook(
    payload: bytes,
    sig_header: str,
    db: AsyncSession,
) -> dict:
    """
    Process incoming Stripe webhook events.
    Returns a dict with the event type and any relevant data.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ValueError("Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("stripe_webhook_received", event_type=event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"event_type": event_type, "status": "processed"}


async def get_subscription_status(user_id: str, db: AsyncSession) -> dict:
    """
    Get the current subscription status for a user.
    Returns subscription info for the billing page.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    # Calculate remaining quotas
    docs_used = user.documents_processed or 0
    queries_today = _get_daily_query_count(user)

    is_pro = user.subscription_tier == "pro" and user.subscription_status == "active"

    return {
        "tier": user.subscription_tier or "free",
        "status": user.subscription_status or "inactive",
        "stripe_customer_id": user.stripe_customer_id,
        "limits": {
            "documents": {
                "used": docs_used,
                "limit": None if is_pro else settings.STRIPE_FREE_DOC_LIMIT,
                "remaining": None if is_pro else max(0, settings.STRIPE_FREE_DOC_LIMIT - docs_used),
            },
            "queries_per_day": {
                "used": queries_today,
                "limit": None if is_pro else settings.STRIPE_FREE_QUERY_LIMIT,
                "remaining": None if is_pro else max(0, settings.STRIPE_FREE_QUERY_LIMIT - queries_today),
            },
        },
        "is_pro": is_pro,
    }


async def create_portal_session(user_id: str, db: AsyncSession) -> str:
    """
    Create a Stripe Customer Portal session for managing subscription.
    Returns the portal URL.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError("Stripe is not configured")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.stripe_customer_id:
        raise ValueError("No Stripe customer found. Subscribe first.")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/billing",
    )
    return session.url


# ─── Tier enforcement helpers ─────────────────────────────────────────────────
def _get_daily_query_count(user: User) -> int:
    """Get the user's query count for today, resetting if it's a new day."""
    today = datetime.now(timezone.utc).date()
    if user.daily_queries_date and user.daily_queries_date.date() == today:
        return user.daily_queries_count or 0
    return 0


async def check_document_limit(user_id: str, db: AsyncSession) -> None:
    """
    Check if the user can upload another document.
    Raises ValueError if the free tier limit is reached.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    is_pro = user.subscription_tier == "pro" and user.subscription_status == "active"
    if is_pro:
        return  # No limits for pro users

    doc_count = user.documents_processed or 0
    if doc_count >= settings.STRIPE_FREE_DOC_LIMIT:
        raise ValueError(
            f"Free tier limit reached: {settings.STRIPE_FREE_DOC_LIMIT} documents. "
            f"Upgrade to Pro for unlimited documents."
        )


async def check_query_limit(user_id: str, db: AsyncSession) -> None:
    """
    Check if the user can make another AI query today.
    Raises ValueError if the free tier daily limit is reached.
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    is_pro = user.subscription_tier == "pro" and user.subscription_status == "active"
    if is_pro:
        return  # No limits for pro users

    queries_today = _get_daily_query_count(user)
    if queries_today >= settings.STRIPE_FREE_QUERY_LIMIT:
        raise ValueError(
            f"Free tier daily limit reached: {settings.STRIPE_FREE_QUERY_LIMIT} queries/day. "
            f"Upgrade to Pro for unlimited queries."
        )


async def increment_daily_queries(user_id: str, db: AsyncSession) -> None:
    """Increment the user's daily query counter."""
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        return

    today = datetime.now(timezone.utc)
    if not user.daily_queries_date or user.daily_queries_date.date() != today.date():
        user.daily_queries_count = 1
        user.daily_queries_date = today
    else:
        user.daily_queries_count = (user.daily_queries_count or 0) + 1

    await db.flush()


# ─── Webhook handlers ────────────────────────────────────────────────────────
async def _handle_checkout_completed(session_data: dict, db: AsyncSession) -> None:
    """Handle successful checkout — activate Pro subscription."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")
    user_id = session_data.get("metadata", {}).get("documind_user_id")

    if not customer_id:
        logger.warning("checkout_missing_customer", session=session_data.get("id"))
        return

    # Find user by customer_id or metadata
    if user_id:
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
    else:
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
    user = result.scalar_one_or_none()

    if not user:
        logger.error("checkout_user_not_found", customer_id=customer_id, user_id=user_id)
        return

    user.stripe_customer_id = customer_id
    user.stripe_subscription_id = subscription_id
    user.subscription_status = "active"
    user.subscription_tier = "pro"
    await db.commit()

    logger.info(
        "subscription_activated",
        user_id=str(user.id),
        customer_id=customer_id,
        tier="pro",
    )


async def _handle_subscription_updated(subscription_data: dict, db: AsyncSession) -> None:
    """Handle subscription updates (renewals, plan changes)."""
    customer_id = subscription_data.get("customer")
    status = subscription_data.get("status")  # active, past_due, canceled, etc.

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("subscription_update_user_not_found", customer_id=customer_id)
        return

    user.subscription_status = status
    if status in ("canceled", "unpaid"):
        user.subscription_tier = "free"

    await db.commit()
    logger.info("subscription_updated", user_id=str(user.id), status=status)


async def _handle_subscription_deleted(subscription_data: dict, db: AsyncSession) -> None:
    """Handle subscription cancellation."""
    customer_id = subscription_data.get("customer")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    user.subscription_status = "canceled"
    user.subscription_tier = "free"
    user.stripe_subscription_id = None
    await db.commit()

    logger.info("subscription_canceled", user_id=str(user.id))


async def _handle_payment_failed(invoice_data: dict, db: AsyncSession) -> None:
    """Handle failed payment — mark subscription as past_due."""
    customer_id = invoice_data.get("customer")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    user.subscription_status = "past_due"
    await db.commit()

    logger.info("payment_failed", user_id=str(user.id))
