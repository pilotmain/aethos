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
from app.services.self_improvement.github_client import (
    GitHubError,
    get_github_client,
)
from app.services.self_improvement.proposal import (
    STATUS_APPLIED,
    STATUS_APPROVED,
    STATUS_MERGED,
    STATUS_PENDING,
    STATUS_PR_OPEN,
    STATUS_REJECTED,
    STATUS_REVERT_PR_OPEN,
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


# =============================================================================
# Phase 73c — GitHub auto-merge flow
# =============================================================================
#
# These endpoints are gated by ``NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED`` (the
# 73b master switch ``NEXA_SELF_IMPROVEMENT_ENABLED`` must also be on; the
# 73b ``_ensure_enabled`` is invoked by every endpoint below). Mutating
# endpoints additionally require the Telegram-linked owner.
#
# State machine for the GitHub flow (parallel to the 73b local-apply flow):
#
#     pending --approve--> approved --open-pr--> pr_open
#         pr_open --merge-pr--> merged
#         merged --revert-merge--> revert_pr_open
#
# ``applied`` (73b) and ``merged`` (73c) are deliberately separate terminal
# states — they describe two different deployment paths for the same diff.


def _ensure_github_enabled() -> None:
    s = get_settings()
    if not bool(getattr(s, "nexa_self_improvement_github_enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub auto-merge is disabled (NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=false).",
        )


def _github_error_to_http(exc: GitHubError) -> HTTPException:
    code = exc.code
    if code in {"github_disabled", "github_token_missing"}:
        return HTTPException(status_code=503, detail=str(exc))
    if code in {"pr_not_found", "github_repo_not_configured"}:
        return HTTPException(status_code=404, detail=str(exc))
    if code == "not_mergeable" or code == "merge_conflict":
        return HTTPException(status_code=409, detail=str(exc))
    if code == "diff_does_not_apply" or code == "diff_apply_failed":
        return HTTPException(status_code=412, detail=str(exc))
    if code == "github_network_error":
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/-/capabilities")
def capabilities(
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Tell the UI which sub-features are wired in this deployment.

    Open to any authenticated web user (read-only). The UI uses this to
    decide whether to render the GitHub-flow buttons.
    """
    _ensure_enabled()
    s = get_settings()
    gh_client = get_github_client()
    return {
        "ok": True,
        "self_improvement": {
            "enabled": True,
            "max_files_per_proposal": int(getattr(s, "nexa_self_improvement_max_files_per_proposal", 5) or 5),
            "max_diff_lines": int(getattr(s, "nexa_self_improvement_max_diff_lines", 400) or 400),
            "allowed_paths": str(getattr(s, "nexa_self_improvement_allowed_paths", "") or ""),
        },
        "github": {
            "enabled": gh_client.enabled,
            "configured": gh_client.has_token and bool(gh_client.owner) and bool(gh_client.repo),
            "owner": gh_client.owner if gh_client.enabled else None,
            "repo": gh_client.repo if gh_client.enabled else None,
            "base_branch": gh_client.base_branch if gh_client.enabled else None,
            "branch_prefix": gh_client.branch_prefix if gh_client.enabled else None,
            "merge_method": gh_client.merge_method if gh_client.enabled else None,
        },
        # Deferred-to-73d note for the UI; we declare the flag here so the
        # frontend can show a "coming in 73d" hint instead of a broken button.
        "auto_restart": {
            "enabled": False,
            "deferred": "phase73d",
        },
    }


@router.post("/{proposal_id}/open-pr")
async def open_pr(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Push the diff to a fresh ``self-improvement/<id>`` branch and open a PR.

    Hard preconditions (mirror the 73b local-apply gate):
    * Proposal in ``approved`` state.
    * Sandbox passed within :data:`APPLY_REQUIRES_FRESH_SANDBOX_S` seconds.
    * GitHub flow enabled + token + owner/repo configured.
    """
    _ensure_enabled()
    _ensure_github_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_APPROVED:
        raise HTTPException(status_code=409, detail=f"cannot_open_pr_from_status:{p.status}")
    sb = p.sandbox_result or {}
    if not sb or not sb.get("success"):
        raise HTTPException(status_code=412, detail="open_pr_requires_passing_sandbox_run")
    age = get_proposal_store().get_sandbox_run_age_seconds(proposal_id)
    if age is None or age > APPLY_REQUIRES_FRESH_SANDBOX_S:
        raise HTTPException(
            status_code=412,
            detail=(
                f"open_pr_requires_fresh_sandbox_run:age={age}s"
                f">max_{APPLY_REQUIRES_FRESH_SANDBOX_S}s"
            ),
        )

    gh = get_github_client()
    pr_body = (
        f"### Self-improvement proposal `{proposal_id}`\n\n"
        f"**Problem statement:**\n\n{p.problem_statement.strip()}\n\n"
        f"**Rationale:** {(p.rationale or 'n/a').strip()}\n\n"
        f"**Targets:** {', '.join(p.target_paths)}\n\n"
        f"_Generated and validated by AethOS Phase 73c (sandbox passed locally)._"
    )
    commit_message = (
        f"[self-improvement:{proposal_id}] {p.title}\n\n"
        f"{(p.rationale or '').strip()}\n\n"
        f"Proposal-id: {proposal_id}"
    )
    try:
        push = await gh.push_diff_branch(
            proposal_id=proposal_id,
            diff_text=p.diff,
            commit_message=commit_message,
            author_name="AethOS Self-Improvement",
            author_email="self-improvement@aethos.local",
        )
        pr = await gh.open_pull_request(
            head_branch=push.branch,
            title=p.title,
            body=pr_body,
        )
    except GitHubError as exc:
        raise _github_error_to_http(exc) from exc

    refreshed = get_proposal_store().set_github_state(
        proposal_id,
        new_status=STATUS_PR_OPEN,
        pr_number=pr.number,
        pr_url=pr.url,
        github_branch=push.branch,
    )
    return {
        "ok": True,
        "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p),
        "pr": {
            "number": pr.number,
            "url": pr.url,
            "head_branch": push.branch,
            "base_branch": pr.base_branch,
            "head_sha": push.head_sha,
        },
    }


@router.get("/{proposal_id}/pr-status")
async def pr_status(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Refresh the PR status from GitHub. Owner-only.

    Returns ``mergeable`` (True/False/None — None means GitHub is still
    computing, retry shortly), ``mergeable_state``, ``state``, ``merged``.
    """
    _ensure_enabled()
    _ensure_github_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if not p.pr_number:
        raise HTTPException(status_code=409, detail="proposal_has_no_open_pr")
    try:
        st = await get_github_client().get_pull_request_status(p.pr_number)
    except GitHubError as exc:
        raise _github_error_to_http(exc) from exc
    return {
        "ok": True,
        "pr": {
            "number": st.number,
            "state": st.state,
            "merged": st.merged,
            "mergeable": st.mergeable,
            "mergeable_state": st.mergeable_state,
            "head_sha": st.head_sha,
            "head_branch": st.head_branch,
            "base_branch": st.base_branch,
        },
    }


@router.post("/{proposal_id}/merge-pr")
async def merge_pr(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Merge the proposal's PR if it's mergeable.

    Hard preconditions:
    * Proposal in ``pr_open`` state with a recorded PR number.
    * Local sandbox passed within :data:`APPLY_REQUIRES_FRESH_SANDBOX_S`
      seconds (matches the 73b apply gate; protects against stale sandboxes
      surviving across long approval queues).
    * GitHub-side ``mergeable=True`` (PR has no merge conflict). NOTE: this
      repo currently has no Python/web CI workflow, so ``mergeable`` reflects
      *only* conflict status — the local sandbox is the actual safety net.
    """
    _ensure_enabled()
    _ensure_github_enabled()
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_PR_OPEN or not p.pr_number:
        raise HTTPException(status_code=409, detail=f"cannot_merge_from_status:{p.status}")
    sb = p.sandbox_result or {}
    if not sb or not sb.get("success"):
        raise HTTPException(status_code=412, detail="merge_requires_passing_sandbox_run")
    age = get_proposal_store().get_sandbox_run_age_seconds(proposal_id)
    if age is None or age > APPLY_REQUIRES_FRESH_SANDBOX_S:
        raise HTTPException(
            status_code=412,
            detail=(
                f"merge_requires_fresh_sandbox_run:age={age}s"
                f">max_{APPLY_REQUIRES_FRESH_SANDBOX_S}s"
            ),
        )

    gh = get_github_client()
    try:
        st = await gh.get_pull_request_status(p.pr_number)
    except GitHubError as exc:
        raise _github_error_to_http(exc) from exc
    if st.merged:
        return {
            "ok": True,
            "proposal": _proposal_to_dict(p),
            "note": "pr_already_merged",
        }
    if st.mergeable is False:
        raise HTTPException(
            status_code=409,
            detail=f"pr_not_mergeable:state={st.mergeable_state}",
        )
    if st.mergeable is None:
        raise HTTPException(
            status_code=409,
            detail="github_still_computing_mergeability_retry_shortly",
        )

    try:
        merge = await gh.merge_pull_request(
            p.pr_number,
            commit_title=f"{gh.pr_title_prefix} {p.title}",
            commit_message=(p.rationale or "").strip() or None,
        )
    except GitHubError as exc:
        raise _github_error_to_http(exc) from exc

    refreshed = get_proposal_store().set_github_state(
        proposal_id,
        new_status=STATUS_MERGED,
        merge_commit_sha=merge.merge_commit_sha,
    )
    return {
        "ok": True,
        "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p),
        "merge_commit_sha": merge.merge_commit_sha,
        "note": (
            "Merge committed on the remote. Operator must `git pull` and "
            "restart the API to deploy the change locally. Auto-restart is "
            "deferred to Phase 73d."
        ),
    }


@router.post("/{proposal_id}/revert-merge")
async def revert_merge(
    proposal_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Open a fresh PR that reverts the previously-merged commit.

    Available even when ``NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=false`` is
    flipped off mid-flight, so an operator can always undo a remote merge.
    The 73b local-apply ``/{id}/revert`` endpoint stays in place for the
    local-only flow.
    """
    _require_owner(db, app_user_id)
    p = _get_or_404(proposal_id)
    if p.status != STATUS_MERGED or not p.merge_commit_sha:
        raise HTTPException(status_code=409, detail=f"cannot_revert_merge_from_status:{p.status}")

    # Lazy import so the module still loads when GitHub is disabled.
    gh = get_github_client()
    if not gh.enabled or not gh.has_token:
        raise HTTPException(
            status_code=503,
            detail="revert_via_pr_requires_github_enabled_and_token",
        )

    revert_title = f"Revert {p.title}"
    revert_body = (
        f"Revert of self-improvement proposal `{proposal_id}` "
        f"(merge commit `{p.merge_commit_sha[:12]}`).\n\n"
        f"Original problem statement:\n\n{p.problem_statement.strip()}"
    )
    try:
        revert_pr = await gh.open_revert_pr(
            merge_commit_sha=p.merge_commit_sha,
            title=revert_title,
            body=revert_body,
        )
    except GitHubError as exc:
        raise _github_error_to_http(exc) from exc

    refreshed = get_proposal_store().set_github_state(
        proposal_id,
        new_status=STATUS_REVERT_PR_OPEN,
        revert_pr_number=revert_pr.number,
        revert_pr_url=revert_pr.url,
    )
    return {
        "ok": True,
        "proposal": _proposal_to_dict(refreshed) if refreshed else _proposal_to_dict(p),
        "revert_pr": {
            "number": revert_pr.number,
            "url": revert_pr.url,
            "head_branch": revert_pr.head_branch,
            "base_branch": revert_pr.base_branch,
        },
    }
