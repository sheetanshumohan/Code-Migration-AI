from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.core.config import settings
from app.infrastructure.database.postgres.models import Organization, User

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    plan: str,  # 'pro' or 'unlimited'
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Create a Stripe checkout session for subscription."""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured on the server.")

    # Pricing logic driven by settings (configurable without a code deploy)
    prices = {
        "pro": {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Pro Subscription - Max 10 calls / 30 min"},
                "unit_amount": settings.STRIPE_PRO_PRICE_CENTS,
                "recurring": {"interval": "month"}
            }
        },
        "unlimited": {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Unlimited Subscription - No rate limits"},
                "unit_amount": settings.STRIPE_UNLIMITED_PRICE_CENTS,
                "recurring": {"interval": "month"}
            }
        }
    }

    if plan not in prices:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")

    # Get frontend URL from config
    frontend_url = settings.FRONTEND_URL

    try:
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                "price_data": prices[plan]["price_data"],  # type: ignore
                "quantity": 1,
            }],
            mode='subscription',
            success_url=f"{frontend_url}/pricing?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/pricing?canceled=true",
            client_reference_id=str(current_user.organization_id),
            metadata={
                "plan_tier": plan,
                "organization_id": str(current_user.organization_id)
            }
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel

class ConfirmSessionRequest(BaseModel):
    session_id: str

@router.post("/confirm-session")
async def confirm_checkout_session(
    req: ConfirmSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Verify completed Stripe checkout session directly and activate subscription."""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured on the server.")

    try:
        session = stripe.checkout.Session.retrieve(req.session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe session: {e}")

    session_data = session.to_dict() if hasattr(session, "to_dict") else dict(session)
    payment_status = session_data.get("payment_status") or getattr(session, "payment_status", "paid")

    if payment_status not in ("paid", "no_payment_required"):
        raise HTTPException(status_code=400, detail="Payment is not complete on Stripe.")

    meta = session_data.get("metadata") or {}
    plan_tier = meta.get("plan_tier")
    if not plan_tier and hasattr(session, "metadata"):
        try:
            plan_tier = session.metadata["plan_tier"]
        except Exception:
            pass

    if not plan_tier:
        raise HTTPException(status_code=400, detail="Missing plan metadata in Stripe session.")

    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    org = (await db.execute(stmt)).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    org.plan_tier = plan_tier
    customer_id = session_data.get("customer") or getattr(session, "customer", None)
    subscription_id = session_data.get("subscription") or getattr(session, "subscription", None)
    if customer_id:
        org.stripe_customer_id = str(customer_id)
    if subscription_id:
        org.stripe_subscription_id = str(subscription_id)
    await db.commit()

    # Record cryptographic audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=org.id,
        user_id=current_user.id,
        action="update",
        resource_type="subscription",
        resource_id=plan_tier,
        metadata={
            "plan_tier": plan_tier,
            "stripe_session_id": req.session_id,
            "status": "active",
        },
    )

    return {
        "status": "success",
        "plan_tier": plan_tier,
        "message": f"Successfully activated {plan_tier} subscription!",
    }

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """Handle Stripe Webhook for subscription updates."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Webhook misconfigured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session_obj = event['data']['object']
        session_data = session_obj.to_dict() if hasattr(session_obj, "to_dict") else dict(session_obj)
        meta = session_data.get("metadata") or {}

        org_id_str = meta.get("organization_id")
        plan_tier = meta.get("plan_tier")
        customer_id = session_data.get("customer")
        subscription_id = session_data.get("subscription")

        if org_id_str and plan_tier:
            import uuid
            org_id = uuid.UUID(org_id_str)
            stmt = select(Organization).where(Organization.id == org_id)
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()
            if org:
                org.plan_tier = plan_tier
                if customer_id:
                    org.stripe_customer_id = str(customer_id)
                if subscription_id:
                    org.stripe_subscription_id = str(subscription_id)
                await db.commit()

                # Record cryptographic audit log
                from app.core.audit import record_audit_log
                await record_audit_log(
                    db=db,
                    organization_id=org.id,
                    action="update",
                    resource_type="subscription",
                    resource_id=plan_tier,
                    metadata={"plan_tier": plan_tier, "customer_id": str(customer_id) if customer_id else None},
                )

                from app.core.logging import get_logger
                logger = get_logger("codemigration.stripe")
                logger.info(f"Upgraded org {org_id} to {plan_tier} via Stripe webhook")

    return {"status": "success"}
