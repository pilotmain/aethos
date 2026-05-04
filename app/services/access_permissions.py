"""Permission requests, grants, and host-executor access checks (no raw shell)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_permission import AccessPermission
from app.services import workspace_registry as workspace_registry_mod
from app.services.audit_service import audit
from app.services.channel_gateway.governance import user_can_approve_high_risk
from app.services.governance_taxonomy import EVENT_APPROVAL_ROLE_DENIED
from app.services.host_executor_intent import safe_relative_path
from app.services.sensitivity import NEXA_SENSITIVITY_KEY, detect_sensitivity
from app.services.trust_audit_constants import (
    ACCESS_HOST_EXECUTOR_BLOCKED,
    ACCESS_PERMISSION_DENIED,
    ACCESS_PERMISSION_GRANTED,
    ACCESS_PERMISSION_REQUESTED,
    ACCESS_PERMISSION_REVOKED,
    ACCESS_PERMISSION_USED,
)
from app.services.trust_audit_correlation import correlation_from_payload
from app.services.workspace_registry import list_roots, path_allowed_under_policy

logger = logging.getLogger(__name__)

# Product scopes (stable identifiers)
SCOPE_FILE_READ = "file_read"
SCOPE_FILE_WRITE = "file_write"
SCOPE_PROJECT_SCAN = "project_scan"
SCOPE_COMMAND_RUN = "command_run"
SCOPE_GIT_OPERATIONS = "git_operations"
SCOPE_APP_OPEN = "app_open"
SCOPE_NETWORK_REQUEST = "network_request"
SCOPE_CREDENTIAL_USE = "credential_use"
SCOPE_CLOUD_CLI = "cloud_cli"
SCOPE_BROWSER_ACTION = "browser_action"
# Explicit approval for sending data off-device (distinct from read-only network_request UX).
SCOPE_NETWORK_EXTERNAL_SEND = "network_external_send"

SCOPES = frozenset(
    {
        SCOPE_FILE_READ,
        SCOPE_FILE_WRITE,
        SCOPE_PROJECT_SCAN,
        SCOPE_COMMAND_RUN,
        SCOPE_GIT_OPERATIONS,
        SCOPE_APP_OPEN,
        SCOPE_NETWORK_REQUEST,
        SCOPE_NETWORK_EXTERNAL_SEND,
        SCOPE_CREDENTIAL_USE,
        SCOPE_CLOUD_CLI,
        SCOPE_BROWSER_ACTION,
    }
)

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

RISK_ORDER = {
    RISK_LOW: 1,
    RISK_MEDIUM: 2,
    RISK_HIGH: 3,
    RISK_CRITICAL: 4,
}

STATUS_PENDING = "pending"
STATUS_GRANTED = "granted"
STATUS_REVOKED = "revoked"
STATUS_DENIED = "denied"
STATUS_CONSUMED = "consumed"

GRANT_MODE_PERSISTENT = "persistent"
GRANT_MODE_ONCE = "once"
GRANT_MODE_SESSION = "session"
# Long-lived grants (metadata records user intent; matching uses same rules as persistent).
GRANT_MODE_ALWAYS_WORKSPACE = "always_workspace"
GRANT_MODE_ALWAYS_REPO_BRANCH = "always_repo_branch"

_SENSITIVE_PATH_HINTS = (
    ".env",
    ".ssh",
    "credentials",
    "secrets",
    ".pem",
    "id_rsa",
    "known_hosts",
)


def _risk_at_least(granted: str, required: str) -> bool:
    return RISK_ORDER.get((granted or "").lower(), 0) >= RISK_ORDER.get((required or "").lower(), 99)


def reason_for_scope(scope: str, *, host_action_hint: str | None = None) -> str:
    """Short trust-layer explanation for UX (why this permission exists)."""
    s = (scope or "").strip()
    return {
        SCOPE_FILE_READ: "To read files needed to answer your question.",
        SCOPE_FILE_WRITE: "To save or update files as part of your requested change.",
        SCOPE_PROJECT_SCAN: "To list or scan project files you asked about.",
        SCOPE_COMMAND_RUN: "To run an allowlisted command you approved.",
        SCOPE_GIT_OPERATIONS: "To run fixed git commands in your repo.",
        SCOPE_APP_OPEN: "To launch or focus an approved app or CLI.",
        SCOPE_NETWORK_REQUEST: "To fetch data over the network as you requested.",
        SCOPE_NETWORK_EXTERNAL_SEND: "To send data from this machine to an external endpoint you approved.",
        SCOPE_CREDENTIAL_USE: "To use scoped credentials for a named service.",
        SCOPE_CLOUD_CLI: "To run cloud CLI commands with fixed arguments.",
        SCOPE_BROWSER_ACTION: "For controlled browser actions you approved.",
    }.get(s, "To complete this local action safely and visibly.")


def explain_permission_risk(scope: str, target: str) -> str:
    """Human-readable risk summary for UX (no execution)."""
    s = (scope or "").strip()
    t = (target or "").strip()[:240]
    base = {
        SCOPE_FILE_READ: "Reads files under the approved folder only.",
        SCOPE_FILE_WRITE: "May create or overwrite files under the approved folder.",
        SCOPE_PROJECT_SCAN: "Lists directories and searches filenames under the approved folder.",
        SCOPE_COMMAND_RUN: "Runs a fixed allowlisted command (no arbitrary shell).",
        SCOPE_GIT_OPERATIONS: "Runs fixed git commands in the approved working tree.",
        SCOPE_APP_OPEN: "May launch or focus allowlisted apps/CLIs with fixed arguments.",
        SCOPE_NETWORK_REQUEST: "May perform scoped network requests from approved tools.",
        SCOPE_NETWORK_EXTERNAL_SEND: "May send HTTP data off this machine to approved destinations only.",
        SCOPE_CREDENTIAL_USE: "Uses stored credentials for a named service (never printed).",
        SCOPE_CLOUD_CLI: "Runs cloud CLI tools with fixed argv patterns.",
        SCOPE_BROWSER_ACTION: "Controlled browser automation (allowlisted).",
    }.get(s, "Scoped local access via Nexa tools.")
    if any(h in t.lower() for h in _SENSITIVE_PATH_HINTS):
        return base + " Target looks sensitive — extra review recommended."
    return base


def request_permission(
    db: Session,
    owner_user_id: str,
    *,
    scope: str,
    target: str,
    risk_level: str,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AccessPermission:
    """Create a pending permission row.

    For **agent assignments**, callers should include ``assignment_id`` and
    ``assigned_to_handle`` in ``metadata`` when applicable so resume and dashboards can
    correlate ``AccessPermission`` ↔ ``AgentAssignment`` rows.
    """
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    md = dict(metadata or {})
    if get_settings().nexa_governance_enabled and "organization_id" not in md:
        d = (get_settings().nexa_default_organization_id or "").strip()[:64]
        if d:
            md["organization_id"] = d
    row = AccessPermission(
        owner_user_id=owner_user_id[:64],
        scope=scope[:64],
        target=(target or "")[:8000],
        risk_level=(risk_level or RISK_LOW)[:16],
        status=STATUS_PENDING,
        expires_at=None,
        granted_by_user_id=None,
        reason=(reason or "")[:4000] if reason else None,
        metadata_json=md,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    oid = (md.get("organization_id") or "").strip()[:64] or None
    audit(
        db,
        event_type=ACCESS_PERMISSION_REQUESTED,
        actor="user",
        user_id=owner_user_id,
        message=f"scope={scope} target={target[:200]}",
        metadata={"permission_id": row.id, "risk": risk_level, **({"organization_id": oid} if oid else {})},
        organization_id=oid,
    )
    return row


def grant_permission(
    db: Session,
    owner_user_id: str,
    permission_id: int,
    *,
    granted_by_user_id: str,
    metadata: dict[str, Any] | None = None,
    grant_mode: str | None = None,
    grant_session_hours: float | None = None,
) -> AccessPermission | None:
    row = db.get(AccessPermission, permission_id)
    if not row or row.owner_user_id != owner_user_id:
        return None
    if row.status != STATUS_PENDING:
        return None
    if get_settings().nexa_governance_enabled and row.risk_level in (RISK_HIGH, RISK_CRITICAL):
        if not user_can_approve_high_risk(db, granted_by_user_id):
            audit(
                db,
                event_type=EVENT_APPROVAL_ROLE_DENIED,
                actor="governance",
                user_id=owner_user_id,
                message=f"permission_id={permission_id} risk={row.risk_level}",
                metadata={
                    "permission_id": permission_id,
                    "granter_user_id": granted_by_user_id,
                    "risk_level": row.risk_level,
                },
            )
            return None
    pl = dict(row.metadata_json or {})
    if metadata:
        pl.update(metadata)

    mode = (grant_mode or pl.get("grant_mode") or GRANT_MODE_PERSISTENT).strip().lower()
    if mode not in (
        GRANT_MODE_PERSISTENT,
        GRANT_MODE_ONCE,
        GRANT_MODE_SESSION,
        GRANT_MODE_ALWAYS_WORKSPACE,
        GRANT_MODE_ALWAYS_REPO_BRANCH,
    ):
        mode = GRANT_MODE_PERSISTENT
    pl["grant_mode"] = mode

    if get_settings().nexa_governance_enabled:
        from app.services.governance.policies import (
            can_use_always_repo_branch,
            can_use_always_workspace,
            get_effective_policy,
        )

        oid_g = (pl.get("organization_id") or get_settings().nexa_default_organization_id or "").strip()[:64]
        if oid_g and mode in (GRANT_MODE_ALWAYS_WORKSPACE, GRANT_MODE_ALWAYS_REPO_BRANCH):
            pol = get_effective_policy(db, organization_id=oid_g)
            if mode == GRANT_MODE_ALWAYS_WORKSPACE and not can_use_always_workspace(pol):
                audit(
                    db,
                    event_type="governance.permission_grant.denied",
                    actor="governance",
                    user_id=owner_user_id,
                    message="always_workspace not allowed by organization policy",
                    metadata={
                        "permission_id": permission_id,
                        "organization_id": oid_g,
                        "grant_mode": mode,
                    },
                    organization_id=oid_g,
                )
                return None
            if mode == GRANT_MODE_ALWAYS_REPO_BRANCH and not can_use_always_repo_branch(pol):
                audit(
                    db,
                    event_type="governance.permission_grant.denied",
                    actor="governance",
                    user_id=owner_user_id,
                    message="always_repo_branch not allowed by organization policy",
                    metadata={
                        "permission_id": permission_id,
                        "organization_id": oid_g,
                        "grant_mode": mode,
                    },
                    organization_id=oid_g,
                )
                return None

    row.status = STATUS_GRANTED
    row.granted_by_user_id = granted_by_user_id[:64]

    if mode == GRANT_MODE_SESSION:
        hrs = (
            grant_session_hours
            if grant_session_hours is not None
            else float(pl.get("grant_session_hours") or 8)
        )
        try:
            row.expires_at = datetime.now(timezone.utc) + timedelta(hours=float(hrs))
        except (TypeError, ValueError):
            row.expires_at = datetime.now(timezone.utc) + timedelta(hours=8.0)
    elif mode == GRANT_MODE_ONCE:
        row.expires_at = None
    elif mode in (GRANT_MODE_ALWAYS_WORKSPACE, GRANT_MODE_ALWAYS_REPO_BRANCH):
        row.expires_at = None
    elif pl.get("grant_ttl_hours"):
        try:
            hrs = float(pl["grant_ttl_hours"])
            row.expires_at = datetime.now(timezone.utc) + timedelta(hours=hrs)
        except (TypeError, ValueError):
            pass

    row.metadata_json = pl
    db.add(row)
    db.commit()
    db.refresh(row)
    oid_audit = (pl.get("organization_id") or "").strip()[:64] or None
    audit(
        db,
        event_type=ACCESS_PERMISSION_GRANTED,
        actor="user",
        user_id=owner_user_id,
        message=f"permission_id={row.id} scope={row.scope}",
        metadata={"permission_id": row.id, **({"organization_id": oid_audit} if oid_audit else {})},
        organization_id=oid_audit,
    )
    return row


def deny_permission(db: Session, owner_user_id: str, permission_id: int) -> AccessPermission | None:
    row = db.get(AccessPermission, permission_id)
    if not row or row.owner_user_id != owner_user_id:
        return None
    if row.status != STATUS_PENDING:
        return None
    row.status = STATUS_DENIED
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type=ACCESS_PERMISSION_DENIED,
        actor="user",
        user_id=owner_user_id,
        message=f"permission_id={permission_id}",
        metadata={"permission_id": permission_id},
    )
    return row


def revoke_permission(db: Session, owner_user_id: str, permission_id: int) -> AccessPermission | None:
    row = db.get(AccessPermission, permission_id)
    if not row or row.owner_user_id != owner_user_id:
        return None
    if row.status not in {STATUS_GRANTED, STATUS_PENDING}:
        return None
    row.status = STATUS_REVOKED
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type=ACCESS_PERMISSION_REVOKED,
        actor="user",
        user_id=owner_user_id,
        message=f"permission_id={permission_id}",
        metadata={"permission_id": permission_id},
    )
    return row


def list_permissions(db: Session, owner_user_id: str, *, limit: int = 50) -> list[AccessPermission]:
    q = (
        select(AccessPermission)
        .where(AccessPermission.owner_user_id == owner_user_id)
        .order_by(AccessPermission.id.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list(db.scalars(q).all())


def host_action_scope_and_risk(
    host_action: str,
    *,
    relative_path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Map host_executor host_action to permission scope + minimum risk tier."""
    a = (host_action or "").strip().lower()
    pl = payload or {}
    if a == "git_status":
        return SCOPE_GIT_OPERATIONS, RISK_LOW
    if a == "git_commit":
        return SCOPE_GIT_OPERATIONS, RISK_HIGH
    if a == "git_push":
        return SCOPE_GIT_OPERATIONS, RISK_HIGH
    if a == "run_command":
        return SCOPE_COMMAND_RUN, RISK_MEDIUM
    if a == "file_read":
        rp = (relative_path or "").lower()
        if any(h in rp for h in _SENSITIVE_PATH_HINTS):
            return SCOPE_FILE_READ, RISK_HIGH
        return SCOPE_FILE_READ, RISK_LOW
    if a == "file_write":
        return SCOPE_FILE_WRITE, RISK_MEDIUM
    if a == "list_directory":
        return SCOPE_PROJECT_SCAN, RISK_LOW
    if a == "find_files":
        return SCOPE_PROJECT_SCAN, RISK_LOW
    if a == "read_multiple_files":
        rs = pl.get("relative_paths")
        extra = ""
        if isinstance(rs, list):
            extra = " ".join(str(x) for x in rs[:24])
        blob = (
            (relative_path or "")
            + str(pl.get("relative_dir") or "")
            + " "
            + extra
        )
        low = blob.lower()
        if any(h in low for h in _SENSITIVE_PATH_HINTS):
            return SCOPE_FILE_READ, RISK_HIGH
        return SCOPE_FILE_READ, RISK_MEDIUM
    return SCOPE_COMMAND_RUN, RISK_MEDIUM


def _expired(row: AccessPermission) -> bool:
    if row.expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < now


def _matching_grant(
    rows: list[AccessPermission],
    *,
    scope: str,
    path: Path,
    required_risk: str,
) -> AccessPermission | None:
    """Pick a grant that covers path under target with sufficient risk ceiling."""
    try:
        p = path.resolve()
    except OSError:
        return None
    best: AccessPermission | None = None
    best_rank = -1
    for row in rows:
        if row.scope != scope:
            continue
        if row.status != STATUS_GRANTED:
            continue
        if _expired(row):
            continue
        if not _risk_at_least(row.risk_level, required_risk):
            continue
        try:
            root = Path(row.target).resolve()
            p.relative_to(root)
        except ValueError:
            continue
        rk = RISK_ORDER.get(row.risk_level, 0)
        if rk > best_rank:
            best_rank = rk
            best = row
    return best


def _normalize_grant_hostname_target(raw: str) -> str:
    r = (raw or "").strip().lower().rstrip("/")
    if "://" in r:
        h = urlparse(r).hostname
        return ((h or r).strip(".")).lower()
    return r.strip(".").lower()


def hostname_covers_external_send_target(grant_target: str, request_host: str) -> bool:
    """Grant target may be example.com, *.example.com, or https://api.example.com/path (host only)."""
    gt = _normalize_grant_hostname_target(grant_target)
    hn = (request_host or "").strip().lower().strip(".")
    if not hn:
        return False
    if gt in ("*", "*.*", "any"):
        return True
    if gt.startswith("*."):
        base = gt[2:]
        return hn == base or hn.endswith("." + base)
    return hn == gt or hn.endswith("." + gt)


def check_network_external_send_permission(
    db: Session,
    owner_user_id: str,
    *,
    hostname: str,
    required_risk: str = RISK_MEDIUM,
) -> tuple[bool, str]:
    rows = _granted_rows_for_scope(db, owner_user_id, SCOPE_NETWORK_EXTERNAL_SEND)
    if not rows:
        return False, "no granted permission for network_external_send"
    for row in rows:
        if _expired(row):
            continue
        if not _risk_at_least(row.risk_level, required_risk):
            continue
        if hostname_covers_external_send_target(row.target, hostname):
            return True, ""
    return False, f"no network_external_send grant covers host {hostname!r}"


def _granted_rows_for_scope(db: Session, owner_user_id: str, scope: str) -> list[AccessPermission]:
    q = select(AccessPermission).where(
        AccessPermission.owner_user_id == owner_user_id,
        AccessPermission.scope == scope,
        AccessPermission.status == STATUS_GRANTED,
    )
    return list(db.scalars(q).all())


def resolve_grants_for_paths(
    db: Session,
    owner_user_id: str,
    scope: str,
    paths: list[Path],
    required_risk: str,
) -> tuple[bool, str, list[AccessPermission]]:
    """Resolve covering grants (deduped by id).

    If an approved grant already covers ``path`` (including explicit chat approvals for paths
    outside registered workspace roots), accept it **before** workspace policy — otherwise
    approve → resume would always fail with "path outside default work root" for Docker /app.
    Workspace policy still applies when no grant covers the path yet.
    When ``nexa_workspace_strict`` is true and the user has no registered roots, policy is
    evaluated first (grant alone does not bypass strict mode — see tests).
    """
    rows = _granted_rows_for_scope(db, owner_user_id, scope)
    if not paths:
        return False, "internal: no paths for permission check", []
    # Use workspace_registry.get_settings so tests that patch it behave like path_allowed_under_policy.
    s = workspace_registry_mod.get_settings()
    strict = bool(getattr(s, "nexa_workspace_strict", False))
    roots = list_roots(db, owner_user_id, active_only=True)
    strict_requires_registration = strict and not roots
    by_id: dict[int, AccessPermission] = {}
    for path in paths:
        if not strict_requires_registration:
            g = _matching_grant(rows, scope=scope, path=path, required_risk=required_risk)
            if g is not None:
                by_id[g.id] = g
                continue
        ok_pol, reason = path_allowed_under_policy(db, owner_user_id, path)
        if not ok_pol:
            return False, reason, []
        g = _matching_grant(rows, scope=scope, path=path, required_risk=required_risk)
        if not g:
            tgt_hint = str(path.resolve())[:200]
            return (
                False,
                f"no granted permission for scope={scope} covering {tgt_hint} "
                f"(risk >= {required_risk}). Use /permissions or ask Nexa to request access.",
                [],
            )
        by_id[g.id] = g
    return True, "", list(by_id.values())


def has_permission_for_paths(
    db: Session,
    owner_user_id: str,
    scope: str,
    paths: list[Path],
    required_risk: str,
) -> tuple[bool, str]:
    """Returns (ok, error_message)."""
    ok, err, _ = resolve_grants_for_paths(db, owner_user_id, scope, paths, required_risk)
    return ok, err


def finalize_permission_use(
    db: Session,
    owner_user_id: str,
    grants: list[AccessPermission],
    *,
    host_action: str,
    payload: dict[str, Any],
) -> str:
    """
    Record last_used_at; consume one-time grants; audit.

    Returns a single-line prefix for job output (trust visibility).
    """
    if not grants:
        return ""
    now_naive = datetime.utcnow()
    for g in grants:
        row = db.get(AccessPermission, g.id)
        if not row or row.owner_user_id != owner_user_id:
            continue
        row.last_used_at = now_naive
        md = dict(row.metadata_json or {})
        if md.get("grant_mode") == GRANT_MODE_ONCE:
            row.status = STATUS_CONSUMED
        row.metadata_json = md
        db.add(row)
        path_sensitive = False
        try:
            pblob = json.dumps(payload, sort_keys=True, default=str).lower()
            path_sensitive = any(
                h in pblob for h in (".env", ".ssh", "credential", "secret", "token", "private_key")
            )
        except (TypeError, ValueError):
            path_sensitive = False
        level = (payload or {}).get(NEXA_SENSITIVITY_KEY)
        if not isinstance(level, str) or level not in ("high", "medium", "low", "none"):
            level = detect_sensitivity(payload)
        sens_flag = path_sensitive or (level != "none")
        audit(
            db,
            event_type=ACCESS_PERMISSION_USED,
            actor="system",
            user_id=owner_user_id,
            message=f"grant_id={row.id} scope={row.scope}",
            metadata={
                **correlation_from_payload(payload),
                "permission_id": row.id,
                "host_action": host_action,
                "target_preview": (row.target or "")[:120],
                "permission_scope_used": row.scope,
                "instruction_source": payload.get("instruction_source"),
                "nexa_safety_policy_version": payload.get("nexa_safety_policy_version"),
                "nexa_safety_policy_sha256": payload.get("nexa_safety_policy_sha256"),
                "nexa_safety_policy_version_int": payload.get("nexa_safety_policy_version_int"),
                "data_sensitivity_flag": sens_flag,
                "sensitivity_level": level,
            },
        )

    db.commit()

    ha = (host_action or "").strip().lower()
    detail = ""
    if ha == "run_command":
        rn = (payload.get("run_name") or "").strip()
        detail = f" ({rn})" if rn else ""
        label = "command_run"
    elif ha in ("git_status", "git_commit", "git_push"):
        label = "git_operations"
    else:
        label = grants[0].scope if grants else ""

    tgt = (grants[0].target or "")[:240] if grants else ""
    extra = f" (+{len(grants) - 1} grants)" if len(grants) > 1 else ""
    why = reason_for_scope(grants[0].scope if grants else "")
    line = (
        f"🔐 Using permission: {label}{detail} on {tgt}{extra}\n"
        f"Reason: {why}"
    )
    return line


def resolve_host_executor_permission_paths(work_root: Path, payload: dict[str, Any]) -> list[Path]:
    """
    Absolute paths used for permission checks (must stay in sync with check_host_executor_job).
    """
    raw_abs = payload.get("nexa_permission_abs_targets")
    if isinstance(raw_abs, list) and raw_abs:
        paths_abs: list[Path] = []
        for item in raw_abs[:12]:
            s = str(item).strip()
            if not s:
                continue
            try:
                paths_abs.append(Path(s).expanduser().resolve())
            except OSError:
                continue
        if paths_abs:
            return paths_abs
    ha = (payload.get("host_action") or "").strip().lower()
    rel = (payload.get("relative_path") or payload.get("relative_dir") or "").strip()
    paths: list[Path] = []
    if ha == "read_multiple_files":
        raw_list = payload.get("relative_paths")
        if isinstance(raw_list, list):
            for item in raw_list[:40]:
                r = str(item).strip().replace("\\", "/").lstrip("/")
                if not r:
                    continue
                try:
                    paths.append((work_root / r).resolve())
                except OSError:
                    continue
        if rel:
            try:
                paths.append((work_root / rel.lstrip("/")).resolve())
            except OSError:
                paths.append(work_root.resolve())
        if not paths:
            paths.append(work_root.resolve())
    elif rel:
        try:
            paths.append((work_root / rel.lstrip("/")).resolve())
        except OSError:
            paths.append(work_root)
    else:
        cwd_extra = str(payload.get("cwd_relative") or "").strip()
        sr_cwd = safe_relative_path(cwd_extra.replace("\\", "/")) if cwd_extra else None
        if sr_cwd and ha in ("git_status", "run_command", "git_commit", "git_push"):
            try:
                paths.append((work_root / sr_cwd).resolve())
            except OSError:
                paths.append(work_root.resolve())
        else:
            paths.append(work_root.resolve())
    return paths


def check_host_executor_job(
    db: Session,
    *,
    owner_user_id: str,
    host_action: str,
    work_root: Path,
    payload: dict[str, Any],
) -> tuple[bool, str, list[AccessPermission]]:
    """
    Verify workspace policy + permission grants before host_executor runs an action.

    paths: absolute paths touched (best-effort).

    Returns grants to finalize **after** the action succeeds (caller responsibility).
    """
    ha = (host_action or "").strip().lower()
    rel = (payload.get("relative_path") or payload.get("relative_dir") or "").strip()
    paths = resolve_host_executor_permission_paths(work_root, payload)

    scope, req_risk = host_action_scope_and_risk(
        host_action,
        relative_path=rel or None,
        payload=payload if ha == "read_multiple_files" else None,
    )
    ok, err, grants = resolve_grants_for_paths(db, owner_user_id, scope, paths, req_risk)
    if not ok:
        audit(
            db,
            event_type=ACCESS_HOST_EXECUTOR_BLOCKED,
            actor="system",
            user_id=owner_user_id,
            message=err[:2000],
            metadata={
                **correlation_from_payload(payload),
                "host_action": host_action,
                "scope": scope,
            },
        )
        return False, err, []

    return True, "", grants


def format_permission_request_prompt(
    *,
    scope: str,
    target: str,
    risk_level: str,
    reason: str,
) -> str:
    """Short assistant bubble when a structured permission card is shown (Web/Telegram)."""
    del scope, target, reason  # Card + DB row carry details; do not narrate UI here.
    extra = ""
    if risk_level in (RISK_HIGH, RISK_CRITICAL):
        extra = "\n\nThis permission may modify files or affect your environment."
    return f"🔐 **Permission required**{extra}".strip()


def format_awaiting_permission_duplicate(*, permission_id: int) -> str:
    return (
        f"🔐 **Permission required**\n\n"
        f"A permission request is already pending (#{permission_id}) for this target."
    )


def permission_denied_fallback_message() -> str:
    return (
        "Denied. I did not access that path.\n\n"
        "You can ask again anytime if you change your mind."
    )


def canned_broad_access_response() -> str:
    return (
        "I can help set up broader access, but Nexa still scopes work to approved folders and "
        "allowlisted tools — I’ll always show risk before actions that change files, run commands, "
        "or touch credentials."
    )
