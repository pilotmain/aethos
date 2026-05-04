"""User-scoped Nexa workspace projects — labeled folders inside approved roots (no scanning)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.project_context import NexaWorkspaceProject
from app.services.host_executor_intent import safe_relative_path
from app.services.workspace_registry import (
    default_work_root_path,
    normalize_root_path,
    path_allowed_under_policy,
)

logger = logging.getLogger(__name__)

_MAX_NAME_LEN = 256


def _join_rel_parts(base: str, child: str) -> str:
    b = (base or "").strip().replace("\\", "/").strip("/")
    c = (child or "").strip().replace("\\", "/").strip("/")
    if not b or b == ".":
        out = c if c else "."
    elif not c or c == ".":
        out = b
    else:
        out = f"{b}/{c}"
    norm = safe_relative_path(out.replace("//", "/"))
    return norm if norm else out.replace("//", "/")


def compute_relative_base_for_project_path(
    db: Session,
    owner_user_id: str,
    project_abs: Path,
) -> str:
    """Path relative to host work root; raises ValueError if not allowed or outside work root."""
    ok, msg = path_allowed_under_policy(db, owner_user_id, project_abs)
    if not ok:
        raise ValueError(msg)
    wr = default_work_root_path().resolve()
    try:
        pa = project_abs.resolve()
        rel = pa.relative_to(wr)
    except (OSError, ValueError) as e:
        raise ValueError(
            "Project folder must be inside the configured host executor work root "
            f"({wr}). Set HOST_EXECUTOR_WORK_ROOT or choose a subdirectory."
        ) from e
    s = safe_relative_path(str(rel).replace("\\", "/"))
    return s if s else "."


def merge_payload_with_project_base(payload: dict[str, Any], relative_base: str) -> dict[str, Any]:
    """
    Prefix relative_path fields with ``relative_base`` and set cwd_relative for git/commands.

    Paths remain relative to the global host work root (single executor boundary).
    """
    if not relative_base or relative_base == ".":
        return dict(payload)
    b = relative_base.strip()
    out = dict(payload)
    ha = (out.get("host_action") or "").strip().lower()
    if ha == "chain":
        actions = out.get("actions")
        if isinstance(actions, list):
            out["actions"] = [
                merge_payload_with_project_base(dict(step), relative_base)
                if isinstance(step, dict)
                else step
                for step in actions
            ]
        return out
    if ha in ("git_status", "run_command", "git_commit", "git_push"):
        out["cwd_relative"] = b
    if ha == "read_multiple_files":
        raw_list = out.get("relative_paths")
        if isinstance(raw_list, list) and raw_list:
            out["relative_paths"] = [_join_rel_parts(b, str(x)) for x in raw_list[:40]]
        rp = str(out.get("relative_path") or out.get("relative_dir") or "").strip()
        if rp:
            out["relative_path"] = _join_rel_parts(b, rp)
        elif not raw_list:
            out["relative_path"] = b
        rd = str(out.get("relative_dir") or "").strip()
        if rd:
            out["relative_dir"] = _join_rel_parts(b, rd)
    elif ha in ("file_read", "file_write", "list_directory", "find_files"):
        if isinstance(out.get("nexa_permission_abs_targets"), list) and out.get(
            "nexa_permission_abs_targets"
        ):
            return out
        rp = str(out.get("relative_path") or ".").strip() or "."
        out["relative_path"] = _join_rel_parts(b, rp) if rp != "." else b
    return out


def add_workspace_project(
    db: Session,
    owner_user_id: str,
    path_raw: str,
    name: str,
    *,
    description: str | None = None,
) -> NexaWorkspaceProject:
    pn = normalize_root_path(path_raw)
    p = Path(pn)
    compute_relative_base_for_project_path(db, owner_user_id, p)
    nm = (name or "").strip()
    if not nm:
        raise ValueError("project name is required")
    nm = nm[:_MAX_NAME_LEN]
    existing = db.scalars(
        select(NexaWorkspaceProject).where(
            NexaWorkspaceProject.owner_user_id == owner_user_id[:64],
            NexaWorkspaceProject.path_normalized == pn,
        )
    ).first()
    if existing:
        raise ValueError(f"a project already exists for path {pn}")
    row = NexaWorkspaceProject(
        owner_user_id=owner_user_id[:64],
        name=nm,
        path_normalized=pn,
        description=(description or "").strip()[:4000] if description else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("nexa_workspace_project added owner=%s path=%s", owner_user_id, pn)
    return row


def list_workspace_projects(db: Session, owner_user_id: str, *, limit: int = 50) -> list[NexaWorkspaceProject]:
    q = (
        select(NexaWorkspaceProject)
        .where(NexaWorkspaceProject.owner_user_id == owner_user_id[:64])
        .order_by(NexaWorkspaceProject.name.asc())
        .limit(min(max(limit, 1), 200))
    )
    return list(db.scalars(q).all())


def get_workspace_project(db: Session, owner_user_id: str, project_id: int) -> NexaWorkspaceProject | None:
    row = db.get(NexaWorkspaceProject, project_id)
    if not row or row.owner_user_id != owner_user_id[:64]:
        return None
    return row


def remove_workspace_project(db: Session, owner_user_id: str, project_id: int) -> NexaWorkspaceProject | None:
    from app.models.conversation_context import ConversationContext

    row = get_workspace_project(db, owner_user_id, project_id)
    if not row:
        return None
    db.execute(
        update(ConversationContext)
        .where(
            ConversationContext.user_id == owner_user_id[:64],
            ConversationContext.active_project_id == project_id,
        )
        .values(active_project_id=None)
    )
    db.delete(row)
    db.commit()
    return row


def set_active_workspace_project(
    db: Session,
    *,
    owner_user_id: str,
    cctx: Any,
    project_id: int | None,
) -> NexaWorkspaceProject | None:
    """Set ``active_project_id`` on conversation context; validates ownership."""
    if project_id is None:
        cctx.active_project_id = None
        db.add(cctx)
        db.commit()
        db.refresh(cctx)
        return None
    row = get_workspace_project(db, owner_user_id, project_id)
    if not row:
        raise ValueError("unknown project id or not yours")
    cctx.active_project_id = row.id
    db.add(cctx)
    db.commit()
    db.refresh(cctx)
    return row


def active_project_relative_base(db: Session, owner_user_id: str, cctx: Any) -> str:
    """Relative path under host work root for the session's active project, or ``'.'``."""
    pid = getattr(cctx, "active_project_id", None)
    if not pid:
        return "."
    row = get_workspace_project(db, owner_user_id, int(pid))
    if not row:
        return "."
    try:
        return compute_relative_base_for_project_path(db, owner_user_id, Path(row.path_normalized))
    except ValueError:
        return "."


_RE_SWITCH = re.compile(
    r"(?is)^(?:switch\s+to|work\s+in|use\s+project)\s+(.+)$"
)
_RE_CLEAR = re.compile(r"(?is)^(?:clear\s+project|no\s+active\s+project)\s*\.?$")


def match_project_by_phrase(
    db: Session,
    owner_user_id: str,
    phrase: str,
) -> NexaWorkspaceProject | None:
    """Case-insensitive match on project name (exact, then substring)."""
    q = (phrase or "").strip()
    if len(q) < 2:
        return None
    rows = list_workspace_projects(db, owner_user_id, limit=100)
    if not rows:
        return None
    ql = q.lower()
    for r in rows:
        if r.name.strip().lower() == ql:
            return r
    for r in rows:
        if ql in r.name.lower():
            return r
    for r in rows:
        tail = Path(r.path_normalized).name.lower()
        if ql == tail or ql in tail:
            return r
    return None


def try_workspace_project_nl_turn(
    db: Session,
    cctx: Any,
    user_text: str,
    *,
    owner_user_id: str | None = None,
) -> str | None:
    """
    Handle natural-language project switching. Returns assistant reply or None.

    Does not elevate permissions — only selects among existing NexaWorkspaceProject rows.
    """
    uid = (owner_user_id or getattr(cctx, "user_id", None) or "").strip()
    if not uid:
        return None
    t = (user_text or "").strip()
    if not t:
        return None
    if _RE_CLEAR.match(t):
        set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=None)
        return "Cleared active Nexa project. Paths default to the host work root unless you specify."

    m = _RE_SWITCH.match(t)
    if not m:
        return None
    phrase = (m.group(1) or "").strip().rstrip(".!")
    hit = match_project_by_phrase(db, uid, phrase)
    if not hit:
        return (
            f"I don’t have a saved project matching “{phrase[:120]}”. "
            "Use `/projects` or **System → Workspace projects** to list projects, "
            "or `/project add <path> <name>` to add one."
        )
    set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=hit.id)
    short_path = hit.path_normalized if len(hit.path_normalized) <= 120 else hit.path_normalized[:117] + "…"
    return (
        f"**Project:** {hit.name}\n"
        f"**Working in:** `{short_path}`\n\n"
        "I’ll use this folder as the default for file requests in this chat until you switch."
    )
