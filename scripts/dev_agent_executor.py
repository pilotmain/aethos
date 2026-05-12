# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Pick up an approved queued dev job, create a branch, write a Cursor prompt, optionally run
a CLI agent, then test / commit (and optionally push + PR).

Local workflow (no DEV_AGENT_COMMAND):
1. python scripts/dev_agent_executor.py
2. Open .agent_tasks/dev_job_N.md in Cursor, implement, run tests
3. DEV_AGENT_COMMIT_ONLY=true python scripts/dev_agent_executor.py
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("PYTHONUTF8", "1")
# Run before any `from app` (config loads .env and may re-apply TERM=API from parent); fix parent too.
_t0 = (os.environ.get("TERM") or "").strip()
if not _t0 or _t0.casefold() == "api" or _t0 in ("dumb", "unknown"):
    os.environ["TERM"] = "xterm-256color"
if "TERMCAP" in os.environ:
    os.environ.pop("TERMCAP", None)
del _t0

DEFAULT_CODEX_PATH = "/Applications/Codex.app/Contents/Resources/codex"
_BAD_T = frozenset(("", "API", "dumb", "unknown"))


def _subprocess_env() -> dict[str, str]:
    """env for all child processes: Cursor/IDEs often set TERM=API and break tset/reset/Codex."""
    e = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    t = (e.get("TERM") or "").strip()
    if not t or t in _BAD_T or t.casefold() == "api":
        e["TERM"] = "xterm-256color"
    e.pop("TERMCAP", None)
    e.setdefault("COLUMNS", "200")
    e.setdefault("LINES", "50")
    return e


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    if not cmd:
        raise ValueError("empty command list")
    if any(c is None for c in cmd):
        nil = [i for i, c in enumerate(cmd) if c is None]
        raise TypeError(
            f"run(): argv has None at index(es) {nil!r} (e.g. missing branch_name) — {cmd!r}"
        )
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
        env=_subprocess_env(),
    )


def run_cwd(cwd: str | Path, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    if not cmd:
        raise ValueError("empty command list")
    c = str(Path(cwd).resolve())
    print("$", " ".join(str(c) for c in cmd), f"(cwd={c})", flush=True)
    return subprocess.run(
        cmd,
        cwd=c,
        text=True,
        capture_output=True,
        check=check,
        env=_subprocess_env(),
    )


def _git_worktree() -> bool:
    """True if PROJECT_ROOT is inside a git work tree (clone or `git init`)."""
    p = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        env=_subprocess_env(),
    )
    return p.returncode == 0


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


CURSOR_POLL_SECONDS = int(os.getenv("CURSOR_POLL_SECONDS", "10"))
CURSOR_JOB_TIMEOUT_SECONDS = int(os.getenv("CURSOR_JOB_TIMEOUT_SECONDS", "3600"))

_log = logging.getLogger(__name__)


def _mask_database_url_for_log(url: str) -> str:
    """Hide password in logs unless DEV_JOB_PICKER_LOG_SECRETS=1."""
    if _env_flag("DEV_JOB_PICKER_LOG_SECRETS"):
        return url
    if not url or "sqlite" in url.split("://", 1)[0].lower():
        return url
    if "@" not in url or "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        cred, host = rest.rsplit("@", 1)
        if ":" in cred:
            user, _pw = cred.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
        return f"{scheme}://***@{host}"
    except Exception:  # noqa: BLE001
        return "<could not parse database url>"


def _log_dev_job_picker_identity(database_url: str) -> None:
    """settings.database_url is what SQLAlchemy uses after app config load."""
    _log.info("DEV_JOB_PICKER DB URL (from get_settings) = %s", _mask_database_url_for_log(database_url))
    env_d = (os.environ.get("DATABASE_URL") or "").strip()
    env_s = (os.environ.get("SQLALCHEMY_DATABASE_URL") or "").strip()
    if env_d or env_s:
        _log.info(
            "DEV_JOB_PICKER process env DATABASE_URL = %s",
            _mask_database_url_for_log(env_d) if env_d else "(unset)",
        )
        if env_s:
            _log.info(
                "DEV_JOB_PICKER process env SQLALCHEMY_DATABASE_URL = %s",
                _mask_database_url_for_log(env_s),
            )


def _dev_job_picker_session_snapshot(db) -> tuple[int, list[tuple]]:
    """
    No hidden filters — only status + worker_type for the count.
    Visible rows: last 5 dev_executor jobs (any status) for this DB session.
    """
    from sqlalchemy import func, select

    from app.models.agent_job import AgentJob

    c_stmt = (
        select(func.count())
        .select_from(AgentJob)
        .where(AgentJob.status == "approved")
        .where(AgentJob.worker_type == "dev_executor")
    )
    n = int(db.scalar(c_stmt) or 0)
    vis = (
        select(AgentJob.id, AgentJob.status, AgentJob.worker_type, AgentJob.created_at)
        .where(AgentJob.worker_type == "dev_executor")
        .order_by(AgentJob.created_at.desc())
        .limit(5)
    )
    raw = db.execute(vis).all()
    rows: list[tuple] = [tuple(r) for r in raw]
    return n, rows


def _dev_executor_pending_approval_hint(db) -> str:
    """Human hint when nothing is in `approved`: jobs often wait for Telegram approval."""
    from sqlalchemy import func, select

    from app.models.agent_job import AgentJob

    stmt = (
        select(AgentJob.status, func.count(AgentJob.id))
        .where(AgentJob.worker_type == "dev_executor")
        .where(
            AgentJob.status.in_(
                ["needs_approval", "needs_risk_approval", "queued"],
            )
        )
        .group_by(AgentJob.status)
    )
    rows = db.execute(stmt).all()
    if not rows:
        return ""
    parts = [f"{st}={int(n)}" for st, n in rows]
    return (
        " Pending dev_executor: "
        + ", ".join(parts)
        + ". In Telegram, reply `approve job #<id>` (after any high-risk ack) so the worker can pick it up."
    )


def _force_pick_approved_dev_executor(db):
    """Failsafe: same filters as the repo (status + worker_type only)."""
    from sqlalchemy import select

    from app.models.agent_job import AgentJob

    st = (
        select(AgentJob)
        .where(AgentJob.status == "approved")
        .where(AgentJob.worker_type == "dev_executor")
        .order_by(AgentJob.created_at.asc())
        .limit(1)
    )
    return db.scalars(st).first()


def _log_picked_job_lock_state(task) -> None:
    _log.info(
        "JOB_LOCK picked id=%s locked_by=%s lock_expires_at=%s started_at=%s approval_required=%s",
        getattr(task, "id", None),
        getattr(task, "locked_by", None),
        getattr(task, "lock_expires_at", None),
        getattr(task, "started_at", None),
        getattr(task, "approval_required", None),
    )


def open_in_cursor(task_file: Path) -> None:
    if not _env_flag("AUTO_OPEN_CURSOR"):
        print(f"Auto-open Cursor disabled. Open: {task_file}", flush=True)
        return
    if sys.platform != "darwin":
        return
    try:
        subprocess.run(
            ["open", "-a", "Cursor", str(task_file)],
            cwd=PROJECT_ROOT,
            check=False,
            env=_subprocess_env(),
        )
    except OSError as exc:
        print(f"Could not open Cursor: {exc} — open manually: {task_file}", flush=True)


def wait_for_done_file(
    done_path: Path, *, log_every: int | None = None
) -> bool:
    """Block until .done.md exists or timeout. Returns True if file now exists."""
    t0 = time.time()
    n = 0
    while not done_path.is_file():
        if time.time() - t0 > CURSOR_JOB_TIMEOUT_SECONDS:
            return False
        n += 1
        if log_every and n % log_every == 0:
            print(f"Still waiting for {done_path} …", flush=True)
        time.sleep(CURSOR_POLL_SECONDS)
    return True


def write_cursor_dev_prompt(task, *, done_path: Path) -> str:
    """Task body for .agent_tasks/dev_job_{id}.md (matches Cursor worker handoff spec)."""
    user_request = (task.instruction or "").strip() or (task.title or "").strip() or "See title."
    jid = task.id
    return f"""# Cursor dev job #{jid}

## User request

{user_request}

## Project

Nexa

## Your role

You are Cursor/Codex acting as a senior developer agent.

## Goal

Implement the requested change safely and minimally.

## Rules

- Work only inside this project.
- Do not read or modify `.env`.
- Do not read SSH keys, credentials, secrets, or private system files.
- Do not run destructive commands.
- Do not push or merge.
- Preserve existing behavior unless the task explicitly asks to change it.
- Add or update tests when useful.
- Run tests before finishing if possible.
- Keep the change focused.

## Completion contract

When done, create this file:

`.agent_tasks/dev_job_{jid}.done.md`

Write the final result in this format:

# Cursor result for job #{jid}

## Status

completed | failed | blocked

## Summary

- ...

## Files changed

- ...

## Tests run

- ...

## Final review

- What looks good
- Risks or concerns
- Suggested follow-up

Do not mark the job complete anywhere else. The local worker will detect the `.done.md` file.

Absolute path to completion file (for reference):

`{done_path}`

## Original title

{task.title}
"""


def find_default_agent_command() -> list[str] | None:
    """Default Codex CLI (only when DEV_AGENT_COMMAND is unset and binary exists)."""
    if (os.getenv("DEV_AGENT_DISABLE_CODEX_FALLBACK", "").strip().lower() in {"1", "true", "yes"}):
        return None
    candidate = Path(os.getenv("DEV_AGENT_CODEX_PATH", DEFAULT_CODEX_PATH))
    if not candidate.is_file():
        return None
    # Codex refuses "untrusted" dirs / certain git states unless this is set; local dev and no-git copies need it.
    return [
        str(candidate),
        "exec",
        "--full-auto",
        "--skip-git-repo-check",
        "--cd",
        PROJECT_ROOT,
        "-",
    ]


def _invoke_dev_agent_cli(
    *,
    done_path: Path,
    prompt_path: Path,
    work_cwd: str | Path | None = None,
) -> tuple[subprocess.CompletedProcess | None, list[str] | None]:
    """
    Run DEV_AGENT_COMMAND (stdin = prompt) or default Codex.
    Returns (None, None) when there is no CLI to run (manual Cursor path).
    """
    prompt_text = prompt_path.read_text(encoding="utf-8")
    wc = str(Path((work_cwd or PROJECT_ROOT)).resolve())
    explicit_agent_command = (os.getenv("DEV_AGENT_COMMAND") or "").strip()
    if explicit_agent_command:
        parts = shlex.split(explicit_agent_command)
        if not parts:
            raise ValueError("DEV_AGENT_COMMAND is empty after parse")
        print("Running agent:", parts, flush=True)
        p = subprocess.run(
            parts,
            cwd=wc,
            text=True,
            input=prompt_text,
            capture_output=True,
            env=_subprocess_env(),
        )
        return p, parts
    parts = find_default_agent_command()
    if not parts:
        print("No DEV_AGENT_COMMAND set, and the default Codex binary is not present (or is disabled).", flush=True)
    elif not _git_worktree() and not _env_flag("DEV_AGENT_CODEX_ALLOW_NO_GIT"):
        print(
            "Skipping default Codex: not a git work tree (or `git` is unavailable). "
            "Use `git init` / a clone, set DEV_AGENT_COMMAND, or DEV_AGENT_CODEX_ALLOW_NO_GIT=true to force Codex on this path.",
            flush=True,
        )
        parts = None
    if not parts:
        return None, None
    parts = parts[:-1] + ["-o", str(done_path), parts[-1]]
    print("Running default local Codex agent:", parts[:-1], flush=True)
    p = subprocess.run(
        parts,
        cwd=wc,
        text=True,
        input=prompt_text,
        capture_output=True,
        env=_subprocess_env(),
    )
    return p, parts


def _raise_on_agent_process_failure(p: subprocess.CompletedProcess, parts: list | None) -> None:
    if p.returncode == 0:
        return
    if p.stdout:
        print(p.stdout, flush=True)
    if p.stderr:
        print(p.stderr, file=sys.stderr, flush=True)
    out = (p.stdout or "").strip()[-2000:]
    err = (p.stderr or "").strip()[-2000:]
    detail: list[str] = []
    if out:
        detail.append(f"stdout (tail):\n{out}")
    if err:
        detail.append(f"stderr (tail):\n{err}")
    if not detail:
        detail.append("(no stdout/stderr captured)")
    cmd_hint = f" {parts!r}" if parts else ""
    raise RuntimeError(
        f"agent process exited {p.returncode} — command:{cmd_hint} —\n" + "\n".join(detail)
    )


def _notify_dev_job_failed(task, message: str) -> None:
    if (getattr(task, "worker_type", None) or "") != "dev_executor":
        return
    from app.services.telegram_outbound import send_telegram_message

    chat = (getattr(task, "telegram_chat_id", None) or "").strip() or str(
        (task.payload_json or {}).get("telegram_chat_id") or ""
    )
    if not chat:
        return
    jid = getattr(task, "id", "?")
    send_telegram_message(
        chat,
        f"Cursor job #{jid} failed.\n\n{message[:3000]}",
    )


def _mark_dev_failed(db, jobs, task, message: str) -> None:
    jobs.mark_failed(db, task, message)
    _notify_dev_job_failed(task, message)


def _fulfill_if_done_exists(db, repo, task):
    """
    If `.done.md` exists, run shared finalize (tests, .review.md, ready_for_review, optional Telegram).
    """
    from app.services.cursor_dev_handoff import fulfill_dev_job_after_done_file

    t = repo.get(db, task.id) or task
    if (t.status or "") != "waiting_for_cursor" or (getattr(t, "worker_type", None) or "") != "dev_executor":
        return None
    return fulfill_dev_job_after_done_file(db, t)


def _resume_waiting_for_cursor(db, jobs, repo, task) -> int:
    """
    Job is waiting for an agent: prompt file exists, but a prior run exited before running the
    agent (e.g. no DEV_AGENT / Codex) or the operator did not re-invoke the script for this status.
    Re-run the CLI if configured so DEV_AGENT can be picked up without re-queuing a job.
    """
    p_task = (task.cursor_task_path or "").strip()
    prompt_path = Path(p_task) if p_task else Path(PROJECT_ROOT) / ".agent_tasks" / f"dev_job_{task.id}.md"
    done_from_payload = str((task.payload_json or {}).get("handoff_marker_path") or "").strip()
    done_path = (
        Path(done_from_payload) if done_from_payload else Path(PROJECT_ROOT) / ".agent_tasks" / f"dev_job_{task.id}.done.md"
    )
    if not prompt_path.is_file():
        print(f"Job {task.id} is waiting_for_cursor but prompt file is missing: {prompt_path}", flush=True)
        return 0
    from app.services.aider_autonomous_loop import _work_root_for_dev_job_payload

    wc = Path(_work_root_for_dev_job_payload(task))
    p, parts = _invoke_dev_agent_cli(
        done_path=done_path, prompt_path=prompt_path, work_cwd=wc
    )
    if p is None:
        print(
            f"Job {task.id} still in manual mode (no non-interactive agent on this worktree). "
            f"Open: {prompt_path} — or set DEV_AGENT_COMMAND and wait for the next operator cycle, "
            f"or run: python scripts/dev_agent_executor.py",
            flush=True,
        )
        return 0
    try:
        _raise_on_agent_process_failure(p, parts)
    except Exception as exc:  # noqa: BLE001
        _mark_dev_failed(db, jobs, task, f"{type(exc).__name__}: {str(exc)}")
        print(f"Job failed: {exc}", file=sys.stderr, flush=True)
        return 1
    try:
        if not done_path.is_file():
            _mark_dev_failed(
                db, jobs, task, "Dev agent process exited 0 but completion file is missing: " + str(done_path)
            )
            return 1
        finished = _fulfill_if_done_exists(db, repo, task)
        if not finished:
            # Should not happen with valid state
            return 0
    except Exception as exc:  # noqa: BLE001
        _mark_dev_failed(db, jobs, task, f"{type(exc).__name__}: {str(exc)}")
        print(f"Job failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


def slugify(text: str) -> str:
    safe = "".join(c.lower() if c.isalnum() else "-" for c in text)
    parts = [p for p in safe.split("-") if p]
    safe2 = "-".join(parts) if parts else ""
    return safe2[:50] or "dev-job"


def _tests_ok(result: subprocess.CompletedProcess, cmd: str) -> bool:
    if result.returncode == 0:
        return True
    if "pytest" in cmd and result.returncode == 5:
        return True
    return False


def run_tests() -> None:
    test_cmd = os.getenv("DEV_AGENT_TEST_COMMAND", "python -m compileall -q app")
    print(f"Running tests: {test_cmd}", flush=True)
    tr = subprocess.run(
        test_cmd,
        cwd=PROJECT_ROOT,
        shell=True,
        text=True,
        capture_output=True,
        env=_subprocess_env(),
    )
    print(tr.stdout or "", end="")
    print(tr.stderr or "", end="", file=sys.stderr)
    if not _tests_ok(tr, test_cmd):
        raise RuntimeError(f"Tests failed (exit {tr.returncode}):\n{tr.stderr or tr.stdout or ''}")


def _summarize_review_no_git(task) -> str:
    run_tests()
    handoff = str((task.payload_json or {}).get("handoff_marker_path") or "").strip()
    handoff_text = ""
    if handoff and Path(handoff).is_file():
        handoff_text = Path(handoff).read_text(encoding="utf-8", errors="replace").strip()
    test_cmd = os.getenv("DEV_AGENT_TEST_COMMAND", "python -m compileall -q app")
    parts = [
        "Review summary (this worktree has no `git` metadata; there is no branch to diff here):",
        "",
        f"Required checks: {test_cmd} (re-run in the dev executor if you need to confirm).",
    ]
    if handoff_text:
        parts += ["", "Handoff from agent / Cursor:", "", handoff_text]
    else:
        parts += ["", "No handoff file on disk; inspect files under this project root manually."]
    parts += [
        "",
        f"Reply `approve commit job #{task.id}` to mark the job complete (no `git commit` is created).",
    ]
    return "\n".join(parts).strip()


def summarize_review(task) -> str:
    if not _git_worktree():
        return _summarize_review_no_git(task)

    if not (getattr(task, "branch_name", None) or "").strip():
        return (
            "Review summary: this dev job has **no `branch_name`** on record yet, so the local executor "
            "cannot align the git worktree for review. Open the job in Nexa, ensure the job reached "
            "`in_progress` / `changes_ready` with a feature branch, then retry."
        )

    br = (run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True).stdout or "").strip()
    target = (task.branch_name or "").strip()
    if br != target:
        run(["git", "checkout", target], check=True)

    run_tests()

    names = run(["git", "status", "--short"], check=True).stdout.strip()
    diff_names = run(["git", "diff", "--name-only"], check=True).stdout.strip()
    diff_stat = run(["git", "diff", "--stat"], check=True).stdout.strip()
    if not names and not diff_names:
        raise RuntimeError("No code changes detected for review.")

    parts = [
        "Review summary:",
        "",
        f"Branch: {task.branch_name}",
        "",
        "Changed files:",
        diff_names or names or "[none found]",
        "",
        "Diff stat:",
        diff_stat or "[no diff stat available]",
        "",
        "Validation:",
        f"- {os.getenv('DEV_AGENT_TEST_COMMAND', 'python -m compileall -q app')}",
        "- Passed",
        "",
        f"Reply `approve commit job #{task.id}` to allow commit.",
    ]
    return "\n".join(parts).strip()


def _complete_no_git_after_user_commit_approval(db, jobs, task) -> None:
    run_tests()
    base = (task.result or "").strip()
    fin = f"{base}\n\n" if base else ""
    fin += "Completed. No `git` repository in this worktree, so there was no commit, SHA, or push."
    jobs.mark_completed(
        db,
        task,
        fin,
    )
    print("Completed (no git worktree).", flush=True)


def _no_git_review_telegram_body(task, done_path: Path) -> str:
    lines = [
        f"Dev job {task.id}: required checks passed (worktree has no `git` repo, so there is no branch/PR to inspect).",
        f"Test command: {os.getenv('DEV_AGENT_TEST_COMMAND', 'python -m compileall -q app')}.",
    ]
    if done_path.is_file():
        note = done_path.read_text(encoding="utf-8", errors="replace").strip()
        if note:
            lines += ["", "Handoff from agent / Cursor:", "", note[:3000] + ("…" if len(note) > 3000 else "")]
    else:
        lines += ["", "No `.done` handoff file on disk; inspect the files it edited manually."]
    lines += ["", f"Reply `approve review job #{task.id}` to continue (commit step is a no-op for no-git)."]
    return "\n".join(lines)


def run_tests_and_commit(db, jobs, task) -> None:
    if not _git_worktree():
        _complete_no_git_after_user_commit_approval(db, jobs, task)
        return
    if not getattr(task, "branch_name", None):
        raise RuntimeError("in_progress dev job has no branch_name")
    br = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True).stdout.strip()
    if br != task.branch_name:
        run(["git", "checkout", task.branch_name], check=True)

    run_tests()

    st = run(["git", "status", "--porcelain"], check=True).stdout.strip()
    if not st:
        _mark_dev_failed(db, jobs, task, "No code changes detected.")
        print("No code changes detected.", flush=True)
        return

    run(["git", "add", "."], check=True)
    safe_title = re.sub(r"[\r\n\"]", " ", (task.title or "task")[:72])
    run(["git", "commit", "-m", f"Dev job #{task.id}: {safe_title}".strip()], check=True)
    sha = run(["git", "rev-parse", "HEAD"], check=True).stdout.strip()
    pr_url: str | None = None

    if os.getenv("DEV_AGENT_PUSH", "false").lower() == "true":
        run(["git", "push", "-u", "origin", task.branch_name], check=True)
        if os.getenv("DEV_AGENT_CREATE_PR", "false").lower() == "true":
            out = run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    task.branch_name,
                    "-t",
                    f"Dev job #{task.id}: {safe_title}"[:200],
                    "-b",
                    f"Automated PR for dev job #{task.id}. Please review the diff before merge.",
                ],
                check=True,
            ).stdout
            pr_url = (out or "").strip() or None
            if pr_url:
                print("PR created:", pr_url, flush=True)

    existing = (task.result or "").strip()
    final_result = (
        existing + "\n\n" if existing else ""
    ) + f"Committed changes on {sha}."
    if pr_url:
        final_result += f"\nPR: {pr_url}"
    jobs.mark_completed(db, task, final_result, commit_sha=sha, pr_url=pr_url)
    print(f"Completed job: {task.id} commit={sha}", flush=True)


def main() -> int:
    from app.core.config import ensure_subprocess_term_env, get_settings
    from app.core.db import SessionLocal, ensure_schema
    from app.services.agent_job_service import AgentJobService

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True
    )

    # app.core.config was loaded; .env/IDE can still set TERM=API — normalize again for this process.
    ensure_subprocess_term_env()
    os.environ.setdefault("LC_ALL", "en_US.UTF-8")
    os.environ.setdefault("LANG", "en_US.UTF-8")

    ensure_schema()

    db = SessionLocal()
    jobs = AgentJobService()
    repo = jobs.repo
    try:
        _log_dev_job_picker_identity(get_settings().database_url)

        from app.services.handoff_tracking_service import HandoffTrackingService

        from app.services.worker_heartbeat import write_heartbeat
        from app.services.worker_state import is_stop_after_current, is_worker_paused

        n_stale = jobs.sweep_stale_dev_locks(db)
        if n_stale:
            print(f"Marked {n_stale} stale-locked job(s) failed.", flush=True)

        write_heartbeat(current_job_id=None, current_stage="idle")
        HandoffTrackingService().process_waiting_handoffs(db)

        aider_commit = repo.get_next_for_worker_statuses(
            db, "dev_executor", ["approved_to_commit"]
        )
        if aider_commit:
            try:
                from app.services.aider_autonomous_loop import process_approved_to_commit

                process_approved_to_commit(db, aider_commit, jobs, from_worker=True)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(
                    db, jobs, aider_commit, f"{type(exc).__name__}: {str(exc)[:2000]}"
                )
                print(f"Job failed: {exc}", flush=True)
                return 1
            return 0

        review_task = repo.get_next_for_worker_statuses(db, "dev_executor", ["review_approved"])
        if review_task:
            try:
                summary = summarize_review(review_task)
                jobs.mark_needs_commit_approval(db, review_task, summary)
                print(summary, flush=True)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(db, jobs, review_task, f"{type(exc).__name__}: {str(exc)}")
                print(f"Job failed: {exc}", flush=True)
                return 1
            return 0

        commit_task = repo.get_next_for_worker_statuses(db, "dev_executor", ["commit_approved"])
        if commit_task:
            try:
                repo.update(db, commit_task, status="in_progress")
                run_tests_and_commit(db, jobs, commit_task)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(db, jobs, commit_task, f"{type(exc).__name__}: {str(exc)}")
                print(f"Job failed: {exc}", flush=True)
                return 1
            return 0

        if os.getenv("DEV_AGENT_COMMIT_ONLY", "false").lower() == "true":
            task = repo.get_next_for_worker_statuses(db, "dev_executor", ["commit_approved"]) or repo.get_latest_in_progress_for_worker(db, "dev_executor")
            if not task:
                print("No in-progress dev job found.", flush=True)
                return 0
            try:
                repo.update(db, task, status="in_progress")
                run_tests_and_commit(db, jobs, task)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(db, jobs, task, f"{type(exc).__name__}: {str(exc)}")
                print(f"Job failed: {exc}", flush=True)
                return 1
            return 0

        wfc = repo.get_next_for_worker_statuses(db, "dev_executor", ["waiting_for_cursor"])
        if wfc:
            try:
                return _resume_waiting_for_cursor(db, jobs, repo, wfc)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(db, jobs, wfc, f"{type(exc).__name__}: {str(exc)}")
                print(f"Job failed: {exc}", file=sys.stderr, flush=True)
                return 1

        # Host worker must key off *worker_type* (e.g. dev_executor), not *kind* (e.g. dev_task).
        # No extra filters (locks, started_at) in the picker — only status + worker_type.
        n_approved, visible_rows = _dev_job_picker_session_snapshot(db)
        _log.info(
            "DEV_JOB_PICKER DEBUG: approved dev_executor count in THIS session = %s",
            n_approved,
        )
        _log.info("DEV_JOB_PICKER visible rows (last 5 dev_executor) = %s", visible_rows)

        task = repo.get_next_for_worker_statuses(db, "dev_executor", ["approved"])
        if not task and n_approved > 0:
            _log.warning(
                "DEV_JOB_PICKER: repository get_next returned None but count>0; running failsafe select (same filters)."
            )
            task = _force_pick_approved_dev_executor(db)
            if task:
                _log.warning(
                    "FORCED PICK (failsafe) job id=%s status=%s worker_type=%s kind=%s",
                    task.id,
                    task.status,
                    task.worker_type,
                    task.kind,
                )
        if not task:
            pending_hint = _dev_executor_pending_approval_hint(db)
            if n_approved > 0:
                _log.warning(
                    "DEV_JOB_PICKER: count says %s approved but get_next returned None — "
                    "check locks, worker_type, or DB session. %s",
                    n_approved,
                    pending_hint or "(no needs_approval/queued rows)",
                )
                print(
                    "No approved dev job picked (picker mismatch). See logs.",
                    flush=True,
                )
            else:
                _log.info(
                    "DEV_JOB_PICKER: no dev_executor jobs in status `approved`.%s",
                    pending_hint or " (none waiting for approval either.)",
                )
                msg = "No approved dev jobs."
                if pending_hint:
                    msg += pending_hint
                else:
                    msg += (
                        " When Nexa sends a job number in Telegram, reply `approve job #<id>` "
                        "so this worker can run it (status must become `approved`)."
                    )
                print(msg, flush=True)
            return 0
        _log.info(
            "DEV_JOB_PICKER found job id=%s status=%s worker_type=%s kind=%s",
            task.id,
            task.status,
            task.worker_type,
            task.kind,
        )
        _log_picked_job_lock_state(task)

        from app.services.aider_autonomous_loop import _work_root_for_dev_job_payload

        pl_mode = dict(task.payload_json or {})
        ed = pl_mode.get("execution_decision") or {}
        mode = (ed.get("mode") or pl_mode.get("dev_execution_mode") or "autonomous_cli").strip()
        effective_tool_key = (
            (ed.get("tool_key") or pl_mode.get("preferred_dev_tool") or "aider") or "aider"
        ).strip()
        if mode == "autonomous_cli" and effective_tool_key != "aider":
            mode = "ide_handoff"
        _log.info(
            "DEV_RUN job id=%s mode=%s tool=%s orchestrator=%s",
            task.id,
            mode,
            effective_tool_key,
            bool(pl_mode.get("orchestrator")),
        )
        if mode == "github_pr":
            _mark_dev_failed(
                db,
                jobs,
                task,
                "dev_execution_mode github_pr is not implemented yet.",
            )
            return 1

        if _env_flag("DEV_AGENT_AUTO_RUN") and mode == "autonomous_cli":
            if is_worker_paused():
                print("dev_worker paused (.runtime/dev_worker_paused) — not starting a new run.", flush=True)
                return 0
            if is_stop_after_current():
                print(
                    "dev_worker stop-after-current (.runtime/dev_worker_stop_after_current) — not picking new approved jobs.",
                    flush=True,
                )
                return 0
            try:
                from app.services.aider_autonomous_loop import run_aider_autonomous_for_approved_job

                return run_aider_autonomous_for_approved_job(db, task, jobs)
            except Exception as exc:  # noqa: BLE001
                _mark_dev_failed(db, jobs, task, f"{type(exc).__name__}: {str(exc)[:2000]}")
                print(f"Autonomous run failed: {exc}", file=sys.stderr, flush=True)
                return 1

        work_root = Path(_work_root_for_dev_job_payload(task))
        branch = f"agent/job-{task.id}-{slugify(task.title)}"
        prompt_dir = work_root / ".agent_tasks"
        prompt_path = prompt_dir / f"dev_job_{task.id}.md"
        done_path = prompt_dir / f"dev_job_{task.id}.done.md"
        gt = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(work_root),
            text=True,
            capture_output=True,
            env=_subprocess_env(),
        )
        use_git = gt.returncode == 0 and (gt.stdout or "").strip() == "true"
        if use_git:
            run_cwd(work_root, ["git", "checkout", "-b", branch], check=True)
            repo.update(db, task, status="in_progress", branch_name=branch)
        else:
            print("No git worktree: skipping `git checkout` (edits and handoff still work).", flush=True)
            repo.update(db, task, status="in_progress", branch_name=None)

        try:
            prompt_dir.mkdir(exist_ok=True)
            no_git_block = (
                f"""
## Worktree: no `git` repository

This project root is not a git work tree. Create or edit files directly. Do not rely on
branches, commits, or PRs. You may still use `git` inside this folder later if the user
initializes a repo, but the automated executor is not using git for this run.

""".lstrip()
                if not use_git
                else ""
            )
            branch_rules = (
                "- Do not make destructive git operations.\n- Do not commit directly to `main` / `master` without a branch/PR."
                if use_git
                else "- Do not run destructive commands; no `git` branch/PR in this worktree (but files are still real)."
            )
            header = ""
            if not use_git:
                header = no_git_block
            if use_git and branch:
                header += f"## Git / branch (this run)\n\n- Active branch: `{branch}`\n- {branch_rules}\n\n"
            prompt_path.write_text(
                header + write_cursor_dev_prompt(task, done_path=done_path),
                encoding="utf-8",
            )

            payload = dict(task.payload_json or {})
            payload["handoff_marker_path"] = str(done_path)
            repo.update(
                db,
                task,
                status="waiting_for_cursor",
                cursor_task_path=str(prompt_path),
                payload_json=payload,
            )
            print(f"Prompt written to: {prompt_path}", flush=True)
            print(f"Completion marker: {done_path}", flush=True)

            if mode == "ide_handoff":
                tool_key = (effective_tool_key or "vscode").strip()
                if tool_key == "aider":
                    tool_key = "vscode"
                from app.services.dev_tools.registry import get_dev_tool

                conn = get_dev_tool(tool_key) or get_dev_tool("manual")
                if conn:
                    r = conn.open_project(work_root, task_file=prompt_path)
                    print(r.message, flush=True)
            elif mode == "manual_review":
                from app.services.telegram_outbound import send_telegram_message

                chat = (getattr(task, "telegram_chat_id", None) or "").strip() or str(
                    (pl_mode.get("telegram_chat_id") or "")
                )
                if chat:
                    send_telegram_message(
                        chat,
                        f"Dev job #{task.id} (manual review). Task file:\n`{prompt_path}`\n"
                        f"When done, add `.agent_tasks/dev_job_{task.id}.done.md`.",
                    )
            else:
                open_in_cursor(prompt_path)

            if mode in ("ide_handoff", "manual_review"):
                p, parts = None, None
            else:
                p, parts = _invoke_dev_agent_cli(
                    done_path=done_path,
                    prompt_path=prompt_path,
                    work_cwd=work_root,
                )
            if p is None:
                if _env_flag("DEV_AGENT_BLOCK_UNTIL_DONE") and done_path:
                    print(
                        f"Blocking until {done_path.name} exists (or timeout). "
                        f"CURSOR_POLL_SECONDS={CURSOR_POLL_SECONDS}, "
                        f"CURSOR_JOB_TIMEOUT_SECONDS={CURSOR_JOB_TIMEOUT_SECONDS}.",
                        flush=True,
                    )
                    if wait_for_done_file(done_path, log_every=1):
                        fin = _fulfill_if_done_exists(db, repo, task)
                        if fin:
                            return 0
                print("Waiting for manual Cursor/Codex work (task file in .agent_tasks/).", flush=True)
                print("Open the prompt in Cursor (already attempted on macOS) and write the completion .done.md.", flush=True)
                print("When done exists, the bot operator loop or this script will finalize to ready_for_review.", flush=True)
                return 0
            _raise_on_agent_process_failure(p, parts)

            if not done_path.is_file():
                _mark_dev_failed(
                    db, jobs, task, "Dev agent process exited 0 but completion file is missing: " + str(done_path)
                )
                return 1
            res = _fulfill_if_done_exists(db, repo, task)
            if res is None:
                print("Completion file present but handoff was not applied (see operator or logs).", flush=True)
            return 0
        except Exception as exc:  # noqa: BLE001
            _mark_dev_failed(db, jobs, task, f"{type(exc).__name__}: {str(exc)}")
            print(f"Job failed: {exc}", file=sys.stderr, flush=True)
            return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
