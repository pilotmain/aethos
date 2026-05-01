"""In-memory token audit trail for transparency (Phase 38); no raw secrets."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.nexa_next_state import STATE

_AUDIT_CAP = 400


def record_token_audit(
    *,
    user_id: str,
    provider: str,
    model: str | None,
    token_estimate: int,
    redactions: list[dict[str, Any]],
    payload_summary: dict[str, Any],
    cost_estimate: float,
    blocked: bool = False,
    block_reason: str | None = None,
) -> None:
    tail = STATE.setdefault("token_audit_tail", [])
    tail.append(
        {
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "token_estimate": int(token_estimate),
            "redactions": [{"kind": str(r.get("kind", "unknown"))[:80]} for r in (redactions or [])][:40],
            "payload_summary": dict(payload_summary or {}),
            "cost_estimate_usd": round(float(cost_estimate), 8),
            "blocked": blocked,
            "block_reason": block_reason,
        }
    )
    while len(tail) > _AUDIT_CAP:
        tail.pop(0)


def list_recent_token_audits(*, user_id: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    tail = list(STATE.get("token_audit_tail") or [])
    if user_id:
        tail = [x for x in tail if isinstance(x, dict) and x.get("user_id") == user_id]
    return tail[-limit:]
