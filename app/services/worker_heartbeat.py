"""Host worker heartbeat (JSON) for /dev health checks."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.services.handoff_paths import PROJECT_ROOT

RUNTIME_DIR = Path(PROJECT_ROOT) / ".runtime"
HEARTBEAT_PATH = RUNTIME_DIR / "dev_worker_heartbeat.json"


def write_heartbeat(
    *,
    current_job_id: int | None = None,
    current_stage: str | None = None,
    active_jobs: int | None = None,
    extra: dict | None = None,
) -> None:
    from app.services.worker_identity import get_worker_id

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    pr = str(PROJECT_ROOT)
    dtree = is_dirty_tree(pr) if git_on_path() else None
    payload: dict = {
        "status": "alive",
        "worker_id": get_worker_id(),
        "last_seen": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "current_job_id": current_job_id,
        "current_stage": current_stage,
        "active_jobs": active_jobs,
        "git_branch": current_branch(pr) if git_on_path() else None,
        "dirty_tree": dtree,
    }
    if extra:
        payload = {k: v for k, v in {**payload, **extra}.items() if v is not None}
    else:
        payload = {k: v for k, v in payload.items() if v is not None}
    HEARTBEAT_PATH.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )


def git_on_path() -> bool:
    return shutil.which("git") is not None


def read_heartbeat() -> dict | None:
    if not HEARTBEAT_PATH.is_file():
        return None
    try:
        return json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def aider_on_path() -> bool:
    return shutil.which("aider") is not None


def git_status_short(project_root: str) -> str:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        text=True,
        capture_output=True,
    )
    return (r.stdout or "").strip()


def is_dirty_tree(project_root: str) -> bool:
    return bool(git_status_short(project_root))


def current_branch(project_root: str) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_root,
        text=True,
        capture_output=True,
    )
    return (r.stdout or "").strip() if r.returncode == 0 else "?"


def _human_age_utc(iso: str) -> str:
    try:
        from datetime import datetime, timezone

        raw = (iso or "").strip()
        if not raw:
            return "unknown"
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        sec = max(0, int((now - dt).total_seconds()))
        if sec < 90:
            return f"{sec} seconds ago"
        if sec < 3600:
            return f"{sec // 60} minutes ago"
        return f"{sec // 3600}h ago"
    except (OSError, TypeError, ValueError):
        return "unknown"


def build_dev_health_report(project_root: str | None = None) -> str:
    pr = str(project_root or PROJECT_ROOT)
    hb = read_heartbeat() or {}
    st = (hb.get("status") or "—").strip()
    raw_seen = hb.get("last_seen")
    last_seen = str(raw_seen).strip() if raw_seen is not None else "—"
    cjid = hb.get("current_job_id")
    age = _human_age_utc(last_seen) if last_seen != "—" else "—"
    parts = [
        "/dev health",
        f"Dev worker: {st}",
        f"Last seen: {age} ({last_seen})" if last_seen != "—" else "Last seen: (no file)",
    ]
    if cjid is not None:
        parts.append(f"Current job: #{cjid}" if cjid else "Current job: —")
    else:
        parts.append("Current job: —")
    if shutil.which("git"):
        parts.append(f"Git branch (this checkout): {current_branch(pr)}")
        d = is_dirty_tree(pr)
        parts.append(f"Dirty tree: {'yes' if d else 'no'}")
    else:
        parts.append("git: not on PATH in this process")
    parts.append(f"Worker id (heartbeat): {hb.get('worker_id', '—')}")
    stg = hb.get("current_stage")
    if stg:
        parts.append(f"Current stage: {stg}")
    if hb.get("active_jobs") is not None:
        parts.append(f"Active dev jobs (pipeline, DB): {hb.get('active_jobs')}")
    parts.append(f"Aider: {'available' if aider_on_path() else 'not on PATH'}")
    from app.services.dev_preflight import run_dev_preflight

    pf = run_dev_preflight(Path(pr))
    icons = {True: "OK", False: "FAIL"}
    psum = "  ".join(
        f"{c.get('name', 'check')[:24]}: {icons.get(c.get('ok'), '?')}" for c in (pf.get("checks") or [])[:8]
    )
    parts.append(f"Preflight: {psum}")
    parts.append("Telegram notify: DEV_WORKER_TELEGRAM_NOTIFY; token from TELEGRAM_BOT_TOKEN.")
    parts.append("API keys: not shown here; keep them in host .env only.")
    return "\n".join(parts)
