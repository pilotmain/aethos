"""One-shot React app scaffolding (argv-only subprocesses; never shell=True)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.status_monitor import TaskStatus, get_status_monitor

_APP_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")


def create_react_app(
    app_name: str,
    workspace_root: str,
    *,
    owner_user_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a React app with ``npx create-react-app``, run ``npm install``, best-effort ``npm start``.

    Uses :envvar:`NEXA_TASK_TIMEOUT_SECONDS` (default 300s) for long steps when set on Settings.
    Optional progress tracking when ``owner_user_id`` is set and ``nexa_status_auto_report`` is true.
    """
    name = (app_name or "").strip()
    s = get_settings()
    timeout_sec = max(60, int(getattr(s, "nexa_task_timeout_seconds", 300)))

    if not name or not _APP_NAME_RE.fullmatch(name):
        return {
            "success": False,
            "steps": [{"step": "validate", "success": False, "output": "Invalid app name"}],
            "app_url": "http://localhost:3000",
            "app_path": "",
        }
    root = Path(workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    app_path = root / name
    results: list[dict[str, Any]] = []

    task_id: str | None = None
    mon = get_status_monitor()
    uid = (owner_user_id or "").strip()
    if uid and bool(getattr(s, "nexa_status_auto_report", True)):
        try:
            task_id = mon.start_long_task(uid, f"React app `{name}`", "npx/npm")
            mon.update_task_progress(
                task_id,
                10,
                TaskStatus.IN_PROGRESS,
                detail="Creating React app structure…",
            )
        except RuntimeError as exc:
            return {
                "success": False,
                "steps": [{"step": "schedule", "success": False, "output": str(exc)}],
                "app_url": "http://localhost:3000",
                "app_path": str(app_path),
            }

    def run_step(argv: list[str], cwd: Path, description: str, *, timeout: int) -> None:
        try:
            r = subprocess.run(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            ok = r.returncode == 0
            out = ((r.stdout or "")[:800] or (r.stderr or "")[:800]).strip()
            results.append({"step": description, "success": ok, "output": out or "(no output)"})
        except subprocess.TimeoutExpired:
            results.append({"step": description, "success": False, "output": "Timeout"})
        except (OSError, FileNotFoundError) as e:
            results.append({"step": description, "success": False, "output": str(e)[:500]})

    def bump(pct: int, detail: str) -> None:
        if task_id:
            mon.update_task_progress(task_id, pct, TaskStatus.IN_PROGRESS, detail=detail)

    npx = shutil.which("npx") or "npx"
    run_step(
        [npx, "--yes", "create-react-app", name],
        root,
        "Creating React app",
        timeout=timeout_sec,
    )
    bump(40, "Creating React app…")
    if not results or not results[-1].get("success"):
        if task_id:
            mon.complete_task(task_id, ok=False, detail="create-react-app failed")
        return {
            "success": False,
            "steps": results,
            "app_url": "http://localhost:3000",
            "app_path": str(app_path),
        }

    bump(55, "Installing dependencies…")
    npm = shutil.which("npm") or "npm"
    run_step([npm, "install"], app_path, "Installing dependencies", timeout=timeout_sec)
    bump(75, "Starting dev server…")

    try:
        subprocess.Popen(
            [npm, "start"],
            cwd=str(app_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        results.append(
            {"step": "Starting dev server", "success": True, "output": "Started in background"}
        )
    except (OSError, FileNotFoundError) as e:
        results.append(
            {"step": "Starting dev server", "success": False, "output": str(e)[:400]}
        )

    ok_all = all(bool(x.get("success")) for x in results)
    if task_id:
        mon.complete_task(task_id, ok=ok_all, detail="React scaffold finished")

    return {
        "success": ok_all,
        "steps": results,
        "app_url": "http://localhost:3000",
        "app_path": str(app_path),
    }


def parse_react_app_intent(text: str) -> dict[str, Any] | None:
    """Parse React app creation intent."""
    if not text or not isinstance(text, str):
        return None
    low = text.strip().splitlines()[0].strip().lower()
    patterns = [
        r"create\s+(?:a|an)?\s*react\s+app\s+called\s+(\w+)",
        r"make\s+(?:a|an)?\s*react\s+app\s+(\w+)",
        r"build\s+(?:a|an)?\s*react\s+app\s+(\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, low)
        if match:
            return {"intent": "react_app", "app_name": match.group(1)}
    return None
