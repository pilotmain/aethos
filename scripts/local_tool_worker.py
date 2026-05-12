# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Process queued local-tool jobs: approved git/pytest/file writes only.

Run:  python scripts/local_tool_worker.py
Loop:  while true; do python scripts/local_tool_worker.py; sleep 20; done
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment, misc]
if load_dotenv and (PROJECT_ROOT / ".env").is_file():
    load_dotenv(PROJECT_ROOT / ".env", override=False)

BLOCKED_PATH_PATTERNS = (
    ".env",
    ".ssh",
    "credentials",
    "secrets",
    ".venv",
    "node_modules",
)


def run(
    cmd: list[str], timeout: int = 120, *, env: dict | None = None, cwd: Path | None = None
) -> str:
    result = subprocess.run(  # noqa: S603 — argv is fixed per handler
        cmd,
        cwd=cwd or PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    pieces: list[str] = []
    if result.stdout:
        pieces.append(result.stdout)
    if result.stderr:
        pieces.append("STDERR:\n" + result.stderr)
    out = "\n".join(pieces) if pieces else ""
    if result.returncode not in (0,):
        if cmd[:3] == ["python", "-m", "pytest"] and result.returncode == 5:
            return (out or "")[:6000] + "\n(pytest: no tests collected, exit 5 — OK)\n"
        err_msg = f"(exit {result.returncode})\n" + (out or "")[:3800]
        raise RuntimeError(err_msg)
    return (out or "")[:6000]


def get_next_action(db):
    from app.repositories.agent_job_repo import AgentJobRepository

    return AgentJobRepository().get_next_for_worker(db, "local_tool")


def handle_review_last_change(action) -> str:
    _ = action
    try:
        diff_names = run(["git", "diff", "--name-only", "HEAD~1..HEAD"], timeout=30)
    except (RuntimeError, FileNotFoundError) as e:
        return f"git not available or not enough history: {e!s}"[:5000]
    try:
        diff_stat = run(["git", "diff", "--stat", "HEAD~1..HEAD"], timeout=30)
    except RuntimeError as e:
        diff_stat = str(e)[:2000]
    return (
        "Latest change summary:\n\n"
        f"Files changed:\n{diff_names}\n\n"
        f"Diff stat:\n{diff_stat}\n\n"
        "Open Cursor and ask it to review these files if deeper review is needed."
    )


def handle_run_tests(_action) -> str:
    return run(["python", "-m", "pytest"], timeout=300)


def handle_create_cursor_task(action) -> str:
    # Legacy: new Telegram /dev create-cursor-task jobs use dev_executor + dev_agent_executor.py
    # instead. Kept for older queued local_tool jobs and tests.
    task_dir = PROJECT_ROOT / ".agent_tasks"
    task_dir.mkdir(exist_ok=True)
    if not (action.instruction or "").strip():
        raise ValueError("create-cursor-task needs an instruction")

    action_id = action.id
    if action_id is None:
        action_id = f"tmp-{uuid.uuid4().hex[:8]}"
    task_file = task_dir / f"cursor_task_{action_id}.md"
    done_file = task_dir / f"cursor_task_{action_id}.done.md"
    body = f"""# Cursor task #{action_id}

## User instruction

{action.instruction}

## Project

Nexa

## Rules

- Make the smallest safe change.
- Do not read or modify `.env`.
- Do not read secrets or credentials.
- Do not run destructive commands.
- Do not push or merge.
- Preserve existing behavior unless the task explicitly changes it.
- Add or update tests if needed.
- Run tests before finalizing.

## Deliverables

- Summary of changes
- Files changed
- Test results
- Any follow-up needed

## Completion handoff

When you finish, write a short completion note to:
{done_file}
"""
    task_file.write_text(body, encoding="utf-8")
    if (os.getenv("LOCAL_WORKER_OPEN_CURSOR", "false") or "").lower() in (
        "1",
        "true",
        "yes",
    ) and sys.platform == "darwin":
        try:
            subprocess.run(  # noqa: S603 — fixed argv
                ["open", "-a", "Cursor", str(task_file)],
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return (
        f"Cursor task file created:\n{task_file}\n"
        f"Completion marker:\n{done_file}\n\n"
        "Open this file in Cursor and ask the Cursor agent to implement it."
    )


def handle_prepare_fix(action) -> str:
    if not (action.instruction or "").strip():
        raise ValueError("prepare-fix needs an instruction")
    task_dir = PROJECT_ROOT / ".agent_tasks"
    task_dir.mkdir(exist_ok=True)
    try:
        recent_status = run(["git", "status", "--short"], timeout=20)
    except (RuntimeError, FileNotFoundError) as e:
        recent_status = f"[git unavailable: {e!s}]"
    action_id = action.id or f"tmp-{uuid.uuid4().hex[:8]}"
    task_file = task_dir / f"fix_task_{action_id}.md"
    task_file.write_text(
        f"""# Fix task #{action_id}

## Fix request

{action.instruction}

## Current git status

{recent_status or "[clean]"}

## Instructions for Cursor

Act as a senior developer.
1. Inspect only project files.
2. Do not open `.env`, secrets, credentials, or SSH files.
3. Identify the smallest safe fix.
4. Implement the fix.
5. Run tests.
6. Summarize what changed.

## Safety

No destructive commands. No pushing. No merging. No secret access.
""",
        encoding="utf-8",
    )
    if (os.getenv("LOCAL_WORKER_OPEN_CURSOR", "false") or "").lower() in (
        "1",
        "true",
        "yes",
    ) and sys.platform == "darwin":
        try:
            subprocess.run(  # noqa: S603
                ["open", "-a", "Cursor", str(task_file)],
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return f"Fix task prepared for Cursor:\n{task_file}"


def handle_summarize_project(_action) -> str:
    try:
        files = run(["git", "ls-files"], timeout=60)
    except (RuntimeError, FileNotFoundError) as e:
        collected: list[str] = []
        for root_name in ("app", "scripts", "tests"):
            root_path = PROJECT_ROOT / root_name
            if not root_path.exists():
                continue
            for path in root_path.rglob("*"):
                if path.is_file():
                    collected.append(str(path.relative_to(PROJECT_ROOT)))
        if not collected:
            return f"git ls-files failed: {e!s}\nNo safe project files were found."[:5000]
        files = "\n".join(collected)
    allowed: list[str] = []
    for line in files.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p in line for p in BLOCKED_PATH_PATTERNS):
            continue
        if line.startswith(("app/", "scripts/", "tests/")):
            allowed.append(line)
    summary = "\n".join(allowed[:300])
    return f"Project file summary (safe paths only):\n\n{summary or '[none matched]'}"


def handle_create_idea_repo(action) -> str:
    from app.core.db import SessionLocal, ensure_schema
    from app.services.project_registry import get_project_by_key

    pjson = dict(action.payload_json or {})
    k = (pjson.get("project_key") or "").strip().lower()
    target = (pjson.get("target_path") or "").strip()
    if not k or not target:
        raise ValueError("create-idea-repo needs project_key and target_path in payload")
    tpath = Path(target).expanduser().resolve()
    tpath.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=str(tpath), timeout=60)
    run(["git", "config", "user.email", "nexa@local.invalid"], cwd=str(tpath), timeout=15)
    run(["git", "config", "user.name", "Nexa Idea Project"], cwd=str(tpath), timeout=15)
    (tpath / ".gitignore").write_text(
        ".env\n.venv\nnode_modules\ndist\n", encoding="utf-8"
    )
    (tpath / "README.md").write_text(
        "# Idea project (Nexa)\n\nLocal scaffold — add your app here.\n",
        encoding="utf-8",
    )
    run(["git", "add", ".gitignore", "README.md"], cwd=str(tpath), timeout=20)
    run(
        ["git", "commit", "-m", "Nexa: init repo for idea project"],
        cwd=str(tpath),
        timeout=60,
    )
    ensure_schema()
    db = SessionLocal()
    try:
        proj = get_project_by_key(db, k)
        if not proj:
            return f"Repo created at {tpath} but no Project `{k}` in DB; link manually."
        proj.repo_path = str(tpath)
        db.add(proj)
        db.commit()
    finally:
        db.close()
    return (
        f"Created git repo and linked project `{k}` to:\n{tpath}\n"
        f"You can add a remote (e.g. GitHub) from your machine; Nexa did not call any cloud API."
    )[:6000]


def handle_dev_workspace_scaffold(action) -> str:
    from app.core.config import get_settings
    from app.core.db import SessionLocal, ensure_schema
    from app.services.project_registry import create_project_mvp, get_project_by_key

    s = get_settings()
    pjson = dict(action.payload_json or {})
    k = (pjson.get("project_key") or "").strip().lower()
    target = (pjson.get("target_path") or "").strip()
    if not k or not target:
        raise ValueError("dev-workspace-scaffold needs project_key and target_path in payload")
    tpath = Path(target).expanduser().resolve()
    if tpath.exists() and tpath.is_dir() and any(tpath.iterdir()):
        raise ValueError(f"Path already exists and is not empty: {tpath}")
    tpath.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=str(tpath), timeout=60)
    run(["git", "config", "user.email", "nexa@local.invalid"], cwd=str(tpath), timeout=15)
    run(["git", "config", "user.name", "Nexa"], cwd=str(tpath), timeout=15)
    (tpath / ".gitignore").write_text(
        ".env\n.venv\nnode_modules\ndist\n", encoding="utf-8"
    )
    (tpath / "README.md").write_text(
        f"# {k} (Nexa)\n\nScaffolded by Nexa — add your app here.\n",
        encoding="utf-8",
    )
    run(["git", "add", ".gitignore", "README.md"], cwd=str(tpath), timeout=20)
    run(
        ["git", "commit", "-m", "Nexa: init workspace project"],
        cwd=str(tpath),
        timeout=60,
    )
    ensure_schema()
    db = SessionLocal()
    try:
        if get_project_by_key(db, k):
            return (
                f"Scaffolded repo at {tpath}, but project `{k}` already exists in the DB. "
                f"Link it manually with `/project add` if needed."
            )[:6000]
        create_project_mvp(
            db,
            key=k,
            display_name=k.replace("-", " ").title(),
            provider_key="local",
            repo_path=str(tpath),
        )
    finally:
        db.close()
    return (
        f"Created **{k}** at:\n`{tpath}`\n\n"
        f"Default dev tool/mode: `{s.nexa_default_dev_tool}` / `{s.nexa_default_dev_mode}`\n"
        f"Set with `/project set-tool` and `/project set-mode` as needed."
    )[:6000]


def process_action(action) -> str:
    ct = (action.command_type or "").lower()
    if ct == "host-executor":
        from app.services.host_executor import execute_host_executor_job

        return execute_host_executor_job(action)
    if ct == "create-idea-repo":
        return handle_create_idea_repo(action)
    if ct == "dev-workspace-scaffold":
        return handle_dev_workspace_scaffold(action)
    if ct == "review-last-change":
        return handle_review_last_change(action)
    if ct == "run-tests":
        return handle_run_tests(action)
    if ct == "create-cursor-task":
        return handle_create_cursor_task(action)
    if ct == "prepare-fix":
        return handle_prepare_fix(action)
    if ct == "summarize-project":
        return handle_summarize_project(action)
    raise ValueError(f"Unsupported command type: {action.command_type!r}")


def main() -> int:
    from app.core.db import SessionLocal, ensure_schema  # noqa: F401: ensure_schema registers models
    from app.services.agent_job_service import AgentJobService

    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    try:
        action = get_next_action(db)
        if not action:
            print("No queued local-tool jobs.")
            return 0
        jobs.repo.mark_started(db, action)

        try:
            out = process_action(action)
        except Exception as e:  # noqa: BLE001
            em = f"{type(e).__name__}: {e!s}"[:4000]
            jobs.mark_failed(db, action, em)
            print("FAILED:", em, flush=True)
            return 1

        if (action.command_type or "").lower() == "create-cursor-task":
            task_path = ""
            done_path = ""
            prefix = "Cursor task file created:"
            if out.startswith(prefix):
                parts = out.splitlines()
                task_path = parts[1].strip() if len(parts) > 1 else ""
                done_idx = parts.index("Completion marker:") + 1 if "Completion marker:" in parts else -1
                if done_idx > 0 and len(parts) > done_idx:
                    done_path = parts[done_idx].strip()
            if task_path:
                payload = dict(action.payload_json or {})
                if done_path:
                    payload["handoff_marker_path"] = done_path
                jobs.repo.update(db, action, payload_json=payload)
                jobs.mark_waiting_for_cursor(db, action, task_path)
                print(out, flush=True)
                return 0

        jobs.mark_completed(db, action, out)
        print(out, flush=True)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
