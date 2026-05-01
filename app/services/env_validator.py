"""Static checks for environment combinations that often break the Nexa dev stack."""

from __future__ import annotations

import logging
import os
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.handoff_paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _dev_executor_on_host() -> bool:
    return _env_truthy("DEV_EXECUTOR_ON_HOST") or get_settings().dev_executor_on_host


def _parse_db_port(url: str) -> int | None:
    s = (url or "").strip()
    if s.lower().startswith("sqlite:"):
        return None
    u = urlparse(s)
    return u.port


def collect_env_validation_issues() -> list[str]:
    out: list[str] = []
    s = get_settings()
    de_host = _dev_executor_on_host()
    op_auto = s.operator_auto_run_dev_executor
    if de_host and op_auto:
        out.append(
            "Both DEV_EXECUTOR_ON_HOST and OPERATOR_AUTO_RUN_DEV_EXECUTOR are on — "
            "the API/operator and the host may both start the dev executor. "
            "Set OPERATOR_AUTO_RUN_DEV_EXECUTOR=false in Docker (or the API process) when the host runs the worker."
        )

    py_raw = (os.environ.get("DEV_EXECUTOR_PYTHON") or "").strip()
    if de_host and not py_raw:
        out.append("DEV_EXECUTOR_ON_HOST=1 but DEV_EXECUTOR_PYTHON is not set (host scripts may pick the wrong Python).")
    if py_raw and not Path(py_raw).is_file():
        out.append(f"DEV_EXECUTOR_PYTHON is set to a path that does not exist: {py_raw!r}.")

    if _env_truthy("DEV_AGENT_AUTO_RUN") and not (os.environ.get("DEV_AGENT_COMMAND") or "").strip():
        out.append("DEV_AGENT_AUTO_RUN is true but DEV_AGENT_COMMAND is empty (the host worker cannot run the agent CLI).")

    if _env_truthy("DEV_AUTO_PUSH"):
        if shutil.which("git") is None:
            out.append("DEV_AUTO_PUSH is true but `git` is not on PATH.")
        else:
            r = subprocess.run(
                ["git", "-C", str(PROJECT_ROOT), "remote"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode != 0 or not (r.stdout or "").strip():
                out.append("DEV_AUTO_PUSH is true but this repo has no remotes (or `git remote` failed).")

    wroot = (s.nexa_workspace_root or "").strip()
    if not wroot:
        out.append("NEXA_WORKSPACE_ROOT is empty.")
    else:
        wp = Path(wroot)
        if not wp.exists():
            out.append(
                f"NEXA_WORKSPACE_ROOT {wroot!r} does not exist. Create it or fix the path."
            )
        elif not wp.is_dir():
            out.append(
                f"NEXA_WORKSPACE_ROOT {wroot!r} is not a directory. "
                "Set it to the parent folder for Nexa project checkouts."
            )

    host_port = (os.environ.get("POSTGRES_HOST_PORT") or "").strip()
    dbp = _parse_db_port(s.database_url)
    if host_port and host_port.isdigit() and dbp is not None and dbp != int(host_port) and de_host:
        out.append(
            f"POSTGRES_HOST_PORT is {host_port} but DATABASE_URL port is {dbp} — "
            "the host dev executor and API must use the same published Postgres port."
        )

    if s.use_real_llm and not (s.anthropic_api_key or s.openai_api_key):
        out.append(
            "USE_REAL_LLM is true but no ANTHROPIC_API_KEY or OPENAI_API_KEY is set — model calls will fail at runtime."
        )

    return out


def format_env_validation_report() -> str:
    issues = collect_env_validation_issues()
    if not issues:
        return "Environment checks: no conflicts detected (basic static scan)."
    lines = [f"• {x}" for x in issues]
    return "Environment issues:\n" + "\n".join(lines)
