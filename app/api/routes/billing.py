"""Stripe billing integration for AethOS Cloud (checkout, portal, webhooks, usage)."""

from __future__ import annotations

import logging
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.cloud_saas import CloudSaasContext, get_cloud_saas_context, require_cloud_enabled
from app.core.config import get_settings
from app.core.db import SessionLocal, get_db
from app.services.billing.usage_tracker import UsageTracker
from app.services.cloud_saas.billing_features import get_features_for_tier
from app.services.cloud_saas.stripe_sync import (
    apply_subscription_object,
    downgrade_subscription_deleted,
    upsert_billing_for_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _stripe_obj_to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    fn = getattr(obj, "to_dict", None)
    if callable(fn):
        out = fn()
        return out if isinstance(out, dict) else dict(out)
    try:
        return dict(obj)
    except Exception:
        return {}


class CreateCheckoutRequest(BaseModel):
    price_id: str = Field(..., min_length=3)
    success_url: str = Field(..., min_length=8)
    cancel_url: str = Field(..., min_length=8)


class CreatePortalRequest(BaseModel):
    return_url: str = Field(..., min_length=8)


def _stripe_configured() -> str:
    key = (get_settings().stripe_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_API_KEY is not configured",
        )
    return key


@router.post("/create-checkout")
def create_checkout_session(
    body: CreateCheckoutRequest,
    ctx: CloudSaasContext = Depends(get_cloud_saas_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    require_cloud_enabled()
    api_key = _stripe_configured()
    stripe.api_key = api_key

    billing = ctx.billing
    email = (ctx.user.email or "").strip()
    if not billing.stripe_customer_id:
        customer = stripe.Customer.create(
            email=email or None,
            metadata={"organization_id": ctx.organization.id},
        )
        billing.stripe_customer_id = customer.id
        db.add(billing)
        db.commit()
        db.refresh(billing)

    session = stripe.checkout.Session.create(
        customer=billing.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": body.price_id.strip(), "quantity": 1}],
        mode="subscription",
        success_url=body.success_url,
        cancel_url=body.cancel_url,
        metadata={"organization_id": ctx.organization.id},
    )
    url = getattr(session, "url", None) or ""
    if not url:
        raise HTTPException(status_code=500, detail="Stripe did not return a checkout URL")
    return {"checkout_url": url}


@router.post("/create-portal")
def create_portal_session(
    body: CreatePortalRequest,
    ctx: CloudSaasContext = Depends(get_cloud_saas_context),
) -> dict[str, str]:
    require_cloud_enabled()
    api_key = _stripe_configured()
    stripe.api_key = api_key

    if not ctx.billing.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file")

    portal = stripe.billing_portal.Session.create(
        customer=ctx.billing.stripe_customer_id,
        return_url=body.return_url,
    )
    url = getattr(portal, "url", None) or ""
    if not url:
        raise HTTPException(status_code=500, detail="Stripe did not return a portal URL")
    return {"portal_url": url}


@router.get("/subscription")
def get_subscription(ctx: CloudSaasContext = Depends(get_cloud_saas_context)) -> dict[str, Any]:
    require_cloud_enabled()
    b = ctx.billing
    tier = (b.subscription_tier or "free").strip().lower()
    return {
        "tier": tier,
        "status": (b.subscription_status or "active").strip().lower(),
        "end_date": b.current_period_end.isoformat() if b.current_period_end else None,
        "features": get_features_for_tier(tier),
    }


@router.get("/usage")
def get_usage(ctx: CloudSaasContext = Depends(get_cloud_saas_context)) -> dict[str, Any]:
    require_cloud_enabled()
    tracker = UsageTracker()
    monthly = tracker.get_monthly_usage(ctx.user.id)
    tier = (ctx.billing.subscription_tier or "free").strip().lower()
    feat = get_features_for_tier(tier)
    token_limit = int(feat["tokens_per_month"]) if isinstance(feat["tokens_per_month"], int) else 0
    tokens_used = int(monthly.get("tokens") or 0)
    percentage = 0.0
    if token_limit > 0:
        percentage = min(100.0, round(100.0 * tokens_used / token_limit, 2))
    return {
        "tokens_used": tokens_used,
        "token_limit": token_limit,
        "percentage": percentage,
        "api_calls": int(monthly.get("requests") or 0),
        "tier": tier,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Stripe webhook — raw body + signature (must not depend on JSON middleware stripping bytes)."""
    settings = get_settings()
    if not settings.aethos_cloud_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cloud disabled")

    wh_secret = (settings.stripe_webhook_secret or "").strip()
    api_key = (settings.stripe_api_key or "").strip()
    if not wh_secret or not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook not configured")

    stripe.api_key = api_key
    payload = await request.body()
    sig = request.headers.get("stripe-signature") or ""

    try:
        event = stripe.Webhook.construct_event(payload, sig, wh_secret)
    except ValueError as exc:
        logger.warning("stripe webhook invalid payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid payload") from exc
    except stripe.SignatureVerificationError as exc:
        logger.warning("stripe webhook bad signature: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    if isinstance(event, dict):
        ev = event
    elif hasattr(event, "to_dict") and callable(event.to_dict):
        ev = event.to_dict()
    else:
        try:
            ev = dict(event)
        except Exception:
            ev = {}
    if not isinstance(ev, dict):
        ev = {}
    etype = str(ev.get("type") or "")
    data_obj = (ev.get("data") or {}).get("object") or {}

    db = SessionLocal()
    try:
        if etype == "checkout.session.completed":
            _handle_checkout_completed(db, _stripe_obj_to_dict(data_obj))
        elif etype == "customer.subscription.updated":
            apply_subscription_object(db, _stripe_obj_to_dict(data_obj))
            db.commit()
        elif etype == "customer.subscription.deleted":
            downgrade_subscription_deleted(db, _stripe_obj_to_dict(data_obj))
            db.commit()
        elif etype == "customer.subscription.created":
            apply_subscription_object(db, _stripe_obj_to_dict(data_obj))
            db.commit()
    except Exception:
        logger.exception("stripe webhook handler failed type=%s", etype)
        db.rollback()
        raise
    finally:
        db.close()

    return {"status": "success"}


def _handle_checkout_completed(db: Session, session_obj: dict[str, Any]) -> None:
    meta = session_obj.get("metadata") or {}
    org_id = str(meta.get("organization_id") or "").strip()
    customer_id = str(session_obj.get("customer") or "").strip()
    if org_id and customer_id:
        upsert_billing_for_org(db, organization_id=org_id, stripe_customer_id=customer_id)
        db.flush()
    sub_id = session_obj.get("subscription")
    if sub_id and customer_id:
        stripe.api_key = (get_settings().stripe_api_key or "").strip()
        sub = stripe.Subscription.retrieve(str(sub_id))
        apply_subscription_object(db, _stripe_obj_to_dict(sub))
    db.commit()


__all__ = ["router"]
