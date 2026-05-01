"""
Aider (or any fixed DEV_AGENT_COMMAND) autonomous loop: run agent, tests, approval, commit.
Never passes user text to shell; only env-driven commands and fixed git.
"""
from __future__ import annotations

import contextvars
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_job import AgentJob
from app.services.agent_job_service import AgentJobService
from app.services.audit_service import audit
from app.services.cursor_dev_handoff import build_final_worker_review, review_path_for_job
from app.services.dev_artifacts import (
    copy_review_to_artifacts,
    copy_task_to_artifacts,
    ensure_job_artifact_dir,
    write_diff_artifacts,
)
from app.services.dev_preflight import (
    format_preflight_errors,
    run_dev_preflight,
    write_preflight_json,
)
from app.services.dev_worktree_guards import ensure_clean_worktree, is_mainish
from app.services.gateway.approval_persistence import persist_job_waiting_approval
from app.services.handoff_paths import AGENT_TASKS_DIR, PROJECT_ROOT
from app.services.secret_scan import scan_combined_diff_for_secrets
from app.services.telegram_dev_ux import compact_review_for_telegram, user_friendly_status
from app.services.telegram_outbound import send_telegram_message
from app.services.worker_heartbeat import write_heartbeat
from app.services.worker_identity import get_worker_id

ROOT = str(PROJECT_ROOT)
_aider_cwd: contextvars.ContextVar[str] = contextvars.ContextVar("nexa_aider_cwd", default="")


def _jroot() -> str:
    v = (_aider_cwd.get() or "").strip()
    return v if v else ROOT


def _work_root_for_dev_job_payload(job) -> str:
    pl = dict(getattr(job, "payload_json", None) or {})
    r = (pl.get("repo_path") or "").strip()
    if r:
        p = Path(r).expanduser().resolve()
        if p.is_dir() and (p / ".git").exists():
            return str(p)
    return ROOT


_BAD_T = frozenset(("", "API", "dumb", "unknown"))
# One git checkout: cap concurrent in-flight dev agent work (see DEV_AGENT_MAX_ACTIVE_JOBS)
_DEV_ACTIVE_STATUSES = [
    "in_progress",
    "agent_running",
    "changes_ready",
    "waiting_approval",
    "approved_to_commit",
]


def _subprocess_env() -> dict[str, str]:
    e = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    t = (e.get("TERM") or "").strip()
    if not t or t in _BAD_T or t.casefold() == "api":
        e["TERM"] = "xterm-256color"
    e.pop("TERMCAP", None)
    e.setdefault("COLUMNS", "200")
    e.setdefault("LINES", "50")
    return e


def _env_flag(name: str, default: str = "false") -> bool:
    return (os.getenv(name) or default).strip().lower() in {"1", "true", "yes", "y", "on"}


def _run(
    args: list[str] | str,
    *,
    cwd: str | None = None,
    shell: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    if not shell and isinstance(args, str):
        raise ValueError("args must be a list if shell is False")
    c = (cwd or "").strip() or _jroot()
    return subprocess.run(  # noqa: S603
        args,
        cwd=c,
        text=True,
        capture_output=True,
        check=check,
        env=_subprocess_env(),
        shell=shell,
    )


def _git_worktree() -> bool:
    p = _run(["git", "rev-parse", "--is-inside-work-tree"], check=False, shell=False)
    return p.returncode == 0 and (p.stdout or "").strip() == "true"


def _slugify(text: str) -> str:
    safe = "".join(c.lower() if c.isalnum() else "-" for c in text)
    parts = [p for p in safe.split("-") if p]
    out = "-".join(parts) if parts else ""
    return (out[:50] or "dev-job").strip() or "dev-job"


def write_aider_task_file(job) -> Path:
    AGENT_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    p = AGENT_TASKS_DIR / f"dev_job_{job.id}.md"
    body = (job.instruction or "").strip() or (job.title or "").strip() or "No instruction."
    pl0 = dict(getattr(job, "payload_json", None) or {})
    p_label = (pl0.get("project_key") or "nexa").strip() or "Nexa"
    text = f"""# Dev job #{job.id}: {job.title}

{body}

## Project

{p_label}

## Rules

- Work only inside this repository.
- Do not read or modify `.env` or other secrets.
- Do not `git push` to main or open PRs to main without a human.
- Leave changes for the worker to commit: prefer not committing, or only commit on this feature branch.

## Tests

- Run: `{os.getenv("DEV_AGENT_TEST_COMMAND", "python -m pytest")}` when possible.

"""
    p.write_text(text, encoding="utf-8")
    return p


def write_revision_task_file(
    job, revision_instruction: str, revision_number: int
) -> Path:
    """Append-only revision handoff: worker runs aider on this file next."""
    AGENT_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = AGENT_TASKS_DIR / f"dev_job_{job.id}_revision_{revision_number}.md"
    otitle = (getattr(job, "title", None) or "").strip() or "Dev job"
    inst = f"""# Revision task for job #{job.id}

## Original job
{otitle}

## Revision request
{revision_instruction}

## Existing work
The previous implementation is already on this job branch.

## Instructions
- Do not restart from scratch unless you must. Keep the good parts.
- Apply only the requested revision, run tests, and keep work on the same branch.
- The worker will commit only after you approve in Telegram (when that flow runs).

## Completion
When done, also write: `.agent_tasks/dev_job_{job.id}.done.md` with a short status line.
"""
    path.write_text(inst, encoding="utf-8")
    return path


def notify_dev_job_failed_telegram(
    db: Session, job_service: AgentJobService, job, reason: str
) -> None:
    if (os.getenv("DEV_WORKER_TELEGRAM_NOTIFY", "true") or "true").strip().lower() not in {
        "1", "true", "yes", "y", "on"
    }:
        return
    if (getattr(job, "worker_type", None) or "") != "dev_executor":
        return
    chat = (getattr(job, "telegram_chat_id", None) or "").strip() or str(
        (dict(getattr(job, "payload_json", None) or {}).get("telegram_chat_id") or "")
    )
    if not chat or not (reason or "").strip():
        return
    jid = getattr(job, "id", "?")
    r = (reason or "").strip()[:2000]
    st = (getattr(job, "failure_stage", None) or getattr(job, "status", None) or "unknown")[:200]
    text = (
        f"Job #{jid} failed.\n\n"
        f"Stage: {st}\n"
        f"Worker: {get_worker_id()}\n\n"
        f"Reason: {r}\n\n"
        f"Useful:\n"
        f"• Ask about job #{jid} for logs, tests, files, or diff • retry after fixes • dev health status\n"
    )[:3900]
    if send_telegram_message(chat, text, max_len=4000):
        j2 = job_service.repo.get(db, job.id) or job
        job_service.mark_notified(db, j2)


def run_aider_subprocess(task_file: Path) -> str:
    raw = (os.getenv("DEV_AGENT_COMMAND") or "").strip()
    if not raw:
        raise RuntimeError(
            "DEV_AGENT_COMMAND must be set (e.g. aider --yes --message-file {task_file})"
        )
    cmd = raw.replace("{task_file}", str(task_file)).replace("{TASK_FILE}", str(task_file))
    p = _run(
        cmd,
        shell=True,
        check=True,
    )  # type: ignore[arg-type]
    return p.stdout or ""


def _agent_timeout_sec() -> int:
    return int(
        os.getenv("DEV_AGENT_TIMEOUT_SECONDS")
        or str(get_settings().dev_agent_timeout_seconds)
    )


def _test_timeout_sec() -> int:
    return int(
        os.getenv("DEV_AGENT_TEST_TIMEOUT_SECONDS")
        or str(get_settings().dev_agent_test_timeout_seconds)
    )


def run_aider_to_artifact_logs(artifact_dir: Path, task_file: Path) -> int:
    os.makedirs(artifact_dir, exist_ok=True)
    raw = (os.getenv("DEV_AGENT_COMMAND") or "").strip()
    if not raw:
        raise RuntimeError("DEV_AGENT_COMMAND not set")
    cmd = raw.replace("{task_file}", str(task_file)).replace("{TASK_FILE}", str(task_file))
    tmo = _agent_timeout_sec()
    out_p = artifact_dir / "agent_stdout.log"
    err_p = artifact_dir / "agent_stderr.log"
    with open(out_p, "w", encoding="utf-8") as o, open(err_p, "w", encoding="utf-8") as e:
        p = subprocess.run(  # noqa: S603
            cmd,
            cwd=_jroot(),
            shell=True,
            text=True,
            stdout=o,
            stderr=e,
            env=_subprocess_env(),
            timeout=tmo,
        )
    return p.returncode


def _run_tests_capture() -> str:
    if (os.getenv("HANDOFF_RUN_TESTS", "true").strip().lower() not in {"1", "true", "yes", "y", "on"}):
        return "Tests/checks skipped (HANDOFF_RUN_TESTS=false)."
    cmd = os.getenv("DEV_AGENT_TEST_COMMAND", "python -m compileall -q app")
    p = _run(
        cmd,
        shell=True,
        check=False,
    )  # type: ignore[arg-type]
    out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
    if p.returncode not in (0, 5):
        return f"Tests/checks failed (exit {p.returncode}):\n" + out[-8000:]
    return f"Tests/checks (exit {p.returncode}):\n" + out[-8000:]


def _run_tests_capture_artifacts(artifact_dir: Path) -> str:
    """Like _run_tests_capture but always writes tests_*.log under the artifact directory."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if (os.getenv("HANDOFF_RUN_TESTS", "true").strip().lower() not in {
        "1", "true", "yes", "y", "on"
    }):
        msg = "Tests/checks skipped (HANDOFF_RUN_TESTS=false)."
        (artifact_dir / "tests_stdout.log").write_text(msg, encoding="utf-8")
        (artifact_dir / "tests_stderr.log").write_text("", encoding="utf-8")
        return msg
    cmd = os.getenv("DEV_AGENT_TEST_COMMAND", "python -m compileall -q app")
    tmo = _test_timeout_sec()
    p = subprocess.run(  # noqa: S603
        cmd,
        cwd=_jroot(),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
        env=_subprocess_env(),
        timeout=tmo,
    )  # type: ignore[arg-type]
    (artifact_dir / "tests_stdout.log").write_text(p.stdout or "", encoding="utf-8")
    (artifact_dir / "tests_stderr.log").write_text(p.stderr or "", encoding="utf-8")
    out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
    if p.returncode not in (0, 5):
        return f"Tests/checks failed (exit {p.returncode}):\n" + out[-8000:]
    return f"Tests/checks (exit {p.returncode}):\n" + out[-8000:]


def approval_inline_markup(job_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Approve commit", "callback_data": f"job:{job_id}:approve"},
                {"text": "Reject", "callback_data": f"job:{job_id}:reject"},
            ],
            [
                {"text": "Show diff", "callback_data": f"job:{job_id}:diff"},
                {
                    "text": "Request changes",
                    "callback_data": f"job:{job_id}:request_changes",
                },
            ],
        ]
    }


def _git_diff_name_only() -> str:
    p = _run(["git", "diff", "--name-only", "HEAD"], check=False, shell=False)
    if p.returncode != 0 or not (p.stdout or "").strip():
        p2 = _run(["git", "diff", "--name-only"], check=False, shell=False)
        return (p2.stdout or "").strip()[:2000]
    return (p.stdout or "").strip()[:2000]


def format_approval_message(job, review: str) -> str:
    _aider_cwd.set(_work_root_for_dev_job_payload(job))
    preview = compact_review_for_telegram((review or "")[:10_000], 2200)
    br = (getattr(job, "branch_name", None) or "").strip() or "(none)"
    pl = getattr(job, "payload_json", None) or {}
    pc = dict(pl or {}).get("policy") or {}
    risk = (getattr(job, "risk_level", None) or pc.get("risk", "normal") or "normal")
    ts = (getattr(job, "tests_status", None) or "unknown")
    ul = user_friendly_status((getattr(job, "status", None) or "waiting_approval"))
    files = _git_diff_name_only() or "[none — see host branch]"
    line_files = "\n".join(f"- {ln}" for ln in files.splitlines()[:18]) if files else "- (none)"
    if len(line_files) > 1200:
        line_files = line_files[:1200] + "…"
    ov = ""
    if (getattr(job, "override_failed_tests", None) or False) and (ts or "") == "failed":
        ov = (
            "\nCaution: you used `approve despite failed tests` — review the host branch and diff before committing.\n"
        )
    tail = (
        "\n\nActions: Approve / Reject / Request changes / Show diff "
        "(buttons below, or the same in chat.)"
    )
    header = (
        f"Job #{job.id} — ready for approval\n"
        f"({ul})\n\n"
        f"Branch: {br}\n"
        f"Files changed:\n{line_files}\n\n"
        f"Tests: {ts}\n"
        f"Risk: {risk}"
        f"{ov}\n\n"
        f"Summary:\n"
    )
    max_total = 3900
    room = max_total - len(header) - len(tail)
    if room < 80:
        room = 80
    preview_fit = preview if len(preview) <= room else preview[: max(room - 1, 0)] + "…"
    return (header + preview_fit + tail)[:max_total]


def get_git_diff_capped(max_len: int = 3000) -> str:
    if not _git_worktree():
        return "[not a git work tree]"
    p = _run(["git", "diff"], check=False, shell=False)
    if p.returncode != 0:
        return (p.stderr or p.stdout or "git diff failed")[:max_len]
    t = p.stdout or ""
    if not t.strip():
        return (
            "[no unstaged diff — the agent may have created commits. "
            "On the host: `git log -2 --oneline` on the job branch.]"
        )
    return t[:max_len] + ("" if len(t) <= max_len else "…")


def _git_rev() -> str:
    return _run(["git", "rev-parse", "HEAD"], shell=False).stdout.strip()


def _git_porcelain() -> str:
    p = _run(["git", "status", "--porcelain"], shell=False, check=False)
    return p.stdout or ""


def _ensure_feature_branch(
    db: Session, job_service: AgentJobService, job
) -> "AgentJob":
    # Fortune-500: isolated branch, never work directly on main
    branch = f"agent/job-{job.id}-{_slugify(job.title or 'task')}"
    if (job.branch_name or "").strip():
        b = job.branch_name.strip()
        if is_mainish(b):
            raise RuntimeError("Refusing: job branch would be main/master; re-queue job.")
        _run(["git", "checkout", b], shell=False)
        return job_service.repo.get(db, job.id) or job
    if (job.status or "") not in ("approved", "in_progress"):
        raise RuntimeError(f"Expected job status=approved|in_progress, got {job.status!r}")
    # Prefer creating the feature branch from main when available
    for candidate in ("main", "master"):
        sw = _run(["git", "switch", candidate], shell=False, check=False)
        if sw.returncode == 0:
            break
    _run(["git", "checkout", "-b", branch], shell=False)
    return job_service.repo.update(
        db,
        job,
        status="in_progress",
        branch_name=branch,
        started_at=datetime.utcnow(),
        error_message=None,
    )


def _record_baseline(db: Session, job_service: AgentJobService, job) -> "AgentJob":
    pl = dict(job.payload_json or {})
    h = _git_rev()
    if not pl.get("aider_baseline_for_diff"):
        pl["aider_baseline_for_diff"] = h
    pl["aider_baseline_head"] = h
    pl["autonomous_aider"] = True
    return job_service.repo.update(db, job, payload_json=pl)


def _notify_approval(
    db: Session, job_service: AgentJobService, job, text: str, *, only_once_key: str = "autonomy_notify_approval"
) -> None:
    if (os.getenv("DEV_WORKER_TELEGRAM_NOTIFY", "true") or "true").strip().lower() not in {
        "1", "true", "yes", "y", "on",
    }:
        return
    chat = (getattr(job, "telegram_chat_id", None) or "").strip() or str(
        (dict(job.payload_json or {}).get("telegram_chat_id") or ""))
    if not chat or not (text or "").strip():
        return
    p = dict(job.payload_json or {})
    if p.get(only_once_key) is True:
        return
    if send_telegram_message(
        chat,
        text[:3900],
        max_len=3900,
        reply_markup=approval_inline_markup(job.id),
    ):
        p[only_once_key] = True
        j = job_service.repo.get(db, job.id) or job
        job_service.repo.update(db, j, payload_json=p)


def revert_aider_changes_on_branch(job) -> tuple[bool, str]:
    _aider_cwd.set(_work_root_for_dev_job_payload(job))
    if not _git_worktree():
        return False, "Not a git work tree; cannot revert."
    br = (getattr(job, "branch_name", None) or "").strip()
    if not br:
        return False, "No branch on job."
    try:
        _run(["git", "checkout", br], shell=False, check=True)
    except subprocess.CalledProcessError as e:
        return False, f"checkout: {e.stderr or str(e)}"[:2000]
    pl = job.payload_json or {}
    bl = (pl.get("aider_baseline_head") or "").strip()
    if bl:
        try:
            _run(["git", "reset", "--hard", bl], shell=False, check=True)
        except subprocess.CalledProcessError as e:
            return False, f"git reset: {e.stderr or str(e)}"[:2000]
        return True, f"Reverted to {bl[:8]} on {br}."
    try:
        _run(["git", "restore", "."], shell=False, check=True)
    except subprocess.CalledProcessError as e:
        return False, f"git restore: {e.stderr or str(e)}"[:2000]
    return True, "Reverted working tree (no baseline; used git restore)."


def process_approved_to_commit(
    db: Session, job, job_service: AgentJobService, *, from_worker: bool = True
) -> "AgentJob":
    """`approved_to_commit` -> commit (if needed) and completed."""
    _aider_cwd.set(_work_root_for_dev_job_payload(job))
    if (getattr(job, "worker_type", None) or "") != "dev_executor":
        return job
    if (job.status or "") != "approved_to_commit":
        return job
    tstat = (getattr(job, "tests_status", None) or "unknown")
    ovr = getattr(job, "override_failed_tests", None) or False
    if (tstat or "") == "failed" and not ovr:
        job_service.mark_failed(
            db, job, "Refusing commit: tests failed. Fix tests or re-run, or use approve despite on Telegram first."
        )
        return job
    apby = (getattr(job, "approved_by_user_id", None) or getattr(job, "user_id", None) or "").strip()
    if not apby:
        job_service.mark_failed(
            db, job, "Commit guard: missing approved_by_user_id. Re-approve the job in Telegram."
        )
        return job
    br0 = (getattr(job, "branch_name", None) or "").strip()
    if br0 in {"main", "master"} or is_mainish(br0):
        job_service.mark_failed(
            db, job, "Commit guard: cannot commit on main/master branch from autonomous pipeline."
        )
        return job
    if not _git_worktree():
        job_service.mark_failed(
            db, job, "Cannot commit: not a git work tree on the worker host."
        )
        return job
    br = (getattr(job, "branch_name", None) or "").strip()
    if not br:
        job_service.mark_failed(db, job, "No feature branch; cannot commit.")
        return job
    _run(["git", "checkout", br], shell=False, check=True)
    plj = dict(job.payload_json or {})
    blf = (plj.get("aider_baseline_for_diff") or plj.get("aider_baseline_head") or "").strip()
    if blf:
        sec2 = scan_combined_diff_for_secrets(_jroot(), blf)
    else:
        from app.services.secret_scan import scan_git_diff_for_secrets
        sec2 = [x for x in scan_git_diff_for_secrets(_jroot()) if not str(x).startswith("git ")]
    if sec2:
        job_service.mark_failed(
            db, job, f"Commit guard: secret scan before commit: {sec2[:2000]}"
        )
        return job
    baseline = str((plj.get("aider_baseline_head") or "")).strip()
    porcelain = _git_porcelain()
    if porcelain.strip():
        _run(["git", "add", "-A"], shell=False, check=True)
        safe = re.sub(r"[\r\n\"]", " ", (job.title or "task")[:100])
        risk = getattr(job, "risk_level", None) or (dict(job.payload_json or {}).get("policy", {}) or {}).get("risk", "normal")
        tstat = (getattr(job, "tests_status", None) or "unknown")
        tnote = tstat
        if (tstat or "") == "failed" and (getattr(job, "override_failed_tests", None) or False):
            tnote = f"{tstat} (overridden; operator accepted risk on Telegram)"
        body = (
            f"Risk: {risk}\nTests: {tnote}\nApproved via dev pipeline (autonomous aider).\n"
            f"User id: {getattr(job, 'user_id', '')}\nAudit: job.approved_to_commit, job.committed"
        )
        cr = _run(
            [
                "git",
                "commit",
                "-m",
                f"Job #{job.id}: {safe}".strip(),
                "-m",
                body[:5000],
            ],
            shell=False,
            check=False,
        )
        if cr.returncode != 0 and "nothing to commit" in (cr.stdout or cr.stderr or "").casefold():
            if baseline and _git_rev() == baseline:
                job_service.mark_failed(
                    db, job, "Nothing to commit: working tree and HEAD unchanged after add."
                )
                return job
    else:
        if not baseline or _git_rev() == baseline:
            job_service.mark_failed(
                db, job, "Nothing to commit: clean tree and no new commits on feature branch."
            )
            return job
    sha = _git_rev()
    if from_worker and _env_flag("DEV_AUTO_PUSH", "false") and br not in (
        "main",
        "master",
        "HEAD",
    ):
        _run(
            ["git", "push", "-u", "origin", br],
            shell=False,
            check=False,
        )
    if from_worker and _env_flag("DEV_AUTO_CREATE_PR", "false"):
        _run(
            ["gh", "pr", "create", "--fill", "--head", br],
            shell=False,
            check=False,
        )
    msg = f"Committed (job {job.id}).\n\nSHA: {sha}\n"
    out = job_service.mark_completed(
        db,
        job,
        ((job.result or "") + "\n\n" + msg)[:12_000],
        commit_sha=sha,
    )
    audit(
        db,
        event_type="job.committed",
        actor="worker",
        user_id=getattr(job, "user_id", None),
        job_id=job.id,
        message=f"commit {sha[:12] if sha else '?'}\n" + msg[:2000],
    )
    if (getattr(out, "telegram_chat_id", None) or (out.payload_json or {}).get("telegram_chat_id")):
        chat = (out.telegram_chat_id or "").strip() or str(
            (out.payload_json or {}).get("telegram_chat_id") or ""
        )
        if (os.getenv("DEV_WORKER_TELEGRAM_NOTIFY", "true") or "true").strip().lower() in {
            "1", "true", "yes", "y", "on",
        } and chat:
            send_telegram_message(
                chat,
                f"Job #{out.id} completed and committed.\n\n" + msg[:2000],
            )
    return out


def run_aider_autonomous_for_approved_job(
    db: Session, job, job_service: AgentJobService, *, on_failure_revert: bool = True
) -> int:
    """Branch → aider (DEV_AGENT_COMMAND) → tests → waiting_approval or approved_to_commit / commit."""
    if (getattr(job, "worker_type", None) or "") != "dev_executor":
        return 1
    if (job.status or "") != "approved":
        print(
            f"autonomous: skip job {job.id} (status {job.status}, want approved).",
            flush=True,
        )
        return 0
    n_active = job_service.repo.count_dev_executor_in_statuses(db, list(_DEV_ACTIVE_STATUSES))
    max_n = int(get_settings().dev_agent_max_active_jobs)
    if n_active >= max_n:
        print(
            f"autonomous: at max in-flight dev jobs ({n_active} >= {max_n}), not starting {job.id}.",
            flush=True,
        )
        return 0
    wid = get_worker_id()
    if not job_service.repo.acquire_job_lock(db, job, wid, ttl_seconds=1800):
        fresh = db.get(AgentJob, job.id)
        lb = (getattr(fresh, "locked_by", None) or "") if fresh else "?"
        le = getattr(fresh, "lock_expires_at", None) if fresh else None
        print(
            f"autonomous: could not acquire lock for job {job.id} (other worker?). "
            f"locked_by={lb!r} lock_expires_at={le!r} this_worker={wid!r}",
            flush=True,
        )
        return 0
    art = ensure_job_artifact_dir(job.id)
    art_str = str(art)
    _aider_cwd.set(_work_root_for_dev_job_payload(job))
    if not _git_worktree():
        j0 = job_service.mark_failed(
            db, job, "Aider autonomous path needs a git work tree (clone the repo on the host worker).",
            failure_stage="pre_git",
            failure_artifact_dir=art_str,
        )
        notify_dev_job_failed_telegram(db, job_service, j0, "Not a git work tree on the worker host.")
        job_service.repo.release_job_lock(db, j0)
        return 1
    if not (os.getenv("DEV_AGENT_COMMAND") or "").strip():
        j0 = job_service.mark_failed(
            db, job, "Set DEV_AGENT_COMMAND (e.g. aider --yes --message-file {task_file})",
            failure_stage="config",
            failure_artifact_dir=art_str,
        )
        notify_dev_job_failed_telegram(db, job_service, j0, "DEV_AGENT_COMMAND is not set on the host.")
        job_service.repo.release_job_lock(db, j0)
        return 1
    j = job
    try:
        j = job_service.repo.get(db, job.id) or j
        j = job_service.repo.update(db, j, artifact_dir=art_str, failure_artifact_dir=None)
        pf = run_dev_preflight(Path(_jroot()))
        write_preflight_json(art, pf)
        if not pf.get("ok"):
            em = format_preflight_errors(pf)[:2000]
            jf = job_service.mark_failed(
                db, j, em, failure_stage="preflight", failure_artifact_dir=art_str, result=em
            )
            notify_dev_job_failed_telegram(db, job_service, jf, em)
            job_service.repo.release_job_lock(db, jf)
            return 1
        write_heartbeat(
            current_job_id=job.id,
            current_stage="preflight_ok",
            active_jobs=n_active,
        )
        try:
            ensure_clean_worktree(_jroot())
        except RuntimeError as exc:
            j0 = job_service.mark_failed(
                db, j, str(exc)[:2000], failure_stage="dirty_worktree", failure_artifact_dir=art_str
            )
            notify_dev_job_failed_telegram(db, job_service, j0, str(exc)[:2000])
            job_service.repo.release_job_lock(db, j0)
            return 1
        j = _ensure_feature_branch(db, job_service, j)
        j = _record_baseline(db, job_service, j)
        j = job_service.repo.update(
            db,
            j,
            status="agent_running",
            error_message=None,
            cursor_task_path=str(AGENT_TASKS_DIR / f"dev_job_{j.id}.md"),
        )
        uid = (j.user_id or None)
        audit(
            db,
            event_type="job.agent_started",
            actor=wid,
            user_id=uid,
            job_id=j.id,
            message=f"Aider/CLI run started for job {j.id} (worker {wid})",
        )
        j = job_service.repo.get(db, j.id) or j
        nrev = int((dict(j.payload_json or {}).get("revision_count", 0) or 0))
        if nrev > 0:
            task_path = AGENT_TASKS_DIR / f"dev_job_{j.id}_revision_{nrev}.md"
            if not task_path.is_file():
                jf = job_service.mark_failed(
                    db, j, f"Missing revision task file {task_path.name}",
                    failure_stage="missing_revision",
                    failure_artifact_dir=art_str,
                )
                notify_dev_job_failed_telegram(
                    db, job_service, jf, f"Expected {task_path.name} (request-changes follow-up).",
                )
                job_service.repo.release_job_lock(db, jf)
                return 1
        else:
            task_path = write_aider_task_file(j)
        copy_task_to_artifacts(task_path, art)
        write_heartbeat(
            current_job_id=job.id,
            current_stage="agent_running",
            active_jobs=job_service.repo.count_dev_executor_in_statuses(
                db, list(_DEV_ACTIVE_STATUSES)
            ),
        )
        try:
            rc = run_aider_to_artifact_logs(art, task_path)
            if rc != 0:
                err_tail = (art / "agent_stderr.log").read_text(encoding="utf-8", errors="replace")[-4000:]
                raise RuntimeError(
                    f"Agent exited {rc}. See agent_stderr.log. Last stderr:\n{err_tail[:2000]}"
                )
        except subprocess.TimeoutExpired:
            oops = f"Agent timed out after {_agent_timeout_sec()}s (see agent logs in {art_str})."
            jf = job_service.mark_failed(
                db, j, oops, failure_stage="agent_timeout", failure_artifact_dir=art_str
            )
            notify_dev_job_failed_telegram(db, job_service, jf, oops)
            job_service.repo.release_job_lock(db, jf)
            return 1
        except RuntimeError as exc:
            jf = job_service.repo.get(db, j.id) or j
            if on_failure_revert and (jf.branch_name or "").strip():
                revert_aider_changes_on_branch(jf)
            em = str(exc)[:4000]
            jf2 = job_service.mark_failed(
                db, jf, f"Aider/command failed: {em}", failure_stage="agent", failure_artifact_dir=art_str
            )
            notify_dev_job_failed_telegram(
                db, job_service, jf2, f"Aider/command failed: {em[:2000]}"
            )
            audit(
                db,
                event_type="job.failed",
                actor="agent",
                user_id=uid,
                job_id=jf.id,
                message=em[:2000],
            )
            job_service.repo.release_job_lock(db, jf2)
            return 1

        j = job_service.repo.get(db, j.id) or j
        j = job_service.repo.update(db, j, status="changes_ready")
        audit(
            db, event_type="job.agent_finished", actor="agent", user_id=uid, job_id=j.id, message="Aider/CLI process exited 0"
        )

        audit(db, event_type="job.tests_started", actor="worker", user_id=uid, job_id=j.id, message="Running tests")
        test_out = _run_tests_capture_artifacts(art)
        test_failed = "Tests/checks failed" in test_out
        tst = "failed" if test_failed else "passed"
        if not (test_out or "").strip().startswith("Tests/checks skipped"):
            j = job_service.repo.update(
                db,
                j,
                tests_status=tst,
                tests_output=(test_out or "")[:20_000],
            )
        else:
            j = job_service.repo.update(db, j, tests_status="skipped", tests_output=test_out)

        if test_failed:
            audit(
                db, event_type="job.tests_failed", actor="worker", user_id=uid, job_id=j.id, message=test_out[:2000]
            )
        else:
            audit(
                db, event_type="job.tests_passed", actor="worker", user_id=uid, job_id=j.id, message="Tests OK"
            )
        if _env_flag("DEV_AIDER_TEST_FAILURE_IS_FATAL", "true") and test_failed:
            oops = f"Tests failed:\n{test_out[:2500]}"
            j = job_service.repo.get(db, j.id) or j
            summary_fail = (
                f"**Tests did not pass.** The feature branch is left as-is (not reverted) so you can review.\n\n"
                f"• Type `approve despite failed tests` to move to approval and commit on your own review.\n"
                f"• Or ask to retry job #{j.id} after fixes.\n\n"
                f"{(test_out or '')[:8000]}"
            )[:12_000]
            jf = job_service.mark_failed(
                db,
                j,
                oops,
                result=summary_fail,
                tests_status="failed",
                tests_output=(test_out or "")[:20_000],
                failure_stage="tests",
                failure_artifact_dir=art_str,
            )
            notify_dev_job_failed_telegram(
                db, job_service, jf, oops,
            )
            audit(
                db,
                event_type="job.failed",
                actor="system",
                user_id=uid,
                job_id=j.id,
                message="Tests did not pass; not requesting approval (reverts disabled for this path)",
            )
            job_service.repo.release_job_lock(db, jf)
            return 1

        bl = (dict(j.payload_json or {}).get("aider_baseline_head") or "").strip()
        if bl:
            sec = scan_combined_diff_for_secrets(_jroot(), bl)
        else:
            from app.services.secret_scan import scan_git_diff_for_secrets

            sec = [x for x in scan_git_diff_for_secrets(_jroot()) if not str(x).startswith("git ")]
        if sec:
            msg = f"Secret scan: possible sensitive content in diff: {sec}"
            jf = job_service.mark_failed(
                db, j, msg[:2000], failure_stage="secret_scan", failure_artifact_dir=art_str
            )
            notify_dev_job_failed_telegram(
                db, job_service, jf, "Secret scan flagged possible sensitive content in the diff.",
            )
            audit(
                db, event_type="job.blocked_by_policy", actor="system", user_id=uid, job_id=j.id, message=msg, metadata={"findings": sec}
            )
            job_service.repo.release_job_lock(db, jf)
            return 1

        ttxt = (task_path.read_text(encoding="utf-8", errors="replace")[:2000] if task_path.is_file() else "(no file)")
        cursorish = f"(Aider/CLI run — see git + tests.)\n\n{ttxt}"
        final = build_final_worker_review(j, cursorish, test_out)
        rpath = review_path_for_job(j.id)
        rpath.write_text(final, encoding="utf-8")
        try:
            copy_review_to_artifacts(rpath, art)
            write_diff_artifacts(art, Path(_jroot()))
        except OSError:
            pass
        summary = f"Autonomous run — {rpath.name}\n\n" + final[:10_000]
        if len(summary) > 12_000:
            summary = summary[:12_000] + "…"
        j = job_service.repo.get(db, j.id) or j

        if _env_flag("DEV_APPROVAL_REQUIRED", "true"):
            j = job_service.repo.update(
                db,
                j,
                status="waiting_approval",
                result=summary,
                result_file=str(rpath),
                error_message=None,
            )
            audit(
                db, event_type="job.waiting_approval", actor="system", user_id=uid, job_id=j.id, message="Waiting for user approval"
            )
            j = job_service.repo.get(db, j.id) or j
            persist_job_waiting_approval(
                db,
                j,
                ctx=None,
                resume_kind="host_worker_poll",
                original_action="autonomous_dev_review",
                risk=(getattr(j, "risk_level", None) or "normal"),
            )
            _notify_approval(db, job_service, j, format_approval_message(j, final))
        else:
            j = job_service.repo.update(
                db,
                j,
                status="approved_to_commit",
                result=summary,
                result_file=str(rpath),
                approved_by_user_id=(j.user_id or None),
            )
            if _env_flag("DEV_AUTO_COMMIT", "false"):
                _notify_approval(
                    db,
                    job_service,
                    j,
                    f"Job #{j.id} is pre-approved. Reply `approve` to run the final commit, "
                    f"or the worker will pick it up (status approved_to_commit).",
                    only_once_key="autonomy_notify_precommit",
                )
            else:
                j2p = process_approved_to_commit(db, j, job_service, from_worker=True)
                j = job_service.repo.get(db, j2p.id) or j2p
        j = job_service.repo.get(db, j.id) or j
        job_service.repo.release_job_lock(db, j)
        return 0
    except (OSError, RuntimeError) as exc:
        j2 = job_service.repo.get(db, j.id) or j
        if on_failure_revert and getattr(j2, "branch_name", None):
            try:
                revert_aider_changes_on_branch(j2)
            except (OSError, subprocess.CalledProcessError):
                pass
        j2 = job_service.mark_failed(
            db, j2, f"{type(exc).__name__}: {str(exc)[:3500]}", failure_stage="autonomous", failure_artifact_dir=art_str
        )
        notify_dev_job_failed_telegram(
            db, job_service, j2, (j2.error_message or str(exc))[:2000]
        )
        job_service.repo.release_job_lock(db, j2)
        return 1
    except subprocess.CalledProcessError as exc:
        j2 = job_service.repo.get(db, j.id) or j
        if on_failure_revert and getattr(j2, "branch_name", None):
            try:
                revert_aider_changes_on_branch(j2)
            except (OSError, subprocess.CalledProcessError):
                pass
        err = (exc.stderr or exc.stdout or str(exc))[:3500]
        j2 = job_service.mark_failed(
            db, j2, f"Git or subprocess: {err}", failure_stage="subprocess", failure_artifact_dir=art_str
        )
        notify_dev_job_failed_telegram(db, job_service, j2, (j2.error_message)[:2000] if j2.error_message else err)
        job_service.repo.release_job_lock(db, j2)
        return 1
    finally:
        write_heartbeat(current_job_id=None, current_stage="idle", active_jobs=None)
