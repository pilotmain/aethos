from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def healthcheck() -> HealthRead:
    settings = get_settings()
    return HealthRead(status="ok", app=settings.app_name, env=settings.app_env)


@router.get("/health/detailed")
def healthcheck_detailed(
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Phase 73e — operator-facing health snapshot.

    Surfaces the inputs the auto-revert monitor uses, plus the cooldown
    state, so an operator can reason about why a revert did or didn't
    fire without scraping logs.

    Read-only; visible to any authenticated web user (same auth gate as
    the rest of the mission-control surfaces).

    Shape (stable):

    .. code-block:: json

        {
          "ok": true,
          "app": "AethOS",
          "env": "dev",
          "process": {
            "started_at": "2026-05-08 09:30:00",  // UTC, may be null on first boot
            "age_seconds": 142.0
          },
          "heartbeat": {
            "last_at": "2026-05-08 09:34:42",
            "age_seconds": 18.0,
            "stale": false  // age > 2x configured interval
          },
          "errors": {
            "window_seconds": 300,
            "total_actions": 132,
            "errors": 7,
            "error_rate": 0.053
          },
          "auto_revert": {
            "enabled": false,
            "threshold": 0.3,
            "min_sample_size": 10,
            "post_restart_grace_seconds": 60,
            "cooldown_minutes": 30,
            "in_cooldown": false,
            "last_auto_revert_age_seconds": null,
            "last_auto_revert_proposal_id": null
          },
          "last_deploy": {
            "proposal_id": "abcd...",     // null when no remote merge yet
            "title": "...",
            "pr_number": 12,
            "merge_commit_sha": "ab12...",
            "merged_at": "2026-05-08 09:32:11",
            "age_seconds": 161.0,
            "observation_window_seconds": 300,
            "observation_window_remaining_seconds": 139.0,
            "auto_revert_state": "watching",
            "auto_revert_disabled": false
          }
        }

    The endpoint never raises on a missing table or stale data — every
    sub-block degrades to ``null`` independently so a single SQLite
    hiccup can't 500 the operator UI.
    """
    s = get_settings()
    out: dict[str, Any] = {
        "ok": True,
        "app": s.app_name,
        "env": s.app_env,
    }

    # --- process / heartbeat ----------------------------------------
    try:
        from app.services.agent.system_state import get_system_state

        sysstate = get_system_state()
        process_age = sysstate.process_age_seconds()
        heartbeat_age = sysstate.heartbeat_age_seconds()
        last_revert_age = sysstate.last_auto_revert_age_seconds()
        cooldown_minutes = int(
            getattr(s, "nexa_self_improvement_revert_cooldown_minutes", 30) or 30
        )
        in_cooldown = sysstate.in_auto_revert_cooldown(cooldown_minutes)
        last_revert_proposal_id = sysstate.get_value("last_auto_revert_at") or None
        process_started_at = sysstate.get_updated_at("process_started_at")
        heartbeat_at = sysstate.get_updated_at("last_heartbeat_at")
    except Exception:  # noqa: BLE001
        sysstate = None  # type: ignore[assignment]
        process_age = None
        heartbeat_age = None
        last_revert_age = None
        in_cooldown = False
        cooldown_minutes = int(
            getattr(s, "nexa_self_improvement_revert_cooldown_minutes", 30) or 30
        )
        last_revert_proposal_id = None
        process_started_at = None
        heartbeat_at = None

    out["process"] = {
        "started_at": process_started_at,
        "age_seconds": process_age,
    }
    hb_interval = int(getattr(s, "nexa_heartbeat_interval_seconds", 300) or 300)
    out["heartbeat"] = {
        "enabled": bool(getattr(s, "nexa_heartbeat_enabled", False)),
        "interval_seconds": hb_interval,
        "last_at": heartbeat_at,
        "age_seconds": heartbeat_age,
        "stale": bool(
            heartbeat_age is not None and heartbeat_age > (2 * hb_interval)
        ),
    }

    # --- error rate (5-minute window by default) --------------------
    window_s = int(
        getattr(s, "nexa_self_improvement_revert_min_observation_window_seconds", 300) or 300
    )
    try:
        from app.services.self_improvement.revert_monitor import (
            fetch_error_rate_window,
        )

        metrics = fetch_error_rate_window(window_seconds=window_s)
    except Exception:  # noqa: BLE001
        metrics = {"total": 0, "errors": 0, "error_rate": 0.0, "window_seconds": window_s}
    out["errors"] = {
        "window_seconds": int(metrics.get("window_seconds") or window_s),
        "total_actions": int(metrics.get("total") or 0),
        "errors": int(metrics.get("errors") or 0),
        "error_rate": float(metrics.get("error_rate") or 0.0),
    }

    # --- auto-revert wiring -----------------------------------------
    out["auto_revert"] = {
        "enabled": bool(getattr(s, "nexa_self_improvement_auto_revert_enabled", False)),
        "threshold": float(
            getattr(s, "nexa_self_improvement_revert_error_rate_threshold", 0.3) or 0.3
        ),
        "min_sample_size": int(
            getattr(s, "nexa_self_improvement_revert_min_sample_size", 10) or 10
        ),
        "post_restart_grace_seconds": int(
            getattr(s, "nexa_self_improvement_revert_post_restart_grace_seconds", 60) or 60
        ),
        "cooldown_minutes": cooldown_minutes,
        "in_cooldown": bool(in_cooldown),
        "last_auto_revert_age_seconds": last_revert_age,
        "last_auto_revert_proposal_id": last_revert_proposal_id or None,
        "observation_window_seconds": window_s,
    }

    # --- last deploy (most recent merged proposal in observation window) ---
    last_deploy: dict[str, Any] | None = None
    try:
        from app.services.self_improvement.proposal import get_proposal_store

        store = get_proposal_store()
        recent = store.list_recent_merged_within(window_seconds=window_s, limit=1)
        if recent:
            p = recent[0]
            merged_age = store.get_merged_age_seconds(p.id) or 0.0
            remaining = max(0.0, float(window_s) - merged_age)
            last_deploy = {
                "proposal_id": p.id,
                "title": p.title,
                "pr_number": p.pr_number,
                "merge_commit_sha": p.merge_commit_sha,
                "merged_at": p.merged_at,
                "age_seconds": merged_age,
                "observation_window_seconds": window_s,
                "observation_window_remaining_seconds": remaining,
                "auto_revert_state": p.auto_revert_state,
                "auto_revert_disabled": bool(p.auto_revert_disabled),
            }
    except Exception:  # noqa: BLE001
        last_deploy = None
    out["last_deploy"] = last_deploy
    return out
