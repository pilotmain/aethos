# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control–style budget caps (Settings + SQLite usage rollups).

Daily/monthly UI targets still live under POST ``/user/settings`` (``ui_preferences``).
This router exposes **server enforcement** limits from :class:`~app.core.config.Settings`
and optional owner-only writes to the repo ``.env``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import ENV_FILE_PATH, get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.llm_usage_recorder import build_llm_usage_summary
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
    is_privileged_owner_for_web_mutations,
)

router = APIRouter(prefix="/budget", tags=["budget"])


class BudgetLimitsBody(BaseModel):
    daily_token_limit: int | None = Field(default=None, ge=1000, le=50_000_000)
    monthly_token_limit: int | None = Field(default=None, ge=1000, le=500_000_000)
    cost_limit_usd_per_day: float | None = Field(default=None, ge=0.0, le=1_000_000.0)


def _usage_owner_scope(db: Session, app_user_id: str) -> bool:
    return is_owner_role(get_telegram_role_for_app_user(db, app_user_id))


def _upsert_dotenv_line(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    key_upper = key.strip()
    out: list[str] = []
    found = False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k == key_upper:
                out.append(f"{key_upper}={value}")
                found = True
                continue
        out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key_upper}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _payload(db: Session, app_user_id: str) -> dict[str, Any]:
    s = get_settings()
    is_owner = _usage_owner_scope(db, app_user_id)
    today = build_llm_usage_summary("today", db, app_user_id, is_owner=is_owner)
    month = build_llm_usage_summary("30d", db, app_user_id, is_owner=is_owner)
    return {
        "ok": True,
        "limits": {
            "daily_token_budget": int(s.nexa_token_budget_per_day),
            "monthly_default_member_budget": int(s.nexa_budget_default_monthly_limit),
            "cost_budget_per_day_usd": float(s.nexa_cost_budget_per_day_usd),
            "block_over_token_budget": bool(s.nexa_block_over_token_budget),
        },
        "usage": {"today": today, "last_30_days": month},
    }


@router.get("/settings")
def get_budget_settings(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return _payload(db, app_user_id)


@router.get("/usage")
def get_budget_usage(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    s = get_settings()
    is_owner = _usage_owner_scope(db, app_user_id)
    today = build_llm_usage_summary("today", db, app_user_id, is_owner=is_owner)
    tokens_used = int(today.get("total_tokens") or 0)
    daily_limit = max(1, int(s.nexa_token_budget_per_day))
    pct = round((tokens_used / daily_limit) * 100, 1)
    cost_today = float(today.get("estimated_cost_usd") or 0.0)
    if pct >= 90:
        color = "red"
        warning = "Critical: approaching daily token budget"
    elif pct >= 75:
        color = "yellow"
        warning = "Warning: most of the daily token budget is in use"
    elif pct >= 50:
        color = "blue"
        warning = "Half of the daily token budget used"
    else:
        color = "green"
        warning = "Within normal range"
    return {
        "ok": True,
        "daily_limit": daily_limit,
        "today_usage_tokens": tokens_used,
        "percent_used": pct,
        "remaining_tokens": max(0, daily_limit - tokens_used),
        "estimated_cost_usd_today": round(cost_today, 6),
        "cost_budget_per_day_usd": float(s.nexa_cost_budget_per_day_usd),
        "color": color,
        "warning": warning,
        "llm_summary_today": today,
    }


@router.post("/settings")
def update_budget_settings(
    body: BudgetLimitsBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    if not is_privileged_owner_for_web_mutations(db, app_user_id):
        raise HTTPException(status_code=403, detail="Owner only")
    if (
        body.daily_token_limit is None
        and body.monthly_token_limit is None
        and body.cost_limit_usd_per_day is None
    ):
        raise HTTPException(status_code=400, detail="No fields to update")
    env_path = ENV_FILE_PATH
    if body.daily_token_limit is not None:
        _upsert_dotenv_line(env_path, "NEXA_TOKEN_BUDGET_PER_DAY", str(int(body.daily_token_limit)))
    if body.monthly_token_limit is not None:
        _upsert_dotenv_line(
            env_path,
            "NEXA_BUDGET_DEFAULT_MONTHLY_LIMIT",
            str(int(body.monthly_token_limit)),
        )
    if body.cost_limit_usd_per_day is not None:
        _upsert_dotenv_line(
            env_path,
            "NEXA_COST_BUDGET_PER_DAY_USD",
            str(float(body.cost_limit_usd_per_day)),
        )
    get_settings.cache_clear()
    return {"ok": True, "message": "Limits written to .env; applied after Settings reload."}
