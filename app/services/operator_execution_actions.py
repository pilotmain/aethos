# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Gated write / deploy / verify actions for operator mode (Phase Next).

Every mutating path requires ``NEXA_OPERATOR_MODE``, ``NEXA_HOST_EXECUTOR_ENABLED``,
and explicit ``NEXA_OPERATOR_ALLOW_WRITE`` / ``NEXA_OPERATOR_ALLOW_DEPLOY`` flags.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, TypeVar

from app.core.config import get_settings
from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.git_tools import create_commit, rev_parse_head
from app.services.dev_runtime.workspace import validate_workspace_path

_log = logging.getLogger(__name__)

T = TypeVar("T")


def operator_diag_gate() -> tuple[bool, str]:
    """Gate for read-only workspace commands (tests) under operator mode."""
    s = get_settings()
    if not bool(getattr(s, "nexa_operator_mode", False)):
        return False, "operator_mode_disabled"
    return True, ""


def operator_action_gates(*, require_write: bool, require_deploy: bool) -> tuple[bool, str]:
    s = get_settings()
    if not bool(getattr(s, "nexa_operator_mode", False)):
        return False, "operator_mode_disabled"
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        return False, "host_executor_disabled"
    if require_write and not bool(getattr(s, "nexa_operator_allow_write", False)):
        return False, "operator_write_disabled"
    if require_deploy and not bool(getattr(s, "nexa_operator_allow_deploy", False)):
        return False, "operator_deploy_disabled"
    return True, ""


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    delays_sec: tuple[int, ...] = (10, 30, 60),
) -> tuple[T | None, list[str]]:
    """
    Run ``fn`` until it returns a truthy ``ok`` in a dict result or attempts exhausted.

    Returns ``(last_result, log_lines)``. If ``fn`` does not return a dict with ``ok``, first return is used.
    """
    log: list[str] = []
    last: Any = None
    for attempt in range(max_attempts):
        if attempt > 0:
            delay = delays_sec[min(attempt - 1, len(delays_sec) - 1)]
            log.append(f"Backoff {delay}s before retry #{attempt + 1}")
            time.sleep(delay)
        last = fn()
        if isinstance(last, dict) and last.get("ok"):
            log.append(f"Succeeded on attempt {attempt + 1}")
            return last, log
        if not isinstance(last, dict):
            log.append(f"Attempt {attempt + 1}: non-dict result")
            continue
        err = last.get("error") or last.get("stderr") or "failed"
        log.append(f"Attempt {attempt + 1}: {str(err)[:200]}")
    return last, log


def apply_code_fix(workspace_path: str | Path, patch: str) -> dict[str, Any]:
    """
    Apply a unified diff via ``patch -p1`` (dry-run then apply). Patch max 64KiB.

    For ad-hoc edits prefer dev missions / Aider; this path is for small deterministic fixes.
    """
    ok_gate, reason = operator_action_gates(require_write=True, require_deploy=False)
    if not ok_gate:
        return {"ok": False, "error": reason}

    raw = (patch or "").strip()
    if not raw:
        return {"ok": True, "noop": True, "message": "empty patch"}

    if len(raw) > 65_536:
        return {"ok": False, "error": "patch_too_large"}

    root = validate_workspace_path(str(workspace_path))
    timeout = float(get_settings().nexa_dev_command_timeout_seconds or 180)

    def _try_apply() -> dict[str, Any]:
        dry = subprocess.run(
            ["patch", "-p1", "--dry-run"],
            cwd=str(root),
            input=raw,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if dry.returncode != 0:
            return {
                "ok": False,
                "error": "patch_dry_run_failed",
                "stderr": (dry.stderr or "")[-8000:],
                "stdout": (dry.stdout or "")[-4000:],
            }
        real = subprocess.run(
            ["patch", "-p1"],
            cwd=str(root),
            input=raw,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        sha = rev_parse_head(root)
        return {
            "ok": real.returncode == 0,
            "returncode": real.returncode,
            "stdout": (real.stdout or "")[-8000:],
            "stderr": (real.stderr or "")[-8000:],
            "commit_sha_after": sha,
        }

    s = get_settings()
    if bool(getattr(s, "nexa_operator_auto_retry", False)):
        last, slog = retry_with_backoff(_try_apply, max_attempts=3)
        out = last if isinstance(last, dict) else {"ok": False, "error": "retry_exhausted"}
        out["retry_log"] = slog
        return out

    return _try_apply()


def run_tests(workspace_path: str | Path) -> dict[str, Any]:
    """Run allowlisted tests (``pytest`` / ``npm test`` per dev allowlist)."""
    ok_gate, reason = operator_diag_gate()
    if not ok_gate:
        return {"ok": False, "error": reason}

    root = validate_workspace_path(str(workspace_path))
    # Prefer pytest then npm test based on lockfile heuristics
    if (root / "package.json").is_file():
        r = run_dev_command(root, "npm test")
        if r.get("ok"):
            return r
        return run_dev_command(root, "npm run test")
    return run_dev_command(root, "pytest")


def commit_and_push(workspace_path: str | Path, message: str) -> dict[str, Any]:
    ok_gate, reason = operator_action_gates(require_write=True, require_deploy=False)
    if not ok_gate:
        return {"ok": False, "error": reason}

    root = validate_workspace_path(str(workspace_path))
    commit = create_commit(root, message, allow_commit=True)
    if not commit.get("ok"):
        return commit
    sha = rev_parse_head(root)
    timeout = 180.0
    try:
        push = subprocess.run(
            ["git", "push"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": push.returncode == 0,
            "returncode": push.returncode,
            "stdout": (push.stdout or "")[-8000:],
            "stderr": (push.stderr or "")[-8000:],
            "commit_sha": sha,
            "phase": "commit_push",
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000], "commit_sha": sha}


def deploy_vercel(workspace_path: str | Path) -> dict[str, Any]:
    ok_gate, reason = operator_action_gates(require_write=True, require_deploy=True)
    if not ok_gate:
        return {"ok": False, "error": reason}

    root = validate_workspace_path(str(workspace_path))
    timeout = 600.0
    try:
        proc = subprocess.run(
            ["vercel", "deploy", "--prod", "--yes"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-12000:],
            "stderr": (proc.stderr or "")[-8000:],
            "provider": "vercel",
        }
    except FileNotFoundError:
        return {"ok": False, "error": "vercel_cli_missing"}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def deploy_railway(workspace_path: str | Path) -> dict[str, Any]:
    ok_gate, reason = operator_action_gates(require_write=True, require_deploy=True)
    if not ok_gate:
        return {"ok": False, "error": reason}

    root = validate_workspace_path(str(workspace_path))
    timeout = 600.0
    try:
        proc = subprocess.run(
            ["railway", "up"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-12000:],
            "stderr": (proc.stderr or "")[-8000:],
            "provider": "railway",
        }
    except FileNotFoundError:
        return {"ok": False, "error": "railway_cli_missing"}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def verify_http_head(url: str, *, timeout_sec: float = 20.0) -> dict[str, Any]:
    """HEAD request — proof for production verification."""
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        return {"ok": False, "error": "invalid_url"}
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "NexaOperator/1.0"})
        req.get_method = lambda: "HEAD"  # type: ignore[method-assign]
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return {"ok": 200 <= int(code) < 400, "status_code": int(code), "url": u}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status_code": exc.code, "url": u, "error": str(exc)[:500]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500], "url": u}


def extract_production_url(text: str) -> str | None:
    m = re.search(r"(?i)production\s+url\s*:\s*(\S+)", text or "")
    if m:
        return m.group(1).strip().strip("`\"'")
    m2 = re.search(r"https?://[^\s]+\.vercel\.app\b", text or "")
    return m2.group(0) if m2 else None


__all__ = [
    "operator_diag_gate",
    "apply_code_fix",
    "commit_and_push",
    "deploy_railway",
    "deploy_vercel",
    "extract_production_url",
    "operator_action_gates",
    "retry_with_backoff",
    "run_tests",
    "verify_http_head",
]
