"""
Telegram @ops high-level: route to parse_ops_command, then execute or queue for approval.
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService
from app.services.ops_actions import OPS_ACTIONS, get_action
from app.services.ops_approval import (
    KIND,
    WORKER_TYPE,
    build_ops_approval_message,
)
from app.services.ops_executor import execute_action
from app.services.ops_mention_routing import ops_mention_reply
from app.services.ops_router import parse_ops_command
from app.services.project_registry import get_default_project, list_project_keys


def handle_nexa_ops_mention(
    db: Session,
    app_user_id: str,
    m_body: str,
    *,
    telegram_chat_id: str | None,
    cctx: Any = None,
    list_jobs: Callable[..., Any],
    format_job_row_short: Callable[..., str],
    requester_role: str = "owner",
) -> str:
    """
    Full @ops body. Returns a single string to send in Telegram.
    `requester_role`: owner|trusted|guest|blocked (from env + bootstrap).
    """
    if (requester_role or "").strip() in ("guest", "blocked"):
        return (
            "Ops execution is restricted on this Nexa instance.\n\n"
            "You can still use read-only help and normal chat, or /help."
        )
    job_service = AgentJobService()
    keys = list_project_keys(db)
    dp = get_default_project(db)
    default_env = (dp.default_environment or "staging").lower() if dp else "staging"
    parsed = parse_ops_command(
        m_body, known_project_keys=keys, default_environment=default_env
    )
    name = parsed.get("action")
    raw_pl = dict(parsed.get("payload") or {})
    payload: dict = dict(raw_pl)
    orig_project = (raw_pl.get("project_key") or "").strip().lower() or None

    p_raw = (payload.get("project_key") or "").strip().lower() or None
    active = (getattr(cctx, "active_project", None) or None) if cctx is not None else None
    if not p_raw and active:
        p_raw = str(active).strip().lower() or None
    if not p_raw and dp:
        p_raw = (dp.key or "aethos").lower()
    if p_raw is not None:
        payload["project_key"] = p_raw
    if not orig_project:
        payload.pop("project_key_explicit", None)
    if p_raw and cctx is not None:
        cctx.active_project = p_raw
        db.add(cctx)
        db.commit()

    if not name:
        legacy = ops_mention_reply(
            db,
            app_user_id,
            m_body,
            list_jobs=list_jobs,
            format_job_row_short=format_job_row_short,
        )
        if legacy is not None:
            return legacy
        return (
            "I didn’t understand that ops command.\n\n"
            "Try:\n"
            "`@ops health`\n"
            "`@ops status nexa`\n"
            "`@ops logs nexa api`\n"
            "`@ops deploy nexa staging`\n"
            "`@ops restart nexa api`"
        )

    action = get_action(name)
    if not action or name not in OPS_ACTIONS:
        return "This operation is not supported in Nexa yet (not in the v1 allowlist)."

    if (requester_role or "").strip() == "trusted" and action.requires_approval:
        return "Ops execution is restricted on this Nexa instance."

    active_key = (cctx.active_project or None) if cctx is not None else None

    if not action.requires_approval:
        return execute_action(
            name,
            payload,
            db=db,
            app_user_id=app_user_id,
            active_project_key=active_key,
        )

    p_block = _format_approval_context_block(name, db, payload)
    ac = AgentJobCreate(
        kind=KIND,
        worker_type=WORKER_TYPE,
        title=f"Nexa Ops: {name}"[:255],
        instruction=(m_body or "")[:10_000],
        source="telegram",
        approval_required=True,
        payload_json={
            "ops_action": name,
            "ops_payload": dict(payload or {}),
        },
        telegram_chat_id=telegram_chat_id,
    )
    job = job_service.create_job(db, app_user_id, ac)
    return build_ops_approval_message(action, job.id, project_block=p_block)


def _format_approval_context_block(
    name: str,
    db: Session,
    payload: dict,
) -> str:
    from app.models.project import Project
    from app.services.project_registry import get_default_project, get_project_by_key

    pk = (payload or {}).get("project_key")
    p: Project | None = get_project_by_key(db, str(pk or "")) if pk else get_default_project(db)
    if p is None:
        return f"**Action:** `{name}`\n**Project:** (not resolved)"
    env = (payload or {}).get("environment")
    if env is None and "deploy" in (name or ""):
        if "production" in name or name == "deploy_production":
            env = "production"
        else:
            env = "staging"
    lines = [
        f"**Action:** `{name}`",
        f"**Project:** {p.display_name} (`{p.key}`)",
        f"**Provider:** `{p.provider_key}`",
    ]
    if env is not None:
        lines.append(f"**Environment:** {env}")
    if (payload or {}).get("service"):
        lines.append(f"**Service:** {payload.get('service')}")
    return "\n".join(lines)
