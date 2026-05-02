"""Phase 46E — lightweight self-improvement signals (metrics-driven recommendations)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.token_economy.budget import snapshot_for_user


def system_self_improve(db: Session | None, user_id: str | None) -> dict[str, Any]:
    """
    Emit heuristic recommendations — safe without mutating production behavior by default.

    Callers may attach results to Mission Control or autonomy logs.
    """
    _ = db
    s = get_settings()
    recs: list[str] = []
    if getattr(s, "nexa_block_over_token_budget", False):
        recs.append("Token blocking is on — consider raising daily caps or enabling local_stub routing.")
    tok = snapshot_for_user((user_id or "").strip()) if user_id else {}
    if int(tok.get("tokens_sent_today") or 0) > 50_000:
        recs.append("High daily token volume — review autonomy execution frequency.")
    return {
        "recommendations": recs[:12],
        "token_hint": tok.get("tokens_sent_today") if user_id else None,
        "phase": 46,
    }


__all__ = ["system_self_improve"]
