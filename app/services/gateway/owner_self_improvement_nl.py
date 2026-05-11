"""Owner-only chat hints for self-improvement / PR workflow (no auto-write, no direct push)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

_SI_NL = re.compile(
    r"(?is)\b("
    r"suggest\s+(?:code\s+)?(?:fix|fixes|improvements)|"
    r"code\s+review|self[- ]?improve(?:ment)?|"
    r"analyze\s+(?:the\s+)?(?:repo|codebase)|"
    r"propose\s+(?:a\s+)?(?:patch|pr|pull\s+request)"
    r")\b"
)


def try_owner_self_improvement_nl_turn(
    gctx: GatewayContext,
    text: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Deterministic guidance for owners — points to API-based propose → sandbox → approve → apply (no push).
    """
    raw = (text or "").strip()
    if not raw or not _SI_NL.search(raw):
        return None
    uid = (gctx.user_id or "").strip()
    if not uid or not is_privileged_owner_for_web_mutations(db, uid):
        return None
    si_on = bool(getattr(get_settings(), "nexa_self_improvement_enabled", False))
    body = (
        "**Self-improvement (owner)**\n\n"
        "I won’t rewrite production code from chat. Use the **Self-improvement** API flow instead:\n\n"
        "1. **POST** `/api/v1/self_improvement/propose` — generates a **pending** proposal (diff preview).\n"
        "2. **POST** `/api/v1/self_improvement/{id}/sandbox` — validate in isolation.\n"
        "3. **POST** `/api/v1/self_improvement/{id}/approve` — human approval gate.\n"
        "4. **POST** `/api/v1/self_improvement/{id}/apply` — applies as a **local commit** "
        "(**does not push**; open a **PR** from your Git host when ready).\n\n"
        "_Never approve blindly — review the diff and sandbox result first._"
    )
    if not si_on:
        body += (
            "\n\n_Note: HTTP routes stay dark until you set `NEXA_SELF_IMPROVEMENT_ENABLED=true` "
            "and restart the API._"
        )
    return {
        "mode": "chat",
        "text": body,
        "intent": "owner_self_improvement_hint",
        "self_improvement_hint": True,
    }


__all__ = ["try_owner_self_improvement_nl_turn"]
