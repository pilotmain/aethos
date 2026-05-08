"""
Phase 73b — Self-Improvement (Genesis Loop) HTTP surface.

All endpoints live under ``/api/v1/self_improvement`` and require web auth
(``X-User-Id`` plus optional ``Authorization: Bearer <NEXA_WEB_API_TOKEN>``).
Mutating endpoints additionally require the Telegram-linked **owner**, the
same trust gate the Marketplace + agent-health surfaces use for destructive
actions. The whole router is gated by ``NEXA_SELF_IMPROVEMENT_ENABLED``
(default ``False``); when off, every endpoint returns ``404`` to keep the
surface dark for non-owner snoops.

Endpoints (v1):

* ``GET    /``                           — list proposals (filter by status).
* ``GET    /{id}``                       — proposal detail.
* ``POST   /propose``                    — generate + validate + persist a
                                           pending proposal (owner-only).
* ``POST   /{id}/sandbox``               — run the diff in an isolated
                                           ``git worktree``; record the
                                           result on the proposal row
                                           (owner-only).
* ``POST   /{id}/approve``               — flip status to ``approved`` (no
                                           file changes; owner-only).
* ``POST   /{id}/reject``                — flip status to ``rejected``
                                           (owner-only).
* ``POST   /{id}/apply``                 — apply the diff to the working
                                           copy and create a single
                                           ``[self-improvement]`` commit.
                                           **Does not push, does not
                                           restart the API.** Requires the
                                           proposal to be ``approved`` AND
                                           have a passing sandbox run from
                                           within the last
                                           ``APPLY_REQUIRES_FRESH_SANDBOX_S``
                                           seconds (owner-only).
* ``POST   /{id}/revert``                — ``git revert <sha>`` the
                                           previously-applied commit
                                           (always available regardless of
                                           the enabled flag, so an operator
                                           can always undo).

GitHub-API integration / branch+PR flow / auto-merge / auto-restart are
deferred to Phase 73c.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.self_improvement.context import repo_root
from app.services.self_improvement.proposal import (
    STATUS_APPLIED,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_REVERTED,
    Proposal,
    generate_proposal_diff,
    get_proposal_store,
    validate_proposal_diff,
)
from app.services.self_improvement.sandbox import run_sandbox
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/self_improvement", tags=["self-improvement"])

#: Maximum age (seconds) of a passing sandbox run that still counts as
#: "fresh" for ``/apply``. Short window is intentional — the working tree
#: changes constantly, so a 10-minute-old sandbox is no longer authoritative.
APPLY_REQUIRES_FRESH_SANDBOX_S: float = 60.0


# --- Auth + enabled gate ---------------------------------------------------


def _ensure_enabled() -> None:
    s = get_settings()
    if not bool(getattr(s, "nexa_self_improvement_enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Self-improvement is disabled (NEXA_SELF_IMPROVEMENT_ENABLED=false).",
        )


def _require_owner(db: Session, app_user_id: str) -> None:
    role = get_telegram_role_for_app_user(db, app_user_id)
    if not is_owner_role(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Self-improvement mutating endpoints require the Telegram-linked owner."
            ),
        )


def _proposal_to_dict(p: Proposal) -> dict[str, Any]:
    d = p.to_dict()
    return d


def _get_or_404(proposal_id: str) -> Proposal:
    p = get_proposal_store().get(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal_not_found")
    return p


# --- Pydantic bodies -------------------------------------------------------


class ProposeBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    problem_statement: str = Field(..., min_length=4, max_length=8000)
    target_paths: list[str] = Field(..., min_length=1, max_length=10)
    extra_context_paths: list[str] = Field(default_factory=list, max_length=10)
    rationale: str | None = Field(default=None, max_length=4000)


class SandboxBody(BaseModel):
    pytest_targets: list[str] | None = Field(
        default=None,
        description="Optional explicit test paths inside the worktree. "
                    "If omitted the sandbox infers targets from the diff.",
        max_length=20,
    )


# --- Read endpoints --------------------------------------------------------


@router.get("/")
def list_proposals(
    status_filter: str | None = None,
    limit: int = 50,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """List proposals (newest first). Read-only; visible to any web user."""
    _ensure_enabled()
    rows = get_proposal_store().list_proposals(status=status_filter, limit=limit)
    return {"ok": True, "proposals": [_proposal_to_dict(p) for p in rows]}


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    p = _get_or_404(proposal_id)
    return {"ok": True, "proposal": _proposal_to_dict(p)}


# --- Mutating endpoints (owner-only) ---------------------------------------


@router.post("/propose")
def propose(
    body: ProposeBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Generate + validate + persist a new proposal."""
    _ensure_enabled()
    _require_owner(db, app_user_id)
    try:
        diff_text, _ctxs = generate_proposal_diff(
            problem_statement=body.problem_statement,
            target_paths=body.target_paths,
            extra_context_paths=body.extra_context_paths,
            budget_member_id=app_user_id,
            budget_member_name="self_improvement_proposer",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_proposal_diff failed")
        raise HTTPException(status_code=502, detail=f"llm_generation_failed:{exc}") from exc

    if not diff_text or diff_text.strip() == "# NO_DIFF_AVAILABLE":
        raise HTTPException(status_code=422, detail="llm_returned_no_diff_available")

    validation = validate_proposal_diff(diff_text)
    if not validation.ok:
        # Surface the structured failure to the caller without persisting.
        return {
            "ok": False,
            "validation": {
                "errors": validation.errors,
                "warnings": validation.warnings,
                "files": [{"path": f.path, "added_lines": f.added_lines,
                           "removed_lines": f.removed_lines, "is_new": f.is_new,
                           "is_delete": f.is_delete} for f in validation.files],
                "total_added": validation.total_added,
                "total_removed": validation.total_removed,
            },
            "diff_preview": diff_text[:4096],
        }

    persisted = get_proposal_store().create(
        title=body.title,
        problem_statement=body.problem_statement,
        target_paths=body.target_paths,
        diff=diff_text,
        rationale=body.rationale,
        created_by=app_user_id,
    )
    return {"ok": True, "proposal": _proposal_to_dict(persisted), "validation": {
        "errors": [], "warnings": validation.warnings,
        "files": [{"path": f.path, "added_lines": f.added_lines,
                   "removed_lines": f.removed_lines, "is_new": f.is_new,
                   "is_delete": f.is_delete} for f in validation.files],
        "total_added": validation.total_added,
        "total_removed": validation.total_removed,
    }}


@router.post("/{proposal_id}/sandbox")
def sandbox(
    proposal_id: str,
    body: SandboxBody | None = None,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Run the diff in an isolated git worktree; persist the result."""
    _ensure_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status in {STATUS_APPLIED, STATUS_REVERTED}:
        raise HTTPException(
            status_code=409,
            detail=f"sandbox_not_meaningful_for_status:{p.status}",
        )
    targets = body.pytest_targets if body else None
    result = run_sandbox(
        proposal_id=proposal_id,
        diff_text=p.diff,
        pytest_targets=targets,
    )
    refreshed = get_proposal_store().record_sandbox_result(proposal_id, result.to_dict())
    return {"ok": True, "sandbox": result.to_dict(),
            "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p)}


@router.post("/{proposal_id}/approve")
def approve(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Flip status pending -> approved. Does not modify any files."""
    _ensure_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_PENDING:
        raise HTTPException(status_code=409, detail=f"cannot_approve_from_status:{p.status}")
    refreshed = get_proposal_store().set_status(proposal_id, STATUS_APPROVED)
    return {"ok": True, "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p)}


@router.post("/{proposal_id}/reject")
def reject(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ensure_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status not in {STATUS_PENDING, STATUS_APPROVED}:
        raise HTTPException(status_code=409, detail=f"cannot_reject_from_status:{p.status}")
    refreshed = get_proposal_store().set_status(proposal_id, STATUS_REJECTED)
    return {"ok": True, "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p)}


def _git(args: list[str], *, cwd, timeout: float = 30.0) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, timeout=timeout, check=False
    )
    return (
        int(proc.returncode),
        (proc.stdout or b"").decode("utf-8", errors="replace"),
        (proc.stderr or b"").decode("utf-8", errors="replace"),
    )


@router.post("/{proposal_id}/apply")
def apply_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Apply the diff to the working copy and create a local commit.

    Hard preconditions:
    * Proposal must be in ``approved`` state.
    * Proposal must have a passing sandbox run within
      :data:`APPLY_REQUIRES_FRESH_SANDBOX_S` seconds (so the operator can't
      approve, wait a day, and apply against a totally different working
      copy).
    """
    _ensure_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_APPROVED:
        raise HTTPException(status_code=409, detail=f"cannot_apply_from_status:{p.status}")
    sb = p.sandbox_result or {}
    if not sb or not sb.get("success"):
        raise HTTPException(status_code=412, detail="apply_requires_passing_sandbox_run")
    age = get_proposal_store().get_sandbox_run_age_seconds(proposal_id)
    if age is None or age > APPLY_REQUIRES_FRESH_SANDBOX_S:
        raise HTTPException(
            status_code=412,
            detail=(
                f"apply_requires_fresh_sandbox_run:age={age}s"
                f">max_{APPLY_REQUIRES_FRESH_SANDBOX_S}s"
            ),
        )

    src = repo_root()
    diff_path = src / "data" / "self_improvement_apply.diff"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        diff_path.write_text(p.diff, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"diff_write_failed:{exc}") from exc

    try:
        # 1. Confirm clean apply.
        rc, out, err = _git(["apply", "--check", str(diff_path)], cwd=src)
        if rc != 0:
            raise HTTPException(status_code=412, detail=f"apply_check_failed:{err.strip() or out.strip()}")
        # 2. Apply.
        rc, out, err = _git(["apply", str(diff_path)], cwd=src)
        if rc != 0:
            raise HTTPException(status_code=500, detail=f"apply_failed:{err.strip() or out.strip()}")
        # 3. Stage + commit only the files the diff touched (avoid sweeping
        #    unrelated working-tree changes into the self-improvement commit).
        from app.services.self_improvement.proposal import parse_unified_diff
        for f in parse_unified_diff(p.diff):
            _git(["add", "--", f.path], cwd=src)
        msg = f"[self-improvement:{proposal_id}] {p.title}\n\n{(p.rationale or '').strip()}\n\nProposal-id: {proposal_id}"
        rc, out, err = _git(["commit", "-m", msg, "--no-verify"], cwd=src, timeout=60.0)
        if rc != 0:
            # Roll back the working-tree apply so we don't leave half-applied changes.
            _git(["restore", "--staged", "."], cwd=src)
            _git(["checkout", "--", "."], cwd=src)
            raise HTTPException(status_code=500, detail=f"commit_failed:{err.strip() or out.strip()}")
        rc, sha_out, _err = _git(["rev-parse", "HEAD"], cwd=src)
        sha = sha_out.strip() if rc == 0 else None
    finally:
        try:
            diff_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    refreshed = get_proposal_store().set_status(
        proposal_id, STATUS_APPLIED, applied_commit_sha=sha
    )
    return {
        "ok": True,
        "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p),
        "applied_commit_sha": sha,
        "note": (
            "Commit is local only. Operator must run `git push origin main` "
            "and restart the API to deploy the change."
        ),
    }


@router.post("/{proposal_id}/revert")
def revert_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """``git revert`` a previously-applied proposal commit.

    Available regardless of ``NEXA_SELF_IMPROVEMENT_ENABLED`` so an
    operator can always undo.
    """
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_APPLIED or not p.applied_commit_sha:
        raise HTTPException(status_code=409, detail=f"cannot_revert_from_status:{p.status}")
    src = repo_root()
    rc, out, err = _git(
        ["revert", "--no-edit", p.applied_commit_sha],
        cwd=src,
        timeout=60.0,
    )
    if rc != 0:
        # Best-effort cleanup of any half-revert state.
        _git(["revert", "--abort"], cwd=src)
        raise HTTPException(status_code=500, detail=f"revert_failed:{err.strip() or out.strip()}")
    rc, sha_out, _err = _git(["rev-parse", "HEAD"], cwd=src)
    revert_sha = sha_out.strip() if rc == 0 else None
    refreshed = get_proposal_store().set_status(
        proposal_id, STATUS_REVERTED, reverted_commit_sha=revert_sha
    )
    return {
        "ok": True,
        "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p),
        "reverted_commit_sha": revert_sha,
    }
