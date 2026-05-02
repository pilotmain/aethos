"""Create Nexa projects from idea intake and optional repo-scaffold jobs."""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.schemas.agent_job import AgentJobCreate
from app.services.conversation_context_service import (
    clear_pending_project,
    get_pending_project_dict,
)
from app.services.project_registry import create_idea_project, get_project_by_key


def commit_pending_idea_as_project(
    db: Session, app_user_id: str, cctx: ConversationContext
) -> str:
    payload = get_pending_project_dict(cctx)
    if not payload:
        return (
            "No draft project in this chat. Share an idea first (e.g. “I want to build a booking app for barbers”), "
            "then reply **create project**."
        )
    name = (payload.get("project_name") or "Project")[:200]
    key = (payload.get("project_key") or "").strip().lower()[:100]
    summary = (payload.get("summary") or "")[:10_000]
    if not key:
        return "Draft project is missing a key. Start over with a new idea."
    try:
        p = create_idea_project(
            db,
            key=key,
            display_name=name,
            idea_summary=summary,
        )
    except ValueError as e:
        return f"Could not create project: {e!s}"
    cctx.active_project = p.key
    clear_pending_project(cctx)
    db.add(cctx)
    db.commit()
    db.refresh(cctx)
    return (
        f"Created project: **{p.display_name}**\n\n"
        f"Key: `{p.key}`\n"
        f"Default provider: `{p.provider_key}`\n"
        f"Repo: `—` (set later or `create repo for {p.key}`)\n\n"
        f"Workflow: Strategy → Marketing → Dev → QA → Ops\n\n"
        f"**Next:** ask Nexa to **validate strategy** for `{p.key}`"
    )[:10_000]


def queue_create_repo_approval(
    db: Session,
    app_user_id: str,
    project_key: str,
    *,
    telegram_chat_id: str | None,
) -> str:
    from app.services.agent_job_service import AgentJobService

    k = (project_key or "").strip().lower()
    p = get_project_by_key(db, k)
    if p is None:
        return f"No project `{k}`. Use /projects or create a project from an idea first."
    if (p.repo_path or "").strip():
        return f"Project `{k}` already has a repo: `{p.repo_path}`"
    from app.core.config import get_settings

    wr = Path(get_settings().nexa_workspace_root).expanduser().resolve()
    target = str((wr / k).resolve())
    js = AgentJobService()
    job = js.create_job(
        db,
        app_user_id,
        AgentJobCreate(
            kind="local_action",
            worker_type="local_tool",
            title=f"Create local repo for {k}",
            instruction=f"Scaffold git repo at {target} and attach to project {k}.",
            command_type="create-idea-repo",
            payload_json={"project_key": k, "target_path": target},
            source="telegram",
            approval_required=True,
            telegram_chat_id=telegram_chat_id,
        ),
    )
    st = (job.status or "").strip()
    ap = f"Reply `approve job #{job.id}` to run on the host, then the worker can create the folder and `git init`."
    return (
        f"**Action: create_repo** (requires approval — Nexa)\n\n"
        f"**Project:** `{k}`\n"
        f"**Planned path:** `{target}`\n"
        f"**Job:** #{job.id} — status: {st}\n\n"
        f"{ap}"
    )[:10_000]


def queue_dev_workspace_scaffold(
    db: Session,
    app_user_id: str,
    project_key: str,
    *,
    telegram_chat_id: str | None,
) -> str:
    """Queue workspace scaffold for a new project key — approval task; scaffolds under NEXA_WORKSPACE_ROOT."""
    from app.core.config import get_settings
    from app.services.agent_job_service import AgentJobService

    k = (project_key or "").strip().lower()
    if not k or not re.match(r"^[a-z0-9][a-z0-9_\-]*$", k):
        return (
            "Project key must start with a letter or digit and use only "
            "letters, numbers, hyphens, and underscores (e.g. `booking-app`)."
        )
    p = get_project_by_key(db, k)
    if p is not None:
        return f"Project `{k}` already exists. Use `/project {k}` or pick another name."

    s = get_settings()
    wr = Path(s.nexa_workspace_root).expanduser().resolve()
    target = str((wr / k).resolve())

    js = AgentJobService()
    job = js.create_job(
        db,
        app_user_id,
        AgentJobCreate(
            kind="local_action",
            worker_type="local_tool",
            title=f"Scaffold workspace project {k}",
            instruction=f"Create {target}, git init, README, and register project `{k}` in Nexa.",
            command_type="dev-workspace-scaffold",
            payload_json={"project_key": k, "target_path": target, "workspace_root": str(wr)},
            source="telegram",
            approval_required=True,
            telegram_chat_id=telegram_chat_id,
        ),
    )
    st = (job.status or "").strip()
    dtool = s.nexa_default_dev_tool
    dmode = s.nexa_default_dev_mode
    return (
        f"Create new project? (Nexa)\n\n"
        f"**Name:** `{k}`\n"
        f"**Path:** `{target}`\n"
        f"**Tool:** `{dtool}`\n"
        f"**Mode:** `{dmode}`\n\n"
        f"**Job:** #{job.id} — status: {st}\n\n"
        f"Reply `approve job #{job.id}` to create it on the host (folder, `git init`, README, project row)."
    )[:10_000]
