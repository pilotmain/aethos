"""Merge organization policy rows and answer policy questions (repos, grant modes)."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import OrganizationPolicy

DEFAULT_EFFECTIVE_POLICY: dict[str, Any] = {
    "permission_defaults": {
        "allow_always_workspace": True,
        "allow_always_repo_branch": True,
    },
    "audit_retention_days": 90,
    "allowed_repos": [],
    "require_approval_for_push": True,
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = copy.deepcopy(v)
    return out


def get_effective_policy(db: Session, *, organization_id: str) -> dict[str, Any]:
    """Merged enabled policy_json rows for the org (defaults + stored policies)."""
    oid = (organization_id or "").strip()[:64]
    effective = copy.deepcopy(DEFAULT_EFFECTIVE_POLICY)
    if not oid:
        return effective
    rows = list(
        db.scalars(
            select(OrganizationPolicy)
            .where(
                OrganizationPolicy.organization_id == oid,
                OrganizationPolicy.enabled.is_(True),
            )
            .order_by(OrganizationPolicy.id.asc())
        ).all()
    )
    for r in rows:
        pj = dict(r.policy_json or {})
        effective = _deep_merge(effective, pj)
    return effective


def is_repo_allowed(policy: dict[str, Any], repo_url: str) -> bool:
    ru = (repo_url or "").strip().rstrip("/")
    if not ru:
        return False
    allowed = policy.get("allowed_repos") or []
    if not isinstance(allowed, list) or len(allowed) == 0:
        return True
    for prefix in allowed:
        p = str(prefix).strip().rstrip("/")
        if p and ru.startswith(p):
            return True
    return False


def can_use_always_workspace(policy: dict[str, Any]) -> bool:
    pd = policy.get("permission_defaults") or {}
    if not isinstance(pd, dict):
        return True
    return bool(pd.get("allow_always_workspace", True))


def can_use_always_repo_branch(policy: dict[str, Any]) -> bool:
    pd = policy.get("permission_defaults") or {}
    if not isinstance(pd, dict):
        return True
    return bool(pd.get("allow_always_repo_branch", True))


def validate_cursor_run_against_policy(
    *,
    policy: dict[str, Any],
    repo_url: str,
    branch: str,
) -> tuple[bool, str | None]:
    """
    Governance gate before Cursor Cloud Agent create.

    Returns (True, None) or (False, user_safe_reason).
    """
    if not is_repo_allowed(policy, repo_url):
        return False, "Denied by organization policy: repository not in allowed_repos."
    branches = policy.get("allowed_branches")
    if isinstance(branches, list) and len(branches) > 0:
        b = (branch or "").strip()
        if b not in [str(x).strip() for x in branches]:
            return False, "Denied by organization policy: branch not allowed."
    return True, None
