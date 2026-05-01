"""Enterprise channel policy enforcement before Gateway Router → core (Phase 13)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.organization_channel_policy import OrganizationChannelPolicy
from app.models.user import User
from app.services.audit_service import audit
from app.services.governance_taxonomy import EVENT_CHANNEL_ACCESS_DENIED

ALL_GOVERNANCE_ROLES: tuple[str, ...] = (
    "owner",
    "admin",
    "operator",
    "approver",
    "viewer",
    "auditor",
)

HIGH_APPROVAL_ROLES: frozenset[str] = frozenset({"owner", "admin", "approver"})


def _external_channels() -> frozenset[str]:
    return frozenset(
        {
            "telegram",
            "slack",
            "email",
            "whatsapp",
            "sms",
            "apple_messages",
        }
    )


def effective_channel_policy(
    db: Session,
    *,
    organization_id: str,
    channel: str,
) -> tuple[bool, list[str], bool]:
    """
    Returns ``(enabled, allowed_roles, approval_required)`` for an org channel.

    Enterprise defaults when no DB row: **web** enabled for all roles; external channels **disabled**.
    """
    row = db.scalar(
        select(OrganizationChannelPolicy).where(
            OrganizationChannelPolicy.organization_id == organization_id,
            OrganizationChannelPolicy.channel == channel,
        )
    )
    if row:
        roles = list(row.allowed_roles or [])
        return bool(row.enabled), roles, bool(row.approval_required)
    ch = (channel or "").strip().lower()
    if ch == "web":
        return True, list(ALL_GOVERNANCE_ROLES), False
    if ch in _external_channels():
        return False, [], False
    # Unknown channel — permissive read (custom integrations)
    return True, list(ALL_GOVERNANCE_ROLES), False


def governance_denial_response(
    *,
    normalized_message: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    """Router-shaped envelope when policy blocks delivery to core."""
    ch = normalized_message.get("channel") or "unknown"
    ch_uid = normalized_message.get("channel_user_id")
    return {
        "message": message,
        "permission_required": None,
        "response_kind": "governance_denied",
        "metadata": {"channel": ch, "channel_user_id": ch_uid},
        "intent": None,
        "agent_key": None,
        "related_job_ids": [],
        "sources": [],
        "web_tool_line": None,
        "usage_summary": None,
        "request_id": None,
        "decision_summary": None,
        "system_events": [],
    }


def check_channel_governance(
    db: Session,
    *,
    user_id: str,
    normalized_message: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Returns a denial envelope if the user/org cannot use this channel; otherwise ``None``.

    When governance is disabled globally, or the user has no ``organization_id``, returns ``None``
    (personal / legacy permissive mode).
    """
    s = get_settings()
    if not s.nexa_governance_enabled:
        return None
    uid = (user_id or "").strip()
    user = db.get(User, uid)
    org_id = (user.organization_id if user else None) or (
        (s.nexa_default_organization_id or "").strip() or None
    )
    if not org_id:
        return None

    channel = str(normalized_message.get("channel") or "").strip().lower()
    enabled, allowed_roles, _approval_required = effective_channel_policy(db, organization_id=org_id, channel=channel)

    if not enabled:
        audit(
            db,
            event_type=EVENT_CHANNEL_ACCESS_DENIED,
            actor="governance",
            user_id=uid,
            message=f"channel={channel} disabled for org={org_id}",
            metadata={
                "organization_id": org_id,
                "channel": channel,
                "reason": "channel_disabled",
            },
        )
        return governance_denial_response(
            normalized_message=normalized_message,
            message="This channel is disabled for your organization. Contact an administrator.",
        )

    role = (user.governance_role if user else None) or "viewer"
    role_l = str(role).strip().lower()
    allowed_set = {str(x).strip().lower() for x in (allowed_roles or [])}
    if allowed_set and role_l not in allowed_set:
        audit(
            db,
            event_type=EVENT_CHANNEL_ACCESS_DENIED,
            actor="governance",
            user_id=uid,
            message=f"channel={channel} role={role_l} not allowed for org={org_id}",
            metadata={
                "organization_id": org_id,
                "channel": channel,
                "role": role_l,
                "reason": "role_not_allowed",
            },
        )
        return governance_denial_response(
            normalized_message=normalized_message,
            message="Your role cannot use this channel. Contact an administrator.",
        )

    return None


def enforce_channel_policy(
    db: Session,
    *,
    user_id: str,
    channel: str,
    organization_id: str | None,
) -> None:
    """
    Legacy signature from spec — raises ``PermissionError`` when blocked.

    Prefer :func:`check_channel_governance` on full normalized messages in the router.
    """
    if not get_settings().nexa_governance_enabled:
        return
    org = (organization_id or "").strip() or None
    if not org:
        return
    enabled, roles, _ = effective_channel_policy(db, organization_id=org, channel=channel)
    if not enabled:
        raise PermissionError("channel disabled")
    user = db.get(User, user_id)
    rl = str((user.governance_role if user else "") or "viewer").lower()
    if roles and rl not in {str(x).lower() for x in roles}:
        raise PermissionError("role not allowed")


def merge_channel_status_governance(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    organization_id: str | None,
) -> list[dict[str, Any]]:
    """Attach enterprise policy fields to channel status rows (Phase 13 status API)."""
    if not organization_id or not get_settings().nexa_governance_enabled:
        return rows
    oid = organization_id.strip()
    if not oid:
        return rows
    for r in rows:
        ch = str(r.get("channel") or "")
        en, roles, appr = effective_channel_policy(db, organization_id=oid, channel=ch)
        # Admin status API (Phase 13) — no secrets; aligns with org channel policy.
        r["governance_enabled"] = en
        r["allowed_roles"] = roles
        r["approval_required"] = appr
    return rows


def user_can_approve_high_risk(db: Session, granter_user_id: str) -> bool:
    """Whether ``granter_user_id`` may approve high/critical permission requests under governance."""
    if not get_settings().nexa_governance_enabled:
        return True
    u = db.get(User, granter_user_id)
    role = str((u.governance_role if u else "") or "").strip().lower()
    return role in HIGH_APPROVAL_ROLES
