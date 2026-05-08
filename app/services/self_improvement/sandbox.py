"""
Phase 73b — Isolated ``git worktree`` sandbox runner.

Given a unified diff, this module:

1. Creates a fresh ``git worktree`` rooted at HEAD, in
   ``data/self_improvement_worktrees/<random-id>/`` so the application's
   live working copy is never touched.
2. Applies the diff inside that worktree with ``git apply --check`` first
   (dry-run) and then ``git apply``.
3. Runs ``python -m compileall -q app`` inside the worktree.
4. Runs a **targeted** ``pytest`` invocation. By default we infer test
   targets from the diff's modified file paths (mapping
   ``app/services/foo.py`` -> ``tests/test_foo*``); callers can pass an
   explicit list. If no tests can be found we still run a tiny smoke
   subset so the sandbox never returns "0 tests, all green".
5. Captures stdout/stderr (bounded), records exit codes and wall time.
6. Removes the worktree and its directory regardless of outcome.

Hard guarantees:

* No network access is required (pytest invocation runs offline; if a test
  imports network-using providers it will use the same env as the running
  app — that's intentional, otherwise the sandbox couldn't validate
  realistic changes).
* All subprocess calls have explicit timeouts. Hitting a timeout is
  treated as a sandbox failure, not a hang.
* Apply / pytest failures never propagate as Python exceptions to the
  caller — they're returned in the :class:`SandboxResult` dict.

The sandbox does NOT validate the diff against the allowlist itself —
that's the proposal validator's job. Pass diffs that already passed
:func:`app.services.self_improvement.proposal.validate_proposal_diff`.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.self_improvement.context import repo_root
from app.services.self_improvement.proposal import parse_unified_diff

logger = logging.getLogger(__name__)


_OUTPUT_TAIL_BYTES = 16 * 1024  # cap captured output at 16 KiB per stream


@dataclass
class SandboxStep:
    """Result of a single subprocess invocation inside the sandbox."""

    name: str
    cmd: list[str]
    exit_code: int
    duration_s: float
    stdout_tail: str
    stderr_tail: str
    timed_out: bool = False


@dataclass
class SandboxResult:
    """Top-level result returned by :func:`run_sandbox`."""

    proposal_id: str
    success: bool
    worktree_path: str
    steps: list[SandboxStep] = field(default_factory=list)
    started_at: float = 0.0
    duration_s: float = 0.0
    error: str | None = None  # set on harness failures (worktree create, etc.)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "success": self.success,
            "worktree_path": self.worktree_path,
            "started_at": self.started_at,
            "duration_s": self.duration_s,
            "error": self.error,
            "steps": [asdict(s) for s in self.steps],
        }


# --- Helpers ---------------------------------------------------------------


def _tail(stream: bytes | str | None, limit: int = _OUTPUT_TAIL_BYTES) -> str:
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        try:
            stream = stream.decode("utf-8", errors="replace")
        except Exception:
            stream = stream.decode("latin-1", errors="replace")
    if len(stream) <= limit:
        return stream
    return "...[truncated]...\n" + stream[-limit:]


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: float,
    name: str,
    env_extra: dict[str, str] | None = None,
) -> SandboxStep:
    """Run a subprocess, return a :class:`SandboxStep` (never raises)."""
    started = time.perf_counter()
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
        return SandboxStep(
            name=name,
            cmd=list(cmd),
            exit_code=int(proc.returncode),
            duration_s=time.perf_counter() - started,
            stdout_tail=_tail(proc.stdout),
            stderr_tail=_tail(proc.stderr),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return SandboxStep(
            name=name,
            cmd=list(cmd),
            exit_code=-1,
            duration_s=time.perf_counter() - started,
            stdout_tail=_tail(exc.stdout),
            stderr_tail=_tail(exc.stderr) or f"timeout after {timeout}s",
            timed_out=True,
        )
    except FileNotFoundError as exc:
        return SandboxStep(
            name=name,
            cmd=list(cmd),
            exit_code=-127,
            duration_s=time.perf_counter() - started,
            stdout_tail="",
            stderr_tail=f"binary not found: {exc}",
            timed_out=False,
        )
    except Exception as exc:  # noqa: BLE001
        return SandboxStep(
            name=name,
            cmd=list(cmd),
            exit_code=-1,
            duration_s=time.perf_counter() - started,
            stdout_tail="",
            stderr_tail=f"unexpected: {exc}",
            timed_out=False,
        )


def _infer_pytest_targets(diff_text: str, worktree: Path) -> list[str]:
    """
    From a parsed unified diff, infer which existing test files to run.

    Mapping rules (best-effort, keeps it predictable):
        ``app/services/<x>.py``         -> ``tests/test_<x>*.py``
        ``app/api/routes/<x>.py``       -> ``tests/test_<x>*.py``
        ``tests/<anything>``            -> the file itself
    """
    files = parse_unified_diff(diff_text)
    targets: list[str] = []
    for f in files:
        p = Path(f.path)
        if p.parts and p.parts[0] == "tests":
            t = worktree / f.path
            if t.is_file():
                targets.append(str(t.relative_to(worktree)))
            continue
        stem = p.stem
        if not stem:
            continue
        candidates = list((worktree / "tests").glob(f"test_{stem}*.py"))
        for c in candidates:
            try:
                rel = str(c.relative_to(worktree))
                if rel not in targets:
                    targets.append(rel)
            except ValueError:
                continue
    return targets


def _sandbox_workspace_root() -> Path:
    settings = get_settings()
    base = Path(getattr(settings, "nexa_data_dir", "") or "data")
    root = base / "self_improvement_worktrees"
    root.mkdir(parents=True, exist_ok=True)
    return root


# --- Public entry point ----------------------------------------------------


def run_sandbox(
    *,
    proposal_id: str,
    diff_text: str,
    pytest_targets: list[str] | None = None,
    timeout_s: float | None = None,
) -> SandboxResult:
    """
    Apply ``diff_text`` in an isolated git worktree and run validation
    (``compileall`` + a targeted ``pytest`` invocation).

    Always returns a :class:`SandboxResult` (no exceptions); inspect
    ``.success`` and ``.steps`` for the outcome. The worktree is removed
    before returning.

    :param proposal_id:    Echoed back into the result for audit.
    :param diff_text:      Unified diff that already passed validation.
    :param pytest_targets: Optional explicit list of test paths (relative
                           to the worktree). If None, inferred from the diff.
    :param timeout_s:      Wall-clock cap for *each* subprocess. Defaults
                           to ``settings.nexa_self_improvement_sandbox_timeout_s``.
    """
    settings = get_settings()
    if timeout_s is None:
        timeout_s = float(getattr(settings, "nexa_self_improvement_sandbox_timeout_s", 120) or 120)

    started = time.time()
    src_root = repo_root()
    workspace_root = _sandbox_workspace_root()
    worktree_dir = workspace_root / f"{proposal_id}-{uuid.uuid4().hex[:6]}"

    result = SandboxResult(
        proposal_id=proposal_id,
        success=False,
        worktree_path=str(worktree_dir),
        started_at=started,
    )

    # 1. Create the worktree at HEAD (no new branch — keep it ephemeral).
    add_step = _run(
        ["git", "worktree", "add", "--detach", str(worktree_dir), "HEAD"],
        cwd=src_root,
        timeout=min(timeout_s, 30.0),
        name="git_worktree_add",
    )
    result.steps.append(add_step)
    if add_step.exit_code != 0:
        result.error = "worktree_create_failed"
        result.duration_s = time.time() - started
        # Best-effort cleanup in case `git worktree add` partially succeeded.
        _force_cleanup_worktree(src_root, worktree_dir)
        return result

    try:
        # 2. Write the diff into a temp file inside the worktree and apply it.
        diff_path = worktree_dir / ".aethos_proposal.diff"
        try:
            diff_path.write_text(diff_text, encoding="utf-8")
        except OSError as exc:
            result.error = f"diff_write_failed:{exc}"
            return _finish_with_cleanup(result, src_root, worktree_dir, started)

        check_step = _run(
            ["git", "apply", "--check", str(diff_path)],
            cwd=worktree_dir,
            timeout=min(timeout_s, 30.0),
            name="git_apply_check",
        )
        result.steps.append(check_step)
        if check_step.exit_code != 0:
            result.error = "diff_does_not_apply_cleanly"
            return _finish_with_cleanup(result, src_root, worktree_dir, started)

        apply_step = _run(
            ["git", "apply", str(diff_path)],
            cwd=worktree_dir,
            timeout=min(timeout_s, 30.0),
            name="git_apply",
        )
        result.steps.append(apply_step)
        if apply_step.exit_code != 0:
            result.error = "diff_apply_failed"
            return _finish_with_cleanup(result, src_root, worktree_dir, started)

        # 3. compileall — fast and catches syntax errors immediately.
        compile_step = _run(
            ["python", "-m", "compileall", "-q", "app"],
            cwd=worktree_dir,
            timeout=timeout_s,
            name="compileall_app",
        )
        result.steps.append(compile_step)
        if compile_step.exit_code != 0:
            result.error = "compileall_failed"
            return _finish_with_cleanup(result, src_root, worktree_dir, started)

        # 4. Targeted pytest. If we can't infer any tests, we still run a small
        #    sanity subset so a passing sandbox actually means *something*.
        targets = pytest_targets or _infer_pytest_targets(diff_text, worktree_dir)
        if not targets:
            for fallback in ("tests/test_health.py", "tests/test_main.py"):
                if (worktree_dir / fallback).is_file():
                    targets = [fallback]
                    break
        pytest_cmd = ["python", "-m", "pytest", "-x", "-q"] + (targets or ["tests"])
        pytest_step = _run(
            pytest_cmd,
            cwd=worktree_dir,
            timeout=timeout_s,
            name="pytest",
        )
        result.steps.append(pytest_step)
        if pytest_step.exit_code != 0:
            result.error = (
                "pytest_timeout"
                if pytest_step.timed_out
                else f"pytest_failed:exit={pytest_step.exit_code}"
            )
            return _finish_with_cleanup(result, src_root, worktree_dir, started)

        result.success = True
        return _finish_with_cleanup(result, src_root, worktree_dir, started)
    except Exception as exc:  # noqa: BLE001 — defensive belt-and-braces
        logger.exception("run_sandbox unexpected failure for %s", proposal_id)
        result.error = f"sandbox_unexpected:{exc}"
        return _finish_with_cleanup(result, src_root, worktree_dir, started)


def _finish_with_cleanup(
    result: SandboxResult,
    src_root: Path,
    worktree_dir: Path,
    started: float,
) -> SandboxResult:
    result.duration_s = time.time() - started
    _force_cleanup_worktree(src_root, worktree_dir)
    return result


def _force_cleanup_worktree(src_root: Path, worktree_dir: Path) -> None:
    """Best-effort removal of a worktree and its directory."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=str(src_root),
            capture_output=True,
            timeout=15.0,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("worktree remove (CLI) failed for %s: %s", worktree_dir, exc)
    if worktree_dir.exists():
        try:
            shutil.rmtree(worktree_dir, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("worktree rmtree failed for %s: %s", worktree_dir, exc)
    # Prune any stale worktree references in .git/worktrees/.
    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(src_root),
            capture_output=True,
            timeout=15.0,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "SandboxResult",
    "SandboxStep",
    "run_sandbox",
]


# Quiet the unused-import warning for tempfile on platforms where Path uses it
# transitively; we keep the import explicit so future refactors that use it
# (e.g., for diff temp files) don't have to re-import.
_ = tempfile
