from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / ".runtime"
DEFAULT_CODEX_PATH = Path("/Applications/Codex.app/Contents/Resources/codex")


def _pid_status(path: Path) -> dict:
    if not path.is_file():
        return {"running": False, "pid": None}
    pid_text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not pid_text.isdigit():
        return {"running": False, "pid": None}
    pid = int(pid_text)
    try:
        os.kill(pid, 0)
        return {"running": True, "pid": pid}
    except OSError:
        return {"running": False, "pid": pid}


def _run(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


def get_system_health() -> dict:
    settings = get_settings()
    api_proc = _pid_status(RUNTIME_DIR / "api.pid")
    bot_proc = _pid_status(RUNTIME_DIR / "bot.pid")
    codex_cli_exists = DEFAULT_CODEX_PATH.is_file()
    codex_login = _run([str(DEFAULT_CODEX_PATH), "login", "status"]) if codex_cli_exists else {
        "ok": False,
        "returncode": None,
        "stdout": "",
        "stderr": "Codex CLI not found",
    }
    return {
        "env_file_present": (ROOT / ".env").is_file(),
        "venv_present": (ROOT / ".venv/bin/python").is_file(),
        "api_process": api_proc,
        "bot_process": bot_proc,
        "runtime_dir": str(RUNTIME_DIR),
        "codex_cli_path": str(DEFAULT_CODEX_PATH),
        "codex_cli_exists": codex_cli_exists,
        "codex_login_ok": codex_login["ok"],
        "codex_login_stdout": codex_login["stdout"],
        "codex_login_stderr": codex_login["stderr"],
        "is_git_repo": (ROOT / ".git").exists(),
        "operator_settings": {
            "poll_seconds": settings.operator_poll_seconds,
            "auto_run_local_tools": settings.operator_auto_run_local_tools,
            "auto_run_dev_executor": settings.operator_auto_run_dev_executor,
            "dev_executor_on_host": settings.dev_executor_on_host,
            "auto_approve_queued_dev_jobs": settings.operator_auto_approve_queued_dev_jobs,
            "auto_approve_review": settings.operator_auto_approve_review,
            "auto_approve_commit_safe": settings.operator_auto_approve_commit_safe,
            "auto_approve_all_commits": settings.operator_auto_approve_all_commits,
        },
    }
