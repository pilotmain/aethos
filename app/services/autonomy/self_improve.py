"""Phase 46E / 47F — usage-aware efficiency signals for Mission Control."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomy import NexaTaskFeedback
from app.services.token_economy.budget import snapshot_for_user


def system_self_improve(db: Session | None, user_id: str | None) -> dict[str, Any]:
    """
    Emit heuristic recommendations and coarse efficiency metrics — safe defaults when DB absent.
    """
    _ = db
    s = get_settings()
    recs: list[str] = []
    if getattr(s, "nexa_block_over_token_budget", False):
        recs.append("Token blocking is on — consider raising daily caps or enabling local_stub routing.")
    uid = (user_id or "").strip()
    tok = snapshot_for_user(uid) if uid else {}
    sent = int(tok.get("tokens_sent_today") or 0)
    cap_hint = int(getattr(s, "nexa_autonomy_daily_token_ceiling", 400_000) or 400_000)
    token_waste_ratio = round(max(0.0, (sent - cap_hint * 0.5) / max(cap_hint, 1)), 4) if cap_hint else 0.0

    if sent > 50_000:
        recs.append("High daily token volume — review autonomy execution frequency.")
    if token_waste_ratio > 0.35:
        recs.append("Token usage trending above comfortable band — tighten autonomy caps or batch work.")

    avg_task_cost = None
    if db is not None and uid:
        try:
            rows = list(
                db.scalars(
                    select(NexaTaskFeedback.meta_json)
                    .where(NexaTaskFeedback.user_id == uid)
                    .order_by(NexaTaskFeedback.created_at.desc())
                    .limit(80)
                ).all()
            )
            costs: list[float] = []

            for raw in rows:
                try:
                    mj = json.loads(raw or "{}")
                    c = mj.get("cost")
                    if c is not None:
                        costs.append(float(c))
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
            if costs:
                avg_task_cost = round(sum(costs) / len(costs), 6)
        except Exception:
            avg_task_cost = None

    optimization_suggestions: list[str] = list(recs)
    if avg_task_cost is not None and avg_task_cost > 0.05:
        optimization_suggestions.append("Elevated average autonomy task cost — prefer local_stub for exploratory cycles.")
    optimization_suggestions = optimization_suggestions[:16]

    return {
        "recommendations": recs[:12],
        "optimization_suggestions": optimization_suggestions,
        "token_hint": sent if uid else None,
        "token_waste_ratio": token_waste_ratio,
        "avg_task_cost_usd": avg_task_cost,
        "tokens_sent_today": sent if uid else None,
        "phase": 47,
        "system_efficiency": {
            "token_waste_ratio": token_waste_ratio,
            "avg_task_cost_usd": avg_task_cost,
            "optimization_suggestions": optimization_suggestions,
        },
    }


__all__ = ["system_self_improve"]
