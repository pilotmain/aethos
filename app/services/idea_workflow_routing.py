"""@strategy / @marketing / @dev subcommands for idea-to-project pipeline."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.models.project import Project
from app.services.project_registry import get_project_by_key
from app.services.project_workflow import (
    format_dev_scope_mvp,
    format_marketing_position,
    format_strategy_validate,
    resolve_project_key_for_workflow,
)

_RE_VALIDATE = re.compile(r"(?i)^\s*validate(?:\s+(.+?))?\s*$")
_RE_POSITION = re.compile(r"(?i)^\s*position(?:\s+(.+?))?\s*$")
_RE_SCOPE = re.compile(r"(?i)^\s*scope(?:\s+(.+?))?\s*$")


def _load_project(
    rest: str | None,
    *,
    db: Session,
    cctx: ConversationContext,
) -> tuple[Project | None, str | None]:
    ap = (cctx.active_project or None) if cctx is not None else None
    r = (rest or "").strip() if rest is not None else ""
    key, err = resolve_project_key_for_workflow(r, db=db, active_project_key=ap)
    if err or not key:
        return (None, err)
    p = get_project_by_key(db, key)
    if not p:
        return (None, f"Unknown project `{key}`.")
    return (p, None)


def try_strategy_workflow(
    m_body: str, *, db: Session, cctx: ConversationContext
) -> str | None:
    t = (m_body or "").strip()
    if not t.lower().startswith("validate"):
        return None
    m = _RE_VALIDATE.match(t)
    if not m:
        return None
    pr, err = _load_project(m.group(1), db=db, cctx=cctx)
    if err or pr is None:
        return f"🧭 **Strategy** (Nexa)\n\n{err or 'Could not load project.'}"
    cctx.active_project = pr.key
    db.add(cctx)
    try:
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return format_strategy_validate(pr)


def try_marketing_workflow(
    m_body: str, *, db: Session, cctx: ConversationContext
) -> str | None:
    t = (m_body or "").strip()
    if not t.lower().startswith("position"):
        return None
    m = _RE_POSITION.match(t)
    if not m:
        return None
    pr, err = _load_project(m.group(1), db=db, cctx=cctx)
    if err or pr is None:
        return f"📣 **Marketing** (Nexa)\n\n{err or 'Could not load project.'}"
    cctx.active_project = pr.key
    db.add(cctx)
    try:
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return format_marketing_position(pr)


def try_dev_scope_workflow(
    m_body: str, *, db: Session, cctx: ConversationContext
) -> str | None:
    t = (m_body or "").strip()
    if not t.lower().startswith("scope"):
        return None
    m = _RE_SCOPE.match(t)
    if not m:
        return None
    pr, err = _load_project(m.group(1), db=db, cctx=cctx)
    if err or pr is None:
        return f"💻 **Dev Agent** (Nexa)\n\n{err or 'Could not load project.'}"
    cctx.active_project = pr.key
    db.add(cctx)
    try:
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return format_dev_scope_mvp(pr)
