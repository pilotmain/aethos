"""Use durable memory + conversation context to refine agent routing for ambiguous work phrases."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.memory_preferences import get_memory_preferences_dict

_AMBIGUOUS_DEV = re.compile(
    r"(?i)\b(work on|continue with|continue the|pick up|keep going with|return to)\b.*\b(app|project|repo|codebase|this)\b|"
    r"\b(fix|debug|patch|solve)\b.*\b(the issue|the bug|it|this)\b|"
    r"\bship\b.+\b(it|this)\b|"
    r"\bfinish\b.+\b(it|this|the app)\b"
)
_AMBIGUOUS_NEXT = re.compile(
    r"(?i)^\s*(what\'?s?\s+next|what\s+next\??|what\s+should\s+i\s+do\s+next)\s*$"
)


def _is_ambiguous_work_message(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _AMBIGUOUS_NEXT.match(t):
        return True
    return bool(_AMBIGUOUS_DEV.search(t))


def resolve_project_key_for_ambiguous_work(
    db: Session,
    text: str,
    context_snapshot: dict | None,
    prefs: dict[str, Any],
) -> str | None:
    from app.services.project_parser import parse_dev_project_phrase
    from app.services.project_registry import get_default_project, get_project_by_key, list_project_keys

    keys = list_project_keys(db)
    pk, _ = parse_dev_project_phrase(text, known_project_keys=keys)
    if pk:
        row = get_project_by_key(db, pk)
        if row:
            return row.key

    ap = (context_snapshot or {}).get("active_project")
    if ap:
        k = str(ap).strip().lower()
        if get_project_by_key(db, k):
            return k

    pp = prefs.get("preferred_project")
    if pp:
        k = str(pp).strip().lower()
        if get_project_by_key(db, k):
            return k

    d = get_default_project(db)
    return d.key if d else None


def apply_memory_aware_route_adjustment(
    route: dict[str, Any],
    text: str,
    context_snapshot: dict | None,
    db: Session | None,
) -> dict[str, Any]:
    """
    Boost Developer routing when the message is ambiguous work language and a project
    can be resolved from context, memory preferences, or default project.

    Priority: explicit instruction in text > active_project > memory preferred_project > default.
    """
    out = dict(route)
    if not db:
        return out

    prefs = get_memory_preferences_dict()
    pk = resolve_project_key_for_ambiguous_work(db, text, context_snapshot, prefs)
    if pk:
        out["resolved_project_key"] = pk

    if not _is_ambiguous_work_message(text):
        return out

    ak = str(out.get("agent_key") or "")
    conf = float(out.get("confidence") or 0)
    reason = str(out.get("reason") or "")

    if conf >= 0.85:
        return out
    if reason == "conversation continuity":
        return out
    if ak not in ("nexa", "general", "ceo", "cto"):
        return out

    if not pk:
        out["reason"] = f"{reason} | ambiguous work; specify a project or set one with /project"
        return out

    out["agent_key"] = "developer"
    out["confidence"] = max(conf, 0.72)
    out["reason"] = f"memory-aware ambiguous work (project: {pk})"
    return out
