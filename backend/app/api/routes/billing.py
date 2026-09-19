"""
Billing API Routes — Stripe integration for Pro subscriptions.

POST /api/v1/billing/checkout       — Create Stripe checkout session (redirect URL)
POST /api/v1/billing/portal         — Create Stripe customer portal session
GET  /api/v1/billing/status         — Get current subscription status + limits
POST /api/v1/billing/webhook        — Stripe webhook endpoint (no auth, signature verified)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import ensure_not_demo, get_current_user
from app.db.database import get_db
from app.services.stripe_service import (
    create_checkout_session,
    create_portal_session,
    get_subscription_status,
    handle_webhook,
)

router = APIRouter(prefix="/billing", tags=["Billing"])
settings = get_settings()
logger = get_logger(__name__)


@router.post("/checkout")
async def create_checkout(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for upgrading to Pro.
    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    ensure_not_demo(current_user)
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured. Contact support.",
        )

    try:
        checkout_url = await create_checkout_session(
            user_id=current_user["sub"],
            user_email=current_user.get("email", ""),
            db=db,
        )
        return {"checkout_url": checkout_url}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/portal")
async def manage_subscription(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session for managing billing.
    The portal allows users to update payment methods, cancel, etc.
    """
    ensure_not_demo(current_user)
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured.",
        )

    try:
        portal_url = await create_portal_session(
            user_id=current_user["sub"],
            db=db,
        )
        return {"portal_url": portal_url}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/status")
async def billing_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current subscription status, tier, and usage limits.
    Used by the frontend billing page and upgrade prompts.
    """
    try:
        status_data = await get_subscription_status(
            user_id=current_user["sub"],
            db=db,
        )
        return status_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe webhook endpoint. Called by Stripe to notify us of
    subscription events. Signature is verified using the webhook secret.

    This endpoint is NOT authenticated via JWT — Stripe signs it instead.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature header",
        )

    try:
        result = await handle_webhook(payload, sig_header, db)
        return result
    except ValueError as e:
        logger.error("webhook_error", error_type=type(e).__name__)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
