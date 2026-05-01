"""Phase 38 — provider token/cost usage summaries (no raw payloads)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import get_valid_web_user_id
from app.services.token_economy.audit import list_recent_token_audits
from app.services.token_economy.budget import snapshot_for_user

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/usage")
def get_provider_usage(
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    calls_raw = list_recent_token_audits(user_id=app_user_id, limit=80)
    calls: list[dict[str, Any]] = []
    for c in calls_raw:
        if not isinstance(c, dict):
            continue
        calls.append(
            {
                "provider": c.get("provider"),
                "model": c.get("model"),
                "token_estimate": c.get("token_estimate"),
                "cost_estimate_usd": c.get("cost_estimate_usd"),
                "payload_summary": c.get("payload_summary"),
                "redactions": c.get("redactions"),
                "blocked": c.get("blocked"),
                "block_reason": c.get("block_reason"),
            }
        )
    return {"calls": calls, "summary": snapshot_for_user(app_user_id)}
