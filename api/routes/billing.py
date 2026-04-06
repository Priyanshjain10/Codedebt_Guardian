"""
CodeDebt Guardian — Billing Routes (Stripe Integration)
Checkout sessions, customer portal, webhook handler, usage tracking.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from config import settings
from database import get_db
from models.db_models import Subscription, TeamMember, User
from services.audit import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])

PLAN_LIMITS = {
    "free": {"scans_monthly": 5, "projects": 1, "members": 1, "fixes_per_scan": 3},
    "pro": {"scans_monthly": 100, "projects": 10, "members": 10, "fixes_per_scan": 10},
    "enterprise": {
        "scans_monthly": 999999,
        "projects": 999999,
        "members": 999999,
        "fixes_per_scan": 999999,
    },
}


class CheckoutRequest(BaseModel):
    plan: str  # pro | enterprise


@router.post("/checkout")
async def create_checkout_session(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe checkout session for plan upgrade."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="No organization found")

    from models.db_models import Team

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()
    org_id = str(team.org_id)

    price_id = {
        "pro": settings.STRIPE_PRICE_PRO_MONTHLY,
        "enterprise": settings.STRIPE_PRICE_ENTERPRISE_MONTHLY,
    }.get(req.plan)

    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL}/settings?billing=success",
            cancel_url=f"{settings.FRONTEND_URL}/settings?billing=cancel",
            metadata={"org_id": org_id, "user_id": str(user.id)},
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout failed: {str(e)}")


@router.post("/portal")
async def create_portal_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe customer portal session for managing subscription."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    # Find user's org subscription
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="No organization found")

    from models.db_models import Team

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.org_id == team.org_id).limit(1)
        )
    ).scalar_one_or_none()

    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No billing account found")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_SECRET_KEY:
        return {"received": True}

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = session.get("metadata", {}).get("org_id")
        if org_id:
            sub = (
                await db.execute(
                    select(Subscription).where(Subscription.org_id == org_id).limit(1)
                )
            ).scalar_one_or_none()
            if sub:
                sub.stripe_customer_id = session.get("customer")
                sub.stripe_subscription_id = session.get("subscription")
                sub.plan = "pro"
                sub.status = "active"
                sub.scans_limit_monthly = PLAN_LIMITS["pro"]["scans_monthly"]
                await db.flush()
                # Audit log: plan upgraded
                user_id_str = session.get("metadata", {}).get("user_id")
                if user_id_str:
                    from uuid import UUID as _UUID

                    await log_action(
                        db,
                        _UUID(org_id),
                        _UUID(user_id_str),
                        "plan.upgraded",
                        {
                            "plan": "pro",
                        },
                    )

    elif event["type"] == "customer.subscription.deleted":
        sub_data = event["data"]["object"]
        customer_id = sub_data.get("customer")
        sub = (
            await db.execute(
                select(Subscription).where(
                    Subscription.stripe_customer_id == customer_id
                )
            )
        ).scalar_one_or_none()
        if sub:
            sub.plan = "free"
            sub.status = "canceled"
            sub.scans_limit_monthly = PLAN_LIMITS["free"]["scans_monthly"]
            await db.flush()
            # Audit log: plan downgraded
            await log_action(
                db,
                sub.org_id,
                None,
                "plan.downgraded",
                {
                    "plan": "free",
                    "reason": "subscription_deleted",
                },
            )

    elif event["type"] == "customer.subscription.updated":
        sub_data = event["data"]["object"]
        customer_id = sub_data.get("customer")
        new_status = sub_data.get("status")
        sub = (
            await db.execute(
                select(Subscription).where(
                    Subscription.stripe_customer_id == customer_id
                )
            )
        ).scalar_one_or_none()
        if sub:
            # Determine plan from price ID on the first line item
            items = sub_data.get("items", {}).get("data", [])
            price_id = items[0]["price"]["id"] if items else ""
            if price_id == settings.STRIPE_PRICE_ENTERPRISE_MONTHLY:
                new_plan = "enterprise"
            elif price_id == settings.STRIPE_PRICE_PRO_MONTHLY:
                new_plan = "pro"
            else:
                new_plan = "free"
            sub.plan = new_plan
            sub.status = new_status
            sub.scans_limit_monthly = PLAN_LIMITS[new_plan]["scans_monthly"]
            await db.flush()
            await log_action(
                db,
                sub.org_id,
                None,
                "plan.updated",
                {"new_plan": new_plan, "status": new_status},
            )

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        sub = (
            await db.execute(
                select(Subscription).where(
                    Subscription.stripe_customer_id == customer_id
                )
            )
        ).scalar_one_or_none()
        if sub:
            sub.status = "past_due"
            await db.flush()
            await log_action(
                db,
                sub.org_id,
                None,
                "payment.failed",
                {"invoice_id": invoice.get("id")},
            )

    return {"received": True}


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current billing period usage."""
    membership = (
        await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id).limit(1)
        )
    ).scalar_one_or_none()
    if not membership:
        return {"plan": "free", "usage": {}}

    from models.db_models import Team

    team = (
        await db.execute(select(Team).where(Team.id == membership.team_id))
    ).scalar_one()
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.org_id == team.org_id).limit(1)
        )
    ).scalar_one_or_none()

    plan = sub.plan if sub else "free"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    return {
        "plan": plan,
        "scans_used": sub.scans_used if sub else 0,
        "scans_limit": limits["scans_monthly"],
        "projects_limit": limits["projects"],
        "members_limit": limits["members"],
        "fixes_per_scan": limits["fixes_per_scan"],
    }
