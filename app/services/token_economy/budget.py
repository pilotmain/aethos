"""Per-request and daily token/cost budgets (Phase 38)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.mission_control.nexa_next_state import STATE
from app.services.user_settings.service import get_settings_document


def _today_key() -> str:
    return date.today().isoformat()


def _usage_store() -> dict[str, Any]:
    st = STATE.setdefault("token_economy_usage", {})
    day = _today_key()
    if st.get("day") != day:
        st["day"] = day
        st["by_user"] = {}
    return st


def record_usage(user_id: str, *, tokens: int, cost_usd: float, provider: str) -> None:
    """Accumulate daily totals for Mission Control / usage API."""
    st = _usage_store()
    by_user: dict[str, Any] = st.setdefault("by_user", {})
    u = by_user.setdefault(
        user_id,
        {"tokens_today": 0, "cost_usd_today": 0.0, "local_calls": 0, "external_calls": 0},
    )
    u["tokens_today"] = int(u.get("tokens_today", 0)) + int(max(0, tokens))
    u["cost_usd_today"] = float(u.get("cost_usd_today", 0.0)) + float(max(0.0, cost_usd))
    if (provider or "").strip().lower() in ("local_stub", ""):
        u["local_calls"] = int(u.get("local_calls", 0)) + 1
    else:
        u["external_calls"] = int(u.get("external_calls", 0)) + 1


def _blocked_store() -> None:
    st = STATE.setdefault("token_economy_blocks", {})
    day = _today_key()
    if st.get("day") != day:
        st["day"] = day
        st["count"] = 0
    st["count"] = int(st.get("count", 0)) + 1


def _user_token_prefs(db: Session | None, user_id: str) -> dict[str, Any]:
    doc = get_settings_document(db, user_id) if db is not None else {}
    ui = doc.get("ui_preferences") or {}
    return {
        "token_budget_per_request": ui.get("token_budget_per_request"),
        "daily_cost_budget_usd": ui.get("daily_cost_budget_usd"),
        "allow_large_context": ui.get("allow_large_context"),
    }


def check_budget(
    db: Session | None,
    user_id: str,
    *,
    token_estimate: int,
    provider: str,
) -> str | None:
    """
    Return error code if call must be blocked, else None.

    local_stub: counts toward token totals but cost_usd = 0.
    """
    s = get_settings()
    prefs = _user_token_prefs(db, user_id)
    per_req = prefs.get("token_budget_per_request")
    if per_req is None:
        per_req = int(s.nexa_token_budget_per_request or 8000)
    else:
        per_req = int(per_req)

    allow_large = prefs.get("allow_large_context")
    if allow_large is not True and token_estimate > per_req:
        return "large_context_disabled"

    max_tok = per_req
    if token_estimate > max_tok and s.nexa_block_over_token_budget:
        _blocked_store()
        return "token_budget_per_request"

    st = _usage_store()
    by_user = st.get("by_user") or {}
    u = by_user.get(user_id) or {}
    tokens_today = int(u.get("tokens_today", 0))
    daily_cap = int(s.nexa_token_budget_per_day or 100_000)
    if tokens_today + token_estimate > daily_cap:
        if s.nexa_block_over_token_budget:
            _blocked_store()
            return "token_budget_per_day"

    cost_pref = prefs.get("daily_cost_budget_usd")
    daily_cost_cap = float(cost_pref) if cost_pref is not None else float(s.nexa_cost_budget_per_day_usd or 5.0)
    cost_today = float(u.get("cost_usd_today", 0.0))
    # Rough next-call upper bound using env pricing (actual charged in gateway)
    rough_next = 0.0 if provider == "local_stub" else max(0.0, (token_estimate / 1000.0) * 0.002)
    if cost_today + rough_next > daily_cost_cap and provider != "local_stub":
        if s.nexa_block_over_token_budget:
            _blocked_store()
            return "cost_budget_per_day"

    return None


def snapshot_for_user(user_id: str) -> dict[str, Any]:
    """Roll-up for Mission Control panel."""
    st = STATE.get("token_economy_usage") or {}
    by_user = (st.get("by_user") or {}).get(user_id) or {}
    blocks = STATE.get("token_economy_blocks") or {}
    audits = list(STATE.get("token_audit_tail") or [])
    recent = [a for a in audits if isinstance(a, dict) and a.get("user_id") == user_id][-20:]
    last = recent[-1] if recent else None
    return {
        "tokens_sent_today": int(by_user.get("tokens_today", 0)),
        "cost_estimate_usd_today": round(float(by_user.get("cost_usd_today", 0.0)), 6),
        "local_calls_today": int(by_user.get("local_calls", 0)),
        "external_calls_today": int(by_user.get("external_calls", 0)),
        "budget_blocks_today": int(blocks.get("count", 0)),
        "last_payload_summary": (last or {}).get("payload_summary"),
        "last_redactions_count": len((last or {}).get("redactions") or []) if last else 0,
    }
