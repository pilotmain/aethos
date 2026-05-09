"""Phase 38 — provider token/cost usage summaries (no raw payloads).

Budget tab + Mission Control use GET ``/providers/usage``. Roll-ups **must** match
``GET /web/usage/summary`` (SQLite ``llm_usage_events``), not only in-memory token
economy counters — those can stay zero when usage is recorded only via the LLM gateway.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.llm_usage_recorder import build_llm_usage_summary, get_recent_llm_usage
from app.services.token_economy.budget import snapshot_for_user
from app.services.user_capabilities import get_telegram_role_for_app_user, is_owner_role

router = APIRouter(prefix="/providers", tags=["providers"])


def _provider_usage_is_owner(db: Session, app_user_id: str) -> bool:
    """Same scope as :meth:`~app.api.routes.web.web_usage_summary`."""
    return is_owner_role(get_telegram_role_for_app_user(db, app_user_id))


def _merge_summary(db_summary: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
    """Overlay DB-backed totals onto Phase 38 snapshot (blocks, audit hints)."""
    tokens = int(db_summary.get("total_tokens") or 0)
    cost = round(float(db_summary.get("estimated_cost_usd") or 0.0), 6)
    out = dict(snap)
    out["tokens_sent_today"] = tokens
    out["cost_estimate_usd_today"] = cost
    out["llm_recorded_calls_today"] = int(db_summary.get("total_calls") or 0)
    out["usage_roll_up_source"] = "llm_usage_events"
    return out


def _recent_calls_for_budget(db: Session, app_user_id: str, *, is_owner: bool, limit: int) -> list[dict[str, Any]]:
    rows = get_recent_llm_usage(db, limit, app_user_id, is_owner=is_owner)
    calls: list[dict[str, Any]] = []
    for r in rows:
        calls.append(
            {
                "provider": r.get("provider"),
                "model": r.get("model"),
                "token_estimate": r.get("total_tokens"),
                "cost_estimate_usd": r.get("estimated_cost_usd"),
                "payload_summary": {
                    "source": r.get("source"),
                    "agent": r.get("agent"),
                    "action": r.get("action"),
                    "session_hint": "llm_usage_events",
                },
                "redactions": [],
                "blocked": False if r.get("success") else None,
                "block_reason": r.get("error_type"),
            }
        )
    return calls


def _build_provider_usage_payload(db: Session, app_user_id: str) -> dict[str, Any]:
    is_owner = _provider_usage_is_owner(db, app_user_id)
    llm = build_llm_usage_summary("today", db, app_user_id, is_owner=is_owner)
    snap = snapshot_for_user(app_user_id)
    summary = _merge_summary(llm, snap)
    calls = _recent_calls_for_budget(db, app_user_id, is_owner=is_owner, limit=80)
    return {
        "ok": True,
        "calls": calls,
        "summary": summary,
        "llm_summary": llm,
    }


@router.get("/usage")
def get_provider_usage(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return _build_provider_usage_payload(db, app_user_id)


@router.get("/usage/today")
def get_provider_usage_today(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Same payload as ``/usage`` (today-only aggregation)."""
    return _build_provider_usage_payload(db, app_user_id)
