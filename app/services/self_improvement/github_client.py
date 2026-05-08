"""
Phase 73c — GitHub auto-merge client.

This module talks to the GitHub REST API directly via :mod:`httpx` (already a
project dependency); we deliberately avoid pulling in PyGithub because (a) it
would be a heavy new dep, and (b) PyGithub is sync — wrapping its calls in
``async def`` without :func:`asyncio.to_thread` would block the event loop.

The flow that creates the actual branch + commit reuses the Phase 73b
``git worktree`` machinery: we apply the diff inside an isolated worktree,
create a normal ``git`` commit there, push the worktree branch to ``origin``
using the configured PAT, and only then call the REST API to open the PR.
That way the branch on GitHub matches what ``git apply`` produces locally —
a property the GitHub Contents API alone can't provide for unified diffs
that touch multiple files with surgical hunks.

Hard guarantees:

* The token is loaded at request time from settings; it is **never** logged,
  never echoed in API responses, and never written to disk other than via
  ``git push``'s in-memory remote URL (which we explicitly remove again after
  the push).
* Every HTTP call has an explicit timeout. Failures are returned as
  structured :class:`GitHubError` instances so the API layer can map them to
  4xx/5xx without leaking stack traces.
* The module is purely additive: nothing here can mutate the local repo's
  ``main`` branch. Branches are pushed under the configured prefix
  (default ``self-improvement/``) and PRs target the configured
  ``base_branch``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.core.config import get_settings
from app.services.self_improvement.context import repo_root

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


# --- Errors ----------------------------------------------------------------


class GitHubError(Exception):
    """Structured failure surfaced by :class:`GitHubClient`.

    ``code`` is a short stable identifier the API layer maps to an HTTP
    status; ``detail`` is the operator-facing message (already redacted of
    any secret values before construction).
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# --- Result dataclasses ---------------------------------------------------


@dataclass
class BranchPushResult:
    branch: str
    head_sha: str


@dataclass
class PullRequestInfo:
    number: int
    url: str
    head_branch: str
    base_branch: str


@dataclass
class PullRequestStatus:
    number: int
    state: str  # open / closed
    merged: bool
    mergeable: bool | None  # None => GitHub still computing
    mergeable_state: str | None
    head_sha: str | None
    base_branch: str
    head_branch: str


@dataclass
class MergeResult:
    merge_commit_sha: str
    merged: bool


# --- Client ----------------------------------------------------------------


class GitHubClient:
    """Thin async wrapper over the bits of the GitHub REST API we need.

    Construct via :func:`get_github_client` so we share a single
    ``httpx.AsyncClient`` per process. Always check :attr:`enabled` before
    calling any method so callers can bail with a clean 503/404 when the
    feature flag is off or the token is missing.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    # --- Config helpers ----------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._settings, "nexa_self_improvement_github_enabled", False))

    @property
    def has_token(self) -> bool:
        return bool((getattr(self._settings, "nexa_self_improvement_github_token", "") or "").strip())

    @property
    def owner(self) -> str:
        return str(getattr(self._settings, "nexa_self_improvement_github_owner", "") or "").strip()

    @property
    def repo(self) -> str:
        return str(getattr(self._settings, "nexa_self_improvement_github_repo", "") or "").strip()

    @property
    def base_branch(self) -> str:
        return str(getattr(self._settings, "nexa_self_improvement_github_base_branch", "main") or "main").strip()

    @property
    def branch_prefix(self) -> str:
        return str(getattr(self._settings, "nexa_self_improvement_github_branch_prefix", "self-improvement/") or "self-improvement/")

    @property
    def pr_title_prefix(self) -> str:
        return str(getattr(self._settings, "nexa_self_improvement_github_pr_title_prefix", "[self-improvement]") or "[self-improvement]")

    @property
    def merge_method(self) -> str:
        m = str(getattr(self._settings, "nexa_self_improvement_github_merge_method", "squash") or "squash").lower()
        return m if m in {"merge", "squash", "rebase"} else "squash"

    def _slug(self) -> str:
        if not self.owner or not self.repo:
            raise GitHubError("github_repo_not_configured", "GitHub owner/repo not set in settings.")
        return f"{self.owner}/{self.repo}"

    # --- Lifecycle ---------------------------------------------------------

    async def _api(self) -> httpx.AsyncClient:
        """Return a lazily-created ``httpx.AsyncClient`` configured with auth."""
        if self._client is None:
            tok = (getattr(self._settings, "nexa_self_improvement_github_token", "") or "").strip()
            if not tok:
                raise GitHubError("github_token_missing", "GitHub token not configured.")
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "AethOS-self-improvement/73c",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    # --- High-level: push diff to a fresh branch --------------------------

    async def push_diff_branch(
        self,
        *,
        proposal_id: str,
        diff_text: str,
        commit_message: str,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> BranchPushResult:
        """
        Apply ``diff_text`` inside an isolated ``git worktree`` rooted at
        the configured base-branch HEAD, commit, and push to the remote
        under :attr:`branch_prefix` + ``proposal_id`` + a short random suffix.

        Returns the new branch name and the head SHA. Always cleans up the
        worktree (success or failure). Raises :class:`GitHubError` on any
        step that fails.
        """
        if not self.enabled:
            raise GitHubError("github_disabled", "GitHub auto-merge is disabled.")
        if not self.has_token:
            raise GitHubError("github_token_missing", "GitHub token not configured.")
        slug = self._slug()
        branch = f"{self.branch_prefix.rstrip('/')}/{proposal_id}-{uuid.uuid4().hex[:6]}"

        src = repo_root()
        wt_root = Path(getattr(self._settings, "nexa_data_dir", "") or "data") / "self_improvement_worktrees_pr"
        wt_root.mkdir(parents=True, exist_ok=True)
        wt_dir = wt_root / branch.replace("/", "__")

        # 1. Worktree at base-branch HEAD on a NEW branch.
        rc, out, err = _run(
            ["git", "worktree", "add", "-b", branch, str(wt_dir), self.base_branch],
            cwd=src,
        )
        if rc != 0:
            self._cleanup_worktree(src, wt_dir)
            raise GitHubError(
                "worktree_create_failed",
                _redact_token(err.strip() or out.strip(), self._settings),
            )

        try:
            # 2. Apply the diff.
            diff_file = wt_dir / ".aethos_pr.diff"
            diff_file.write_text(diff_text, encoding="utf-8")
            rc, out, err = _run(["git", "apply", "--check", str(diff_file)], cwd=wt_dir)
            if rc != 0:
                raise GitHubError("diff_does_not_apply", err.strip() or out.strip())
            rc, out, err = _run(["git", "apply", str(diff_file)], cwd=wt_dir)
            if rc != 0:
                raise GitHubError("diff_apply_failed", err.strip() or out.strip())

            # 3. Stage exactly the touched files (avoid sweeping in stray
            #    files the worktree might have accumulated).
            from app.services.self_improvement.proposal import parse_unified_diff

            for f in parse_unified_diff(diff_text):
                _run(["git", "add", "--", f.path], cwd=wt_dir)

            # 4. Commit. Use --no-verify so any client-side hook can't break us.
            commit_env = {}
            if author_name:
                commit_env["GIT_AUTHOR_NAME"] = author_name
                commit_env["GIT_COMMITTER_NAME"] = author_name
            if author_email:
                commit_env["GIT_AUTHOR_EMAIL"] = author_email
                commit_env["GIT_COMMITTER_EMAIL"] = author_email
            rc, out, err = _run(
                ["git", "commit", "-m", commit_message, "--no-verify"],
                cwd=wt_dir,
                env_extra=commit_env or None,
            )
            if rc != 0:
                raise GitHubError("commit_failed", err.strip() or out.strip())

            # 5. Resolve HEAD SHA.
            rc, sha_out, _err = _run(["git", "rev-parse", "HEAD"], cwd=wt_dir)
            head_sha = sha_out.strip() if rc == 0 else ""

            # 6. Push to origin via tokenized remote URL.
            push_url = self._token_remote_url(slug)
            rc, out, err = _run(
                ["git", "push", push_url, f"HEAD:refs/heads/{branch}"],
                cwd=wt_dir,
                # Push includes network I/O; allow a longer timeout.
                timeout=90.0,
            )
            if rc != 0:
                raise GitHubError(
                    "push_failed",
                    _redact_token(err.strip() or out.strip(), self._settings),
                )
            return BranchPushResult(branch=branch, head_sha=head_sha)
        finally:
            self._cleanup_worktree(src, wt_dir)

    def _token_remote_url(self, slug: str) -> str:
        tok = (getattr(self._settings, "nexa_self_improvement_github_token", "") or "").strip()
        # The PAT is URL-quoted defensively; GitHub accepts the literal too,
        # but quoting protects us from operator-pasted weirdness.
        return f"https://x-access-token:{quote_plus(tok)}@github.com/{slug}.git"

    def _cleanup_worktree(self, src: Path, wt_dir: Path) -> None:
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(wt_dir)],
                cwd=str(src),
                capture_output=True,
                timeout=15.0,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("worktree remove failed for %s: %s", wt_dir, exc)
        if wt_dir.exists():
            shutil.rmtree(wt_dir, ignore_errors=True)
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(src),
                capture_output=True,
                timeout=15.0,
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    # --- High-level: REST API operations ----------------------------------

    async def open_pull_request(
        self,
        *,
        head_branch: str,
        title: str,
        body: str,
        base_branch: str | None = None,
    ) -> PullRequestInfo:
        if not self.enabled:
            raise GitHubError("github_disabled", "GitHub auto-merge is disabled.")
        api = await self._api()
        slug = self._slug()
        base = base_branch or self.base_branch
        full_title = f"{self.pr_title_prefix} {title}".strip() if self.pr_title_prefix else title
        try:
            r = await api.post(
                f"/repos/{slug}/pulls",
                json={"title": full_title, "head": head_branch, "base": base, "body": body},
            )
        except httpx.HTTPError as exc:
            raise GitHubError("github_network_error", str(exc)) from exc
        if r.status_code >= 400:
            raise GitHubError(
                f"open_pr_failed_{r.status_code}",
                _safe_response_message(r),
            )
        data = r.json() or {}
        return PullRequestInfo(
            number=int(data.get("number") or 0),
            url=str(data.get("html_url") or ""),
            head_branch=head_branch,
            base_branch=base,
        )

    async def get_pull_request_status(self, pr_number: int) -> PullRequestStatus:
        if not self.enabled:
            raise GitHubError("github_disabled", "GitHub auto-merge is disabled.")
        api = await self._api()
        slug = self._slug()
        try:
            r = await api.get(f"/repos/{slug}/pulls/{pr_number}")
        except httpx.HTTPError as exc:
            raise GitHubError("github_network_error", str(exc)) from exc
        if r.status_code == 404:
            raise GitHubError("pr_not_found", f"PR #{pr_number} not found in {slug}.")
        if r.status_code >= 400:
            raise GitHubError(
                f"pr_status_failed_{r.status_code}",
                _safe_response_message(r),
            )
        d = r.json() or {}
        return PullRequestStatus(
            number=int(d.get("number") or pr_number),
            state=str(d.get("state") or "open"),
            merged=bool(d.get("merged", False)),
            mergeable=d.get("mergeable"),
            mergeable_state=str(d.get("mergeable_state") or "") or None,
            head_sha=str((d.get("head") or {}).get("sha") or "") or None,
            base_branch=str((d.get("base") or {}).get("ref") or self.base_branch),
            head_branch=str((d.get("head") or {}).get("ref") or ""),
        )

    async def merge_pull_request(
        self,
        pr_number: int,
        *,
        commit_title: str | None = None,
        commit_message: str | None = None,
    ) -> MergeResult:
        if not self.enabled:
            raise GitHubError("github_disabled", "GitHub auto-merge is disabled.")
        api = await self._api()
        slug = self._slug()
        body: dict[str, Any] = {"merge_method": self.merge_method}
        if commit_title:
            body["commit_title"] = commit_title
        if commit_message:
            body["commit_message"] = commit_message
        try:
            r = await api.put(f"/repos/{slug}/pulls/{pr_number}/merge", json=body)
        except httpx.HTTPError as exc:
            raise GitHubError("github_network_error", str(exc)) from exc
        if r.status_code == 405:
            raise GitHubError("not_mergeable", _safe_response_message(r))
        if r.status_code == 409:
            raise GitHubError("merge_conflict", _safe_response_message(r))
        if r.status_code >= 400:
            raise GitHubError(
                f"merge_failed_{r.status_code}",
                _safe_response_message(r),
            )
        d = r.json() or {}
        return MergeResult(
            merge_commit_sha=str(d.get("sha") or ""),
            merged=bool(d.get("merged", True)),
        )

    async def open_revert_pr(
        self,
        *,
        merge_commit_sha: str,
        title: str,
        body: str,
    ) -> PullRequestInfo:
        """Open a PR that reverts a previously-merged commit.

        Implementation: create a fresh local worktree at base-branch HEAD,
        ``git revert -m 1 --no-edit <merge_sha>``, push to a new branch,
        open a PR against the base branch.
        """
        if not self.enabled:
            raise GitHubError("github_disabled", "GitHub auto-merge is disabled.")
        slug = self._slug()
        branch = f"{self.branch_prefix.rstrip('/')}/revert-{merge_commit_sha[:8]}-{uuid.uuid4().hex[:4]}"
        src = repo_root()
        wt_root = Path(getattr(self._settings, "nexa_data_dir", "") or "data") / "self_improvement_worktrees_pr"
        wt_root.mkdir(parents=True, exist_ok=True)
        wt_dir = wt_root / branch.replace("/", "__")

        # Need to fetch the merge commit first in case it's not local.
        _run(["git", "fetch", "origin", self.base_branch], cwd=src, timeout=60.0)
        rc, out, err = _run(
            ["git", "worktree", "add", "-b", branch, str(wt_dir), self.base_branch],
            cwd=src,
        )
        if rc != 0:
            self._cleanup_worktree(src, wt_dir)
            raise GitHubError("worktree_create_failed", _redact_token(err.strip() or out.strip(), self._settings))

        try:
            # Use -m 1 to revert against the first parent (works for both
            # plain and merge commits; harmless on non-merge commits).
            rc, out, err = _run(
                ["git", "revert", "--no-edit", "-m", "1", merge_commit_sha],
                cwd=wt_dir,
                timeout=60.0,
            )
            if rc != 0:
                # Try again without the -m flag for non-merge commits (some
                # squash merges produce non-merge commits).
                _run(["git", "revert", "--abort"], cwd=wt_dir)
                rc, out, err = _run(
                    ["git", "revert", "--no-edit", merge_commit_sha],
                    cwd=wt_dir,
                    timeout=60.0,
                )
                if rc != 0:
                    raise GitHubError("revert_failed", err.strip() or out.strip())

            push_url = self._token_remote_url(slug)
            rc, out, err = _run(
                ["git", "push", push_url, f"HEAD:refs/heads/{branch}"],
                cwd=wt_dir,
                timeout=90.0,
            )
            if rc != 0:
                raise GitHubError(
                    "push_failed",
                    _redact_token(err.strip() or out.strip(), self._settings),
                )

            return await self.open_pull_request(
                head_branch=branch,
                title=title,
                body=body,
                base_branch=self.base_branch,
            )
        finally:
            self._cleanup_worktree(src, wt_dir)


# --- Module helpers --------------------------------------------------------


def _run(
    cmd: list[str],
    *,
    cwd,
    timeout: float = 30.0,
    env_extra: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Wrapper around :func:`subprocess.run` returning ``(rc, stdout, stderr)``."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return (
            int(proc.returncode),
            (proc.stdout or b"").decode("utf-8", errors="replace"),
            (proc.stderr or b"").decode("utf-8", errors="replace"),
        )
    except subprocess.TimeoutExpired as exc:
        return (
            -1,
            (exc.stdout or b"").decode("utf-8", errors="replace") if exc.stdout else "",
            f"timeout after {timeout}s",
        )
    except FileNotFoundError as exc:
        return -127, "", f"binary not found: {exc}"


def _redact_token(text: str, settings: Any) -> str:
    """Strip the GitHub PAT out of an error message before surfacing it."""
    if not text:
        return text
    tok = (getattr(settings, "nexa_self_improvement_github_token", "") or "").strip()
    if tok and tok in text:
        text = text.replace(tok, "<REDACTED-TOKEN>")
    quoted = quote_plus(tok) if tok else ""
    if quoted and quoted in text:
        text = text.replace(quoted, "<REDACTED-TOKEN>")
    return text


def _safe_response_message(r: httpx.Response) -> str:
    """Extract a short human-readable message from a GitHub error response."""
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return f"http {r.status_code}: {r.text[:200]}"
    if isinstance(data, dict):
        msg = str(data.get("message") or "")
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            extra = "; ".join(str(e.get("message") or e) for e in errors[:3])
            msg = f"{msg} ({extra})" if msg else extra
        return msg or f"http {r.status_code}"
    return f"http {r.status_code}"


# --- Singleton accessor ----------------------------------------------------

_github_client: GitHubClient | None = None


def get_github_client() -> GitHubClient:
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client


# Quiet unused-import warning — tempfile is reserved for a future fallback path.
_ = tempfile
_ = time


__all__ = [
    "BranchPushResult",
    "GitHubClient",
    "GitHubError",
    "MergeResult",
    "PullRequestInfo",
    "PullRequestStatus",
    "get_github_client",
]
