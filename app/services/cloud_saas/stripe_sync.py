"""Apply Stripe subscription objects to :class:`~app.models.cloud_billing.CloudOrgBilling`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.cloud_billing import CloudOrgBilling


def _price_id_from_subscription(sub: dict[str, Any]) -> str | None:
    items = (sub.get("items") or {}).get("data") or []
    if not items:
        return None
    price = (items[0] or {}).get("price") or {}
    return str(price.get("id") or "").strip() or None


def tier_from_price_id(settings: Settings, price_id: str | None) -> str:
    pid = (price_id or "").strip()
    if not pid:
        return "free"
    pro = (settings.stripe_price_id_pro or "").strip()
    bus = (settings.stripe_price_id_business or "").strip()
    ent = (settings.stripe_price_id_enterprise or "").strip()
    if pro and pid == pro:
        return "pro"
    if bus and pid == bus:
        return "business"
    if ent and pid == ent:
        return "enterprise"
    return "free"


def map_stripe_status(stripe_status: str | None) -> str:
    s = (stripe_status or "").strip().lower()
    if s in ("active", "trialing"):
        return "active"
    if s in ("past_due", "unpaid"):
        return "past_due"
    if s in ("canceled", "cancelled"):
        return "cancelled"
    if s in ("incomplete_expired",):
        return "expired"
    return "cancelled"


def upsert_billing_for_org(
    db: Session,
    *,
    organization_id: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    subscription_tier: str | None = None,
    subscription_status: str | None = None,
    current_period_end: datetime | None = None,
) -> CloudOrgBilling:
    row = db.execute(
        select(CloudOrgBilling).where(CloudOrgBilling.organization_id == organization_id)
    ).scalar_one_or_none()
    if row is None:
        row = CloudOrgBilling(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_tier=subscription_tier or "free",
            subscription_status=subscription_status or "active",
            current_period_end=current_period_end,
        )
        db.add(row)
    else:
        if stripe_customer_id is not None:
            row.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            row.stripe_subscription_id = stripe_subscription_id
        if subscription_tier is not None:
            row.subscription_tier = subscription_tier
        if subscription_status is not None:
            row.subscription_status = subscription_status
        if current_period_end is not None:
            row.current_period_end = current_period_end
    db.flush()
    return row


def apply_subscription_object(db: Session, sub: dict[str, Any]) -> CloudOrgBilling | None:
    """Update billing row from a Stripe Subscription dict (API object or webhook payload)."""
    settings = get_settings()
    cid = str(sub.get("customer") or "").strip()
    if not cid:
        return None
    row = db.execute(select(CloudOrgBilling).where(CloudOrgBilling.stripe_customer_id == cid)).scalar_one_or_none()
    if row is None:
        return None
    price_id = _price_id_from_subscription(sub)
    tier = tier_from_price_id(settings, price_id)
    status = map_stripe_status(str(sub.get("status") or ""))
    cpe_raw = sub.get("current_period_end")
    cpe: datetime | None = None
    if isinstance(cpe_raw, (int, float)):
        cpe = datetime.fromtimestamp(int(cpe_raw), tz=timezone.utc).replace(tzinfo=None)
    sid = str(sub.get("id") or "").strip() or None
    row.stripe_subscription_id = sid
    row.subscription_tier = tier
    row.subscription_status = status
    row.current_period_end = cpe
    db.flush()
    return row


def downgrade_subscription_deleted(db: Session, sub: dict[str, Any]) -> CloudOrgBilling | None:
    cid = str(sub.get("customer") or "").strip()
    if not cid:
        return None
    row = db.execute(select(CloudOrgBilling).where(CloudOrgBilling.stripe_customer_id == cid)).scalar_one_or_none()
    if row is None:
        return None
    row.stripe_subscription_id = None
    row.subscription_tier = "free"
    row.subscription_status = "cancelled"
    row.current_period_end = None
    db.flush()
    return row


__all__ = [
    "tier_from_price_id",
    "map_stripe_status",
    "upsert_billing_for_org",
    "apply_subscription_object",
    "downgrade_subscription_deleted",
]
