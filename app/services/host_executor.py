# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Approval-gated host execution for local_tool jobs.

No arbitrary shell: only fixed tool names and argv lists. Execution happens only after
the user approves the job and local_tool_worker runs it — never directly from LLM output.

``git`` subprocesses optionally use :mod:`app.services.operator_shell_cli` (same ``$SHELL`` login
session + nvm/rc loader as operator ``vercel`` / ``gh``) when ``NEXA_OPERATOR_CLI_PROFILE_SHELL`` is enabled.

When ``db`` and ``job`` with ``user_id`` are provided, permission registry + grants are enforced.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.services.host_executor_chain import (
    chain_actions_are_browser_open_screenshot_system,
    chain_actions_are_browser_plugin_skills,
    chain_step_output_failed,
    merge_chain_step,
    parse_chain_inner_allowed,
)
from app.services.host_executor_intent import safe_relative_path
from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback
from app.services.operator_cli_path import cli_environ_for_operator
from app.services.operator_shell_cli import profile_shell_enabled, run_allowlisted_argv_via_login_shell

logger = logging.getLogger(__name__)

# Keys -> full argv (no user-controlled tokens in argv).
ALLOWED_RUN_COMMANDS: dict[str, list[str]] = {
    "pytest": ["python", "-m", "pytest"],
    "git_status_short": ["git", "status", "--short", "--branch"],
}

DEFAULT_ALLOWED_COMMANDS: tuple[str, ...] = (
    "npm",
    "yarn",
    "pnpm",
    "pip",
    "python",
    "python3",
    "node",
    "npx",
    "git",
    "gh",
    "ls",
    "cat",
    "echo",
    "mkdir",
    "touch",
    "cp",
    "mv",
    "cd",
    "pwd",
    "chmod",
    "grep",
    "find",
)

_BLOCKED_COMMAND_SUBSTRINGS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf ~",
    "dd if=",
    "mkfs",
    ":(){ :|:& };:",
    "chmod 777 /",
    "> /dev/sda",
    "git reset --hard",
    "git clean -fd",
    "git push --force",
)

_SHELL_META_TOKENS: tuple[str, ...] = (
    "||",
    ";",
    "|",
    ">",
    "<",
    "`",
    "$(",
    "${",
    "\n",
    "\r",
)

# Allowed only when validated per-segment (see :func:`is_command_safe`).
_CHAIN_AND = " && "

_MAX_COMMAND_CHAIN_SEGMENTS = 10

# Optional git_push remote/ref — argv only (no shell).
_PUSH_REMOTE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")
_PUSH_REF_RE = re.compile(r"^[a-zA-Z0-9/_.-]{1,200}$")
# Vercel project name (slug) — no path separators.
_VERCEL_PROJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")

_PATH_BLOCKED_SUBSTRINGS = (
    ".env",
    ".ssh",
    "credentials",
    "secrets",
    ".pem",
    "id_rsa",
    "known_hosts",
)

# On-demand multi-file reads (text-ish only; no shell; no indexing).
TEXT_INTEL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".yaml",
        ".yml",
        ".toml",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".swift",
        ".kt",
        ".vue",
        ".xml",
        ".csv",
        ".svg",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
    }
)


def _host_settings():
    return get_settings()


def _base_work_dir() -> Path:
    s = _host_settings()
    raw = (getattr(s, "host_executor_work_root", None) or str(REPO_ROOT)).strip()
    return Path(raw).expanduser().resolve()


def _resolve_exec_root(payload: dict[str, Any], base: Path) -> Path:
    """Optional subdirectory (relative to host work root) for git/commands cwd."""
    cr = str(payload.get("cwd_relative") or "").strip()
    if not cr:
        return base
    sr = safe_relative_path(cr.replace("\\", "/"))
    if not sr:
        raise ValueError("invalid cwd_relative")
    return _safe_join_under_root(base, sr)


def _safe_join_under_root(root: Path, relative: str) -> Path:
    rel = (relative or "").strip().replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts or rel.startswith("/"):
        raise ValueError("path must be relative and cannot contain '..'")
    out = (root / rel).resolve()
    try:
        out.relative_to(root)
    except ValueError as e:
        raise ValueError("path escapes work root") from e
    return out


def argv_for_vercel_remove(payload: dict[str, Any]) -> list[str]:
    """Build fixed argv for ``vercel remove <project> --yes`` (non-interactive only)."""
    name = (payload.get("vercel_project_name") or payload.get("project_name") or "").strip()
    if not name or not _VERCEL_PROJECT_RE.fullmatch(name):
        raise ValueError(
            "vercel_project_name or project_name is required and must be a single Vercel project slug "
            "(alphanumeric, dot, underscore, hyphen; no path characters)"
        )
    if payload.get("vercel_yes") is not True:
        raise ValueError(
            "vercel_yes must be JSON true to confirm non-interactive removal (runs vercel remove … --yes)"
        )
    return ["vercel", "remove", name, "--yes"]


def argv_for_git_push(payload: dict[str, Any]) -> list[str]:
    """Build fixed argv for ``git push`` (optional remote + ref)."""
    remote = (payload.get("push_remote") or "").strip()
    ref = (payload.get("push_ref") or "").strip()
    if remote and not _PUSH_REMOTE_RE.fullmatch(remote):
        raise ValueError("push_remote must match [a-zA-Z][a-zA-Z0-9_.-]{0,63}")
    if ref and not _PUSH_REF_RE.fullmatch(ref):
        raise ValueError("push_ref must be a branch/ref name (allowed charset only)")
    if ref and not remote:
        raise ValueError("push_ref requires push_remote")
    if remote and ref:
        return ["git", "push", remote, ref]
    if remote:
        return ["git", "push", remote]
    return ["git", "push"]


def _path_allowed_for_io(p: Path) -> None:
    sp = str(p).lower()
    for b in _PATH_BLOCKED_SUBSTRINGS:
        if b in sp:
            raise ValueError(f"path not allowed (blocked segment): {b}")


def _allowed_command_names() -> frozenset[str]:
    s = _host_settings()
    raw = str(
        getattr(s, "nexa_allowed_commands", None)
        or os.getenv("NEXA_ALLOWED_COMMANDS", "")
        or ""
    ).strip()
    if not raw:
        return frozenset(DEFAULT_ALLOWED_COMMANDS)
    names = {x.strip().lower() for x in raw.split(",") if x.strip()}
    return frozenset(names or DEFAULT_ALLOWED_COMMANDS)


def _split_command(command: str) -> list[str] | None:
    try:
        argv = shlex.split(command or "")
    except ValueError:
        return None
    return argv or None


def _looks_like_url_arg(arg: str) -> bool:
    return bool(re.match(r"(?i)^(?:https?|ssh|git)://", arg)) or arg.startswith("git@")


def _command_arg_safe(arg: str) -> bool:
    if not arg:
        return True
    if _looks_like_url_arg(arg):
        return True
    low = arg.lower()
    if any(blocked in low for blocked in _PATH_BLOCKED_SUBSTRINGS):
        return False
    if any(tok in arg for tok in _SHELL_META_TOKENS):
        return False
    if arg.startswith(("/", "~")):
        return _absolute_arg_allowed(arg)
    if "=/" in arg:
        return False
    normalized = arg.replace("\\", "/")
    if ".." in Path(normalized).parts:
        return False
    return True


def is_command_safe(command: str, *, _segment: bool = False) -> bool:
    """Validate a command string before converting it to argv execution."""
    command_text = (command or "").strip()
    if not command_text:
        return False
    low = command_text.lower()
    if any(pattern in low for pattern in _BLOCKED_COMMAND_SUBSTRINGS):
        return False
    if not _segment and _CHAIN_AND in command_text:
        for tok in _SHELL_META_TOKENS:
            if tok in command_text:
                return False
        parts = re.split(r"\s+&&\s+", command_text)
        if len(parts) < 2 or len(parts) > _MAX_COMMAND_CHAIN_SEGMENTS:
            return False
        for p in parts:
            seg = p.strip()
            if not seg or not is_command_safe(seg, _segment=True):
                return False
        return True
    argv = _split_command(command_text)
    if not argv:
        return False
    first = Path(argv[0]).name.lower()
    if first not in _allowed_command_names():
        return False
    return all(_command_arg_safe(arg) for arg in argv[1:])


def _command_work_dir() -> Path:
    s = _host_settings()
    raw = (
        str(getattr(s, "nexa_command_work_root", "") or "").strip()
        or os.getenv("NEXA_COMMAND_WORK_ROOT", "").strip()
        or str(_base_work_dir())
    )
    return Path(raw).expanduser().resolve()


def _allowed_command_cwd_anchor_roots() -> list[Path]:
    """Resolved dirs where ``cwd_relative`` / ``npm install in`` may target (mkdir allowed)."""
    roots: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        try:
            r = p.expanduser().resolve(strict=False)
            k = str(r)
            if k not in seen:
                seen.add(k)
                roots.append(r)
        except OSError:
            return

    add(_command_work_dir())
    add(_base_work_dir())
    try:
        add(Path("/tmp"))
    except OSError:
        pass
    try:
        import tempfile

        add(Path(tempfile.gettempdir()))
    except OSError:
        pass
    return roots


def path_is_under_allowed_command_cwd_anchor(p: Path) -> bool:
    """True when ``p`` resolves under command root, host work root, ``/tmp``, or system temp."""
    try:
        pr = p.expanduser().resolve(strict=False)
    except OSError:
        return False
    for a in _allowed_command_cwd_anchor_roots():
        try:
            pr.relative_to(a)
            return True
        except ValueError:
            continue
    return False


def _resolve_command_cwd(cwd: str | None = None) -> Path:
    root = _command_work_dir()
    raw = (cwd or "").strip()
    if not raw:
        return root
    if raw.startswith("/"):
        try:
            resolved = Path(raw).expanduser().resolve(strict=False)
        except OSError as e:
            raise ValueError(f"invalid cwd: {e}") from e
        if not path_is_under_allowed_command_cwd_anchor(resolved):
            raise ValueError(
                "command cwd must be under NEXA_COMMAND_WORK_ROOT, HOST_EXECUTOR_WORK_ROOT, /tmp, or system temp"
            )
        _path_allowed_for_io(resolved)
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(f"could not create cwd: {e}") from e
        return resolved

    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = root / raw
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise ValueError("command cwd escapes NEXA_COMMAND_WORK_ROOT") from e
    _path_allowed_for_io(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _absolute_arg_allowed(arg: str) -> bool:
    """Allow ``/`` or ``~`` tokens under allowed cwd anchors; mkdir missing dirs when permitted."""
    raw = (arg or "").strip()
    if not raw or raw.startswith("-"):
        return False
    if not (raw.startswith("/") or raw.startswith("~")):
        return False
    try:
        p = Path(raw).expanduser().resolve(strict=False)
        _path_allowed_for_io(p)
    except (OSError, ValueError):
        return False

    if not path_is_under_allowed_command_cwd_anchor(p):
        return False
    if not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
    return True


def _command_timeout(default_timeout: int) -> int:
    """Resolve subprocess timeout from env and per-call hint.

    Previously this incorrectly capped at ``default_timeout``, so raising
    ``NEXA_COMMAND_TIMEOUT_SECONDS`` above the caller default (often 60) had no effect.
    """
    s = _host_settings()
    configured = int(getattr(s, "nexa_command_timeout_seconds", default_timeout) or default_timeout)
    effective = max(configured, default_timeout)
    return min(max(effective, 5), 3600)


def _maybe_ensure_package_json_for_local_install(command_text: str, exec_cwd: Path) -> None:
    """Create a minimal ``package.json`` when ``npm|pnpm|yarn install`` runs in a folder without one."""
    low = (command_text or "").strip().lower()
    if " -g " in low or "--global" in low or low.startswith("npm install -g"):
        return
    if not (
        low == "npm install"
        or low.startswith("npm install ")
        or low == "pnpm install"
        or low.startswith("pnpm install ")
        or low == "yarn install"
        or low.startswith("yarn install ")
    ):
        return
    pkg = exec_cwd / "package.json"
    if pkg.exists():
        return
    raw_name = exec_cwd.name or "workspace"
    safe = re.sub(r"[^a-z0-9._-]", "-", raw_name.lower()).strip("-")[:214] or "workspace"
    minimal = {"name": safe, "version": "1.0.0", "private": True}
    pkg.write_text(json.dumps(minimal, indent=2) + "\n", encoding="utf-8")


def _apply_task_scaffold_timeout(argv: list[str], base_timeout: int) -> int:
    """Bump timeout for long npm/npx scaffolds (e.g. ``create-react-app``)."""
    blob = " ".join(str(a) for a in argv).lower()
    if "create-react-app" not in blob:
        return base_timeout
    s = _host_settings()
    task = int(getattr(s, "nexa_task_timeout_seconds", 300) or 300)
    floor = max(300, task)
    return min(max(base_timeout, floor), 3600)


def _execute_command_sync(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    user_id: str | None = None,
    *,
    _chain_depth: int = 0,
) -> dict[str, Any]:
    _ = user_id
    if not bool(getattr(_host_settings(), "nexa_command_execution_enabled", True)):
        return {
            "success": False,
            "error": "Command execution is disabled",
            "stderr": "Set NEXA_COMMAND_EXECUTION_ENABLED=true to allow approved commands.",
            "command": command,
        }
    if not is_command_safe(command):
        return {
            "success": False,
            "error": "Command blocked for security reasons",
            "stderr": "This command is not in the allowed list",
            "command": command,
        }
    command_text = (command or "").strip()
    if _chain_depth == 0 and _CHAIN_AND in command_text:
        parts = re.split(r"\s+&&\s+", command_text)
        if len(parts) >= 2:
            stdout_acc: list[str] = []
            stderr_acc: list[str] = []
            last_rc = 0
            for i, seg in enumerate(parts):
                sub = seg.strip()
                if not sub:
                    return {
                        "success": False,
                        "error": "Empty chain segment",
                        "stderr": "Chained command has an empty segment.",
                        "command": command_text,
                    }
                sub_res = _execute_command_sync(
                    sub,
                    cwd,
                    timeout,
                    user_id,
                    _chain_depth=_chain_depth + 1,
                )
                if sub_res.get("stdout"):
                    stdout_acc.append(str(sub_res.get("stdout") or ""))
                if sub_res.get("stderr"):
                    stderr_acc.append(str(sub_res.get("stderr") or ""))
                last_rc = int(sub_res.get("return_code") if sub_res.get("return_code") is not None else 1)
                if not sub_res.get("success"):
                    scwd = str(sub_res.get("cwd") or "")
                    return {
                        "success": False,
                        "stdout": "\n".join(stdout_acc),
                        "stderr": "\n".join(stderr_acc),
                        "return_code": last_rc,
                        "command": command_text,
                        "cwd": scwd,
                    }
            try:
                ecwd = str(_resolve_command_cwd(cwd))
            except ValueError:
                ecwd = str(_command_work_dir())
            return {
                "success": True,
                "stdout": "\n".join(stdout_acc),
                "stderr": "\n".join(stderr_acc),
                "return_code": 0,
                "command": command_text,
                "cwd": ecwd,
            }
    argv = _split_command(command_text)
    if not argv:
        return {
            "success": False,
            "error": "Command is empty or invalid",
            "stderr": "Command could not be parsed safely.",
            "command": command,
        }
    try:
        exec_cwd = _resolve_command_cwd(cwd)
    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
            "stderr": str(exc),
            "command": command,
        }
    _maybe_ensure_package_json_for_local_install(command_text, exec_cwd)
    exec_timeout = _apply_task_scaffold_timeout(argv, _command_timeout(timeout))
    hs = _host_settings()
    attempts = max(1, min(10, int(getattr(hs, "nexa_host_command_max_attempts", 3) or 3)))
    retry_host = bool(getattr(hs, "nexa_host_command_retry_enabled", False))
    code, out, err = -1, "", ""
    if retry_host and attempts > 1:
        from app.services.self_healing import retry_config_from_settings, retry_delay_seconds

        cfg = retry_config_from_settings()
        cfg.max_attempts = attempts
        for attempt in range(attempts):
            code, out, err = _run_argv(argv, cwd=exec_cwd, timeout=exec_timeout)
            if code == 0:
                break
            if attempt < attempts - 1:
                delay = retry_delay_seconds(attempt + 1, cfg)
                if delay > 0:
                    time.sleep(delay)
    else:
        code, out, err = _run_argv(argv, cwd=exec_cwd, timeout=exec_timeout)
    # Self-heal: missing cwd (race, partial setup, or mkdir skipped) — create once and retry.
    if code != 0 and exec_cwd and cwd:
        combined = f"{out}\n{err}".lower()
        if "no such file or directory" in combined:
            try:
                root_chk = _command_work_dir()
                resolved_cwd = Path(exec_cwd).resolve()
                resolved_cwd.relative_to(root_chk)
                resolved_cwd.mkdir(parents=True, exist_ok=True)
                code, out, err = _run_argv(argv, cwd=exec_cwd, timeout=exec_timeout)
            except (OSError, ValueError):
                pass
    try:
        from app.services.observability import get_observability

        obs = get_observability()
        obs.record_metric("host.command.executions", 1.0, "count")
        obs.record_metric("host.command.success" if code == 0 else "host.command.failure", 1.0, "count")
    except Exception:
        pass
    return {
        "success": code == 0,
        "stdout": out,
        "stderr": err,
        "return_code": code,
        "command": command,
        "cwd": str(exec_cwd),
    }


async def execute_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Execute an approved command under the command work root."""
    return await asyncio.to_thread(_execute_command_sync, command, cwd, timeout, user_id)


def read_workspace_text_file(filepath: str, user_id: str | None = None) -> dict[str, Any]:
    """Read a UTF-8 text file under ``NEXA_COMMAND_WORK_ROOT`` (or command work dir)."""
    _ = user_id
    root = _command_work_dir()
    max_bytes = min(max(int(getattr(_host_settings(), "host_executor_max_file_bytes", 262_144)), 1024), 2_000_000)
    raw = (filepath or "").strip().strip('`"\'')
    if not raw:
        return {"success": False, "error": "Empty path", "content": None}
    p = Path(raw)
    if not p.is_absolute():
        full_path = (root / raw.replace("\\", "/").lstrip("/")).resolve()
    else:
        full_path = p.expanduser().resolve()
    try:
        full_path.relative_to(root)
    except ValueError:
        return {
            "success": False,
            "error": f"Access denied: {filepath} is outside workspace",
            "content": None,
        }
    try:
        _path_allowed_for_io(full_path)
    except ValueError as e:
        return {"success": False, "error": str(e), "content": None}
    try:
        data = full_path.read_bytes()
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {filepath}", "content": None}
    except OSError as e:
        return {"success": False, "error": str(e), "content": None}
    if len(data) > max_bytes:
        return {"success": False, "error": f"File too large (max {max_bytes} bytes)", "content": None}
    text = data.decode("utf-8", errors="replace")
    return {
        "success": True,
        "content": text,
        "path": str(full_path),
        "size": len(text.encode("utf-8", errors="replace")),
    }


async def read_file(filepath: str, user_id: str | None = None) -> dict[str, Any]:
    """Async wrapper for :func:`read_workspace_text_file`."""
    return await asyncio.to_thread(read_workspace_text_file, filepath, user_id)


def _format_command_result(result: dict[str, Any]) -> str:
    pieces: list[str] = []
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    if stdout.strip():
        pieces.append(stdout)
    if stderr.strip():
        pieces.append("STDERR:\n" + stderr)
    msg = "\n".join(pieces) if pieces else "(no output)"
    if not result.get("success"):
        code = result.get("return_code")
        if code is not None:
            return f"(exit {code})\n{msg}"[:8000]
        return f"{result.get('error') or 'Command failed'}\n{msg}"[:8000]
    return msg[:8000]


def _run_argv(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> tuple[int, str, str]:
    argv = apply_operator_cli_absolute_fallback(list(argv))
    if profile_shell_enabled() and argv and Path(argv[0]).name == "git":
        out = run_allowlisted_argv_via_login_shell(
            argv,
            cwd=str(cwd),
            timeout=float(timeout),
            env=cli_environ_for_operator(),
        )
        if out.get("error") == "timeout":
            logger.warning("host_executor profile_shell timeout argv0=%s", argv[:1])
            return -1, "", "timeout"
        if out.get("error"):
            logger.warning(
                "host_executor profile_shell argv0=%s err=%s",
                argv[:1],
                str(out.get("error"))[:200],
            )
            return (
                -1,
                (out.get("stdout") or "")[:24_000],
                (out.get("stderr") or "")[:24_000],
            )
        code = int(out.get("exit_code") if out.get("exit_code") is not None else (0 if out.get("ok") else 1))
        so = (out.get("stdout") or "")[:24_000]
        se = (out.get("stderr") or "")[:24_000]
        logger.info(
            "host_executor profile_shell argv0=%s exit=%s ok=%s",
            argv[0] if argv else "",
            code,
            code == 0,
        )
        return code, so, se
    try:
        r = subprocess.run(  # noqa: S603 — argv constructed only from allowlists
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=cli_environ_for_operator(),
        )
    except subprocess.TimeoutExpired:
        logger.warning("host_executor timeout argv0=%s", argv[:1])
        return -1, "", "timeout"
    except (OSError, FileNotFoundError) as e:
        logger.warning("host_executor spawn failed argv0=%s err=%s", argv[:1], type(e).__name__)
        return -1, "", str(e)[:2000]
    out = (r.stdout or "")[:24_000]
    err = (r.stderr or "")[:24_000]
    logger.info(
        "host_executor argv0=%s exit=%s ok=%s",
        argv[0] if argv else "",
        r.returncode,
        r.returncode == 0,
    )
    return r.returncode, out, err


# Phase 70 — host actions whose simulation plan is just "would read" (no side effects).
_SIMULATION_READ_ONLY_ACTIONS: frozenset[str] = frozenset(
    {
        "git_status",
        "file_read",
        "list_directory",
        "find_files",
        "read_multiple_files",
    }
)


def _format_simulation_plan(
    payload: dict[str, Any],
    *,
    action: str,
    exec_root: Path,
    root: Path,
) -> str:
    """
    Phase 70 — produce a readable "would do …" summary for ``execute_payload(simulate=True)``.

    Runs after validation + permission enforcement, so any error the real call
    would have raised (invalid path, missing field, blocked permission) has
    already been raised and the user sees a real failure rather than a fake plan.
    The summary intentionally uses the real allowlist (``ALLOWED_RUN_COMMANDS``)
    so what we describe is exactly what would have run.
    """
    cwd_display = str(exec_root)
    header = f"[SIMULATED] action={action or '(missing)'} cwd={cwd_display}"
    lines: list[str] = [header]

    if action in _SIMULATION_READ_ONLY_ACTIONS:
        lines.append("Effect: read-only — no files modified, no commands executed.")
    else:
        lines.append("Effect: would mutate files / run a process — nothing was executed.")

    if action == "chain":
        steps = payload.get("actions") or []
        if isinstance(steps, list) and steps:
            lines.append(f"Plan: {len(steps)} chained step(s) (none executed)")
            for i, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    lines.append(f"  {i}. (invalid step entry)")
                    continue
                inner = (step.get("host_action") or "").strip().lower() or "(missing)"
                target = (
                    step.get("relative_path")
                    or step.get("ref")
                    or step.get("remote")
                    or step.get("run_name")
                    or step.get("project")
                    or step.get("skill_name")
                    or "—"
                )
                lines.append(f"  {i}. host_action={inner} target={target}")
            lines.append("Pass simulate=False to execute.")
            return "\n".join(lines)

    if action == "run_command":
        command = (payload.get("command") or "").strip()
        if command:
            lines.append(f"Would run: {command} (cwd={_command_work_dir()})")
        else:
            name = (payload.get("run_name") or "").strip().lower()
            argv = ALLOWED_RUN_COMMANDS.get(name)
            if argv:
                lines.append(f"Would run: {' '.join(argv)} (cwd={cwd_display})")
            else:
                lines.append(f"Would resolve run_name={name!r} via ALLOWED_RUN_COMMANDS")
    elif action == "git_push":
        remote = (payload.get("remote") or "origin").strip()
        ref = (payload.get("ref") or "HEAD").strip()
        lines.append(f"Would run: git push {remote} {ref} (cwd={cwd_display})")
    elif action == "git_commit":
        msg = (payload.get("commit_message") or "").strip()
        preview = msg[:120] + ("…" if len(msg) > 120 else "")
        lines.append(f"Would run: git add -A && git commit -m {preview!r} (cwd={cwd_display})")
        gst = _git_status_short_paths(exec_root)
        paths = gst.get("paths") if isinstance(gst.get("paths"), list) else []
        if paths:
            tail = ", ".join(str(p) for p in paths[:12])
            more = f" … (+{len(paths) - 12} more)" if len(paths) > 12 else ""
            lines.append(f"Changed paths (status --short): {tail}{more}")
        elif gst.get("error") and gst.get("error") != "sandbox_probes_disabled":
            lines.append(f"(Could not list changed files: {gst.get('error')})")
    elif action == "git_status":
        lines.append(f"Would run: git status --short --branch (cwd={cwd_display})")
    elif action == "file_write":
        rel = (payload.get("relative_path") or "").strip()
        content = payload.get("content")
        size = len(content) if isinstance(content, (str, bytes)) else 0
        lines.append(f"Would write {size} byte(s) to {rel or '(missing relative_path)'}")
    elif action == "file_read":
        rel = (payload.get("relative_path") or "").strip()
        lines.append(f"Would read file: {rel or '(missing relative_path)'}")
    elif action == "list_directory":
        rel = (payload.get("relative_path") or ".").strip() or "."
        lines.append(f"Would list directory: {rel}")
    elif action == "find_files":
        rel = (payload.get("relative_path") or ".").strip() or "."
        pat = (payload.get("glob") or payload.get("pattern") or "*").strip()
        lines.append(f"Would search for files matching {pat!r} under {rel}")
    elif action == "read_multiple_files":
        explicit = payload.get("relative_paths")
        if isinstance(explicit, list) and explicit:
            preview = ", ".join(str(p) for p in explicit[:5])
            tail = " …" if len(explicit) > 5 else ""
            lines.append(f"Would read up to {len(explicit)} file(s): {preview}{tail}")
        else:
            base = payload.get("base") or payload.get("relative_path") or "."
            lines.append(f"Would read multiple files under base={base}")
    elif action == "plugin_skill":
        name = (payload.get("skill_name") or "").strip()
        lines.append(f"Would invoke plugin skill: {name or '(missing skill_name)'}")
    elif action == "browser_open":
        u = (payload.get("url") or "").strip()
        lines.append(f"Would open in system default browser: {u or '(missing url)'}")
    elif action == "show_workspace_root":
        lines.append("Would print NEXA_WORKSPACE_ROOT and HOST_EXECUTOR_WORK_ROOT (read-only).")
    elif action in ("browser_click", "browser_fill", "browser_screenshot"):
        lines.append(f"Would run browser host action (Playwright): {action}")
    elif not action:
        lines.append("Would dispatch (action missing — would have raised ValueError at runtime).")
    else:
        lines.append(f"Would dispatch host_action={action} (no specialized simulator defined).")

    lines.append("Pass simulate=False to execute.")
    return "\n".join(lines)


# ============================================================================
# Phase 76 — structured simulation plan (Blue-Green safety preview)
# ============================================================================

# Cloud providers we recognise for the structured "would deploy" preview. The
# list is intentionally tiny — Phase 76 doesn't call out to any provider API,
# it just surfaces a structured "would_affect" payload so the UI can render a
# meaningful confirmation card. Add more providers here as integrations land.
_SIMULATION_DEPLOY_HINTS: dict[str, list[str]] = {
    "vercel": ["serverless functions", "static assets", "preview URL"],
    "vercel_redeploy": ["serverless functions", "static assets", "preview URL"],
    "vercel_remove": ["project deletion", "all deployments", "DNS detach"],
    "railway": ["service runtime", "environment variables", "scaling policy"],
    "aws": ["IAM-bounded resources", "stack outputs", "environment"],
}


def _resolve_simulation_diff_cap() -> int:
    """Cap returned diff size. ``0`` (or unset) → fall back to a sensible default."""
    raw = getattr(_host_settings(), "nexa_simulation_max_diff_lines", 500)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 500
    return max(50, n)


def _build_file_write_diff(
    *,
    relative_path: str,
    proposed_content: str,
    exec_root: Path,
    max_lines: int,
) -> dict[str, Any]:
    """Compute a unified diff between the on-disk file (if any) and the proposed content.

    Returns a structured payload suitable for the UI:

    .. code-block:: json

        {
          "kind": "file_write",
          "path": "<relative path>",
          "is_new_file": <bool>,
          "old_size_bytes": <int>,
          "new_size_bytes": <int>,
          "unified": "<unified diff text or empty>",
          "added": <int>,
          "removed": <int>,
          "truncated": <bool>,
          "max_lines": <int>
        }

    The diff is computed against the resolved on-disk path under ``exec_root``;
    paths that escape the host work root return ``unified=""`` and the
    ``error`` field set so the caller can surface a non-fatal warning. The
    diff is NEVER computed for binary files (UTF-8 decode failure marks
    ``binary=True`` and skips the unified text).
    """
    import difflib

    payload: dict[str, Any] = {
        "kind": "file_write",
        "path": relative_path,
        "is_new_file": False,
        "old_size_bytes": 0,
        "new_size_bytes": len(proposed_content.encode("utf-8", errors="replace"))
        if isinstance(proposed_content, str)
        else len(proposed_content or b""),
        "unified": "",
        "added": 0,
        "removed": 0,
        "truncated": False,
        "max_lines": max_lines,
        "binary": False,
    }
    if not isinstance(proposed_content, str):
        # We don't try to diff bytes payloads (skill might be uploading a
        # binary asset). The structured row still surfaces size + path.
        payload["binary"] = True
        return payload

    try:
        target = _safe_join_under_root(exec_root, relative_path)
    except ValueError as exc:
        payload["error"] = f"path_resolution_failed: {exc}"
        return payload

    old_text = ""
    if target.exists() and target.is_file():
        try:
            old_text = target.read_text(encoding="utf-8")
            payload["old_size_bytes"] = len(old_text.encode("utf-8", errors="replace"))
        except UnicodeDecodeError:
            payload["binary"] = True
            return payload
        except OSError as exc:
            payload["error"] = f"read_failed: {exc}"
            return payload
    else:
        payload["is_new_file"] = True

    old_lines = old_text.splitlines(keepends=True)
    new_lines = proposed_content.splitlines(keepends=True)
    diff_iter = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
        n=3,
    )
    raw_lines: list[str] = []
    for line in diff_iter:
        if not line.endswith("\n"):
            line = line + "\n"
        raw_lines.append(line)
        if len(raw_lines) >= max_lines:
            payload["truncated"] = True
            break
    if payload["truncated"]:
        raw_lines.append(f"... [diff truncated at {max_lines} lines] ...\n")
    payload["unified"] = "".join(raw_lines)
    # Count + / - lines, ignoring the file headers (+++ / ---).
    for line in raw_lines:
        if line.startswith("+") and not line.startswith("+++"):
            payload["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            payload["removed"] += 1
    return payload


def _git_ahead_behind(exec_root: Path, remote: str, ref: str) -> dict[str, Any]:
    """Best-effort ``git rev-list --left-right --count`` summary for a push preview.

    Returns ``{"ahead": int, "behind": int, "current_branch": str|None}`` or
    ``{"error": "..."}``. Never raises — git failures degrade to an empty
    structured payload so the simulation card still renders.
    """
    import subprocess  # noqa: PLC0415

    out: dict[str, Any] = {"ahead": None, "behind": None, "current_branch": None}
    if not exec_root.exists():
        return {"error": "exec_root_missing"}
    try:
        branch = subprocess.run(
            ["git", "-C", str(exec_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if branch.returncode == 0:
            out["current_branch"] = branch.stdout.strip() or None
        target = ref or "HEAD"
        upstream_ref = f"{remote}/{out['current_branch']}" if out["current_branch"] else remote
        rev = subprocess.run(
            [
                "git", "-C", str(exec_root),
                "rev-list", "--left-right", "--count",
                f"{upstream_ref}...{target}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if rev.returncode == 0 and rev.stdout.strip():
            parts = rev.stdout.strip().split()
            if len(parts) == 2:
                out["behind"], out["ahead"] = int(parts[0]), int(parts[1])
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"git_probe_failed: {exc!s}"[:200]
    return out


def _git_status_short_paths(exec_root: Path, *, timeout: int = 15) -> dict[str, Any]:
    """Best-effort paths from ``git status --short`` for simulation previews (no mutations)."""
    out: dict[str, Any] = {"paths": [], "error": None}
    if not bool(getattr(_host_settings(), "nexa_simulation_sandbox_mode", True)):
        out["error"] = "sandbox_probes_disabled"
        return out
    if not exec_root.exists():
        out["error"] = "exec_root_missing"
        return out
    try:
        r = subprocess.run(
            ["git", "-C", str(exec_root), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            out["error"] = f"git_status_failed: {err}"[:200]
            return out
        paths: list[str] = []
        for line in (r.stdout or "").splitlines():
            line = line.rstrip()
            if len(line) < 4:
                continue
            rest = line[3:].strip()
            if " -> " in rest:
                rest = rest.split(" -> ", 1)[-1].strip()
            rest = rest.strip('"').strip("'")
            if rest:
                paths.append(rest)
        out["paths"] = paths[:500]
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"git_status_probe_failed: {exc!s}"[:200]
    return out


def build_simulation_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Phase 76 — return a structured "would do …" preview for one host action.

    Mirrors :func:`_format_simulation_plan` but emits a JSON-shaped payload
    (with an optional ``diff`` key for file_write actions). Designed to be
    called *after* the caller has run ``execute_payload(simulate=True)`` so
    validation + permission errors have already surfaced.

    The function NEVER raises on per-action probing failures — anything that
    can't be derived (missing field, file outside the workspace, git probe
    failure) is reported as a soft ``error`` field on the relevant block.

    Returned shape:

    .. code-block:: json

        {
          "action": "file_write",
          "kind": "mutation" | "read_only" | "deploy" | "skill" | "chain" | "unknown",
          "fields": {...},          // action-specific structured fields
          "diff": {...} | null,     // present only for file_write
          "steps": [...] | null,    // present only for chain (recursive plans)
          "supports_diff": <bool>
        }
    """
    pl = payload if isinstance(payload, dict) else {}
    action = (pl.get("host_action") or pl.get("action") or "").strip().lower()
    base = _base_work_dir()
    try:
        exec_root = _resolve_exec_root(pl, base)
    except ValueError:
        exec_root = base
    cap = _resolve_simulation_diff_cap()

    plan: dict[str, Any] = {
        "action": action or "(missing)",
        "kind": "unknown",
        "fields": {},
        "diff": None,
        "steps": None,
        "supports_diff": False,
    }

    if action in _SIMULATION_READ_ONLY_ACTIONS:
        plan["kind"] = "read_only"

    if action == "file_write":
        plan["kind"] = "mutation"
        plan["supports_diff"] = True
        rel = (pl.get("relative_path") or "").strip()
        content = pl.get("content")
        plan["fields"] = {
            "relative_path": rel,
            "exec_root": str(exec_root),
            "size_bytes_proposed": len(content.encode("utf-8", errors="replace"))
            if isinstance(content, str)
            else (len(content) if isinstance(content, (bytes, bytearray)) else 0),
            "content_preview": (content[:200] if isinstance(content, str) else None),
        }
        if rel and isinstance(content, str):
            plan["diff"] = _build_file_write_diff(
                relative_path=rel,
                proposed_content=content,
                exec_root=exec_root,
                max_lines=cap,
            )

    elif action == "file_read":
        plan["fields"] = {
            "relative_path": (pl.get("relative_path") or "").strip() or None,
            "exec_root": str(exec_root),
        }

    elif action == "list_directory":
        plan["fields"] = {
            "relative_path": (pl.get("relative_path") or ".").strip() or ".",
            "exec_root": str(exec_root),
        }

    elif action == "find_files":
        plan["fields"] = {
            "relative_path": (pl.get("relative_path") or ".").strip() or ".",
            "pattern": (pl.get("glob") or pl.get("pattern") or "*").strip(),
            "exec_root": str(exec_root),
        }

    elif action == "read_multiple_files":
        explicit = pl.get("relative_paths")
        plan["fields"] = {
            "relative_paths": (
                [str(p) for p in explicit]
                if isinstance(explicit, list)
                else None
            ),
            "base": pl.get("base") or pl.get("relative_path") or ".",
            "exec_root": str(exec_root),
        }

    elif action == "git_status":
        plan["kind"] = "read_only"
        plan["fields"] = {
            "exec_root": str(exec_root),
            "command_preview": "git status --short --branch",
        }

    elif action == "git_push":
        plan["kind"] = "mutation"
        remote = (pl.get("remote") or "origin").strip()
        ref = (pl.get("ref") or "HEAD").strip()
        plan["fields"] = {
            "remote": remote,
            "ref": ref,
            "exec_root": str(exec_root),
            "command_preview": f"git push {remote} {ref}",
            "ahead_behind": _git_ahead_behind(exec_root, remote, ref),
        }

    elif action == "git_commit":
        plan["kind"] = "mutation"
        cm = (pl.get("commit_message") or "").strip()
        gst = _git_status_short_paths(exec_root)
        plan["fields"] = {
            "commit_message": cm or None,
            "exec_root": str(exec_root),
            "changed_files": gst.get("paths") or [],
            "git_status_note": gst.get("error"),
            "command_preview": "git add -A && git commit -m <message>",
        }

    elif action == "run_command":
        plan["kind"] = "mutation"
        command = (pl.get("command") or "").strip()
        if command:
            plan["fields"] = {
                "command": command,
                "argv": _split_command(command),
                "exec_root": str(_command_work_dir()),
                "command_preview": command,
            }
        else:
            name = (pl.get("run_name") or "").strip().lower()
            argv = ALLOWED_RUN_COMMANDS.get(name)
            plan["fields"] = {
                "run_name": name or None,
                "argv": list(argv) if argv else None,
                "exec_root": str(exec_root),
                "command_preview": " ".join(argv) if argv else None,
            }

    elif action == "plugin_skill":
        plan["kind"] = "skill"
        plan["fields"] = {
            "skill_name": (pl.get("skill_name") or "").strip() or None,
            "input_preview": pl.get("input")
            if isinstance(pl.get("input"), dict)
            else None,
        }

    elif action in ("browser_open", "browser_click", "browser_fill", "browser_screenshot"):
        plan["kind"] = "browser"
        hs = _host_settings()
        txt = str(pl.get("text") or "")
        plan["fields"] = {
            "action": action,
            "url": (pl.get("url") or "").strip() or None,
            "selector": (pl.get("selector") or "").strip() or None,
            "text_preview": (txt[:120] + ("…" if len(txt) > 120 else "")) if txt else None,
            "name": (pl.get("name") or "").strip() or None,
            "screenshot_dir": str(getattr(hs, "nexa_browser_screenshot_dir", "") or ""),
        }

    elif action == "show_workspace_root":
        plan["kind"] = "info"
        plan["fields"] = {
            "action": "show_workspace_root",
            "nexa_workspace_root": (pl.get("nexa_workspace_root") or getattr(_host_settings(), "nexa_workspace_root", "") or ""),
            "host_executor_work_root": (
                pl.get("host_executor_work_root") or getattr(_host_settings(), "host_executor_work_root", "") or ""
            ),
        }

    elif action in _SIMULATION_DEPLOY_HINTS:
        plan["kind"] = "deploy"
        plan["fields"] = {
            "provider": (pl.get("provider") or action).strip().lower(),
            "environment": (pl.get("environment") or "production").strip(),
            "project": pl.get("project") or pl.get("vercel_project_name"),
            "would_affect": list(_SIMULATION_DEPLOY_HINTS[action]),
            "note": (
                "Phase 76 v1 does not call provider APIs during simulation; "
                "the would_affect list is a static safety hint."
            ),
        }

    elif action == "chain":
        plan["kind"] = "chain"
        steps_in = pl.get("actions") if isinstance(pl.get("actions"), list) else []
        substeps: list[dict[str, Any]] = []
        for i, step in enumerate(steps_in, start=1):
            if not isinstance(step, dict):
                substeps.append({"index": i, "error": "invalid_step_entry"})
                continue
            substep_plan = build_simulation_plan(step)
            substep_plan["index"] = i
            substeps.append(substep_plan)
        plan["steps"] = substeps
        plan["fields"] = {"step_count": len(substeps)}

    elif not action:
        plan["kind"] = "unknown"
        plan["fields"] = {"error": "missing_host_action"}

    else:
        plan["fields"] = {
            "note": f"no specialized simulator defined for {action!r}",
            "exec_root": str(exec_root),
        }

    return plan


def execute_payload(
    payload: dict[str, Any],
    *,
    db: Any | None = None,
    job: Any | None = None,
    simulate: bool | None = None,
) -> str:
    """
    Run one host action from an allowlisted payload (used by tests and worker).

    Permission + workspace checks run when enforcement is on, ``db`` and ``job.user_id`` are set
    (production worker with ``NEXA_ACCESS_PERMISSIONS_ENFORCED=1``).
    Unit tests call with payload only → checks skipped.

    Phase 70 — when ``simulate=True`` the function runs through validation,
    permission, and policy enforcement (so dry-runs surface real errors) but
    returns a planned-actions summary instead of executing the host action.
    Defaults to :data:`Settings.nexa_host_executor_dry_run_default` (False) so
    existing call sites are unchanged.

    Returns user-facing text (stdout/stderr summary, or a ``[SIMULATED]`` plan
    when ``simulate=True``). Raises ValueError on validation.
    """
    s = _host_settings()
    if not getattr(s, "nexa_host_executor_enabled", False):
        raise ValueError(
            "Host executor is disabled. Set NEXA_HOST_EXECUTOR_ENABLED=1 on the worker host."
        )

    from app.services.enforcement_pipeline import (
        audit_enforcement_path_if_enabled,
        enforce_host_execution_policy,
    )

    payload = enforce_host_execution_policy(payload, boundary="host_executor")

    action = (payload.get("host_action") or payload.get("action") or "").strip().lower()
    uid = getattr(job, "user_id", None) if job is not None else None
    enforce_perm = bool(getattr(s, "nexa_access_permissions_enforced", False))
    if db is not None and uid and enforce_perm:
        from app.services.trust_audit_correlation import warn_missing_correlation

        warn_missing_correlation(
            payload,
            boundary="host_executor",
            logger=logger,
            hint=f"host_action={action}",
        )

    if db is not None and uid:
        audit_enforcement_path_if_enabled(
            db,
            boundary="host_executor",
            action_type=action or "unknown",
            user_id=str(uid),
            extra={"sensitivity": payload.get("_nexa_sensitivity")},
        )
    timeout = min(
        max(int(getattr(s, "host_executor_timeout_seconds", 120)), 5),
        3600,
    )
    root = _base_work_dir()
    exec_root = _resolve_exec_root(payload, root)
    max_bytes = min(max(int(getattr(s, "host_executor_max_file_bytes", 262_144)), 1024), 2_000_000)

    chain_inner = bool(payload.get("_nexa_chain_inner_step"))
    enforce = enforce_perm
    grants: list[Any] = []
    check_perms = bool(db is not None and uid and enforce and not chain_inner)
    if check_perms:
        from app.services.access_permissions import (
            check_host_executor_chain_job,
            check_host_executor_job,
        )

        if action == "chain":
            ok, err, grants = check_host_executor_chain_job(
                db,
                owner_user_id=str(uid),
                work_root=root,
                payload=payload,
            )
        else:
            ok, err, grants = check_host_executor_job(
                db,
                owner_user_id=str(uid),
                host_action=action,
                work_root=root,
                payload=payload,
            )
        if not ok:
            raise ValueError(err)

    def _finalize_output(text: str) -> str:
        if db is None or not uid or not enforce or not grants:
            return text
        from app.services.access_permissions import finalize_permission_use

        prefix = finalize_permission_use(
            db, str(uid), grants, host_action=action, payload=payload
        )
        return f"{prefix}\n\n{text}" if prefix else text

    effective_simulate = (
        bool(simulate)
        if simulate is not None
        else bool(getattr(s, "nexa_host_executor_dry_run_default", False))
    )
    if effective_simulate:
        plan = _format_simulation_plan(payload, action=action, exec_root=exec_root, root=root)
        logger.info(
            "host_executor simulate=true action=%s exec_root=%s",
            action or "(unknown)",
            str(exec_root)[-128:],
        )
        return _finalize_output(plan)

    if action == "show_workspace_root":
        lines = [
            "Configured workspace paths:",
            "",
            f"- NEXA_WORKSPACE_ROOT: {getattr(s, 'nexa_workspace_root', '') or '(unset)'}",
            f"- HOST_EXECUTOR_WORK_ROOT: {getattr(s, 'host_executor_work_root', '') or '(unset)'}",
        ]
        hr = (getattr(s, "host_executor_work_root", "") or "").strip()
        if hr:
            try:
                r = Path(hr).expanduser().resolve()
                lines.append(f"- Resolved host work root: {r}")
            except OSError as exc:
                lines.append(f"- (Could not resolve host work root: {exc})")
        return _finalize_output("\n".join(lines))

    if action == "chain":
        actions_in = payload.get("actions")
        browser_chain = isinstance(actions_in, list) and chain_actions_are_browser_plugin_skills(
            actions_in
        )
        system_open_shot = isinstance(actions_in, list) and chain_actions_are_browser_open_screenshot_system(
            actions_in
        )
        if (
            not bool(getattr(s, "nexa_host_executor_chain_enabled", False))
            and not browser_chain
            and not system_open_shot
        ):
            raise ValueError(
                "Chain host actions are disabled. Set NEXA_HOST_EXECUTOR_CHAIN_ENABLED=1 on the worker."
            )
        allowed_inner = parse_chain_inner_allowed(s)
        if not isinstance(actions_in, list) or not actions_in:
            raise ValueError("chain requires a non-empty actions list")
        max_s = min(max(int(getattr(s, "nexa_host_executor_chain_max_steps", 10)), 1), 20)
        if len(actions_in) > max_s:
            raise ValueError(f"chain has {len(actions_in)} steps; max is {max_s}")
        for i, step in enumerate(actions_in):
            if not isinstance(step, dict):
                raise ValueError(f"chain step {i + 1} must be an object")
            iha = (step.get("host_action") or "").strip().lower()
            if iha == "chain":
                raise ValueError("nested chain is not allowed")
            if iha not in allowed_inner:
                raise ValueError(
                    f"chain step {i + 1}: host_action {iha!r} is not allowed in a chain; "
                    f"allowed: {sorted(allowed_inner)}"
                )
        stop_on = payload.get("stop_on_failure", True)
        if not isinstance(stop_on, bool):
            stop_on = True
        parts_out: list[str] = []
        n_actions = len(actions_in)
        total_start = time.perf_counter()
        success_count = 0

        def _log_chain_summary(*, exit_reason: str) -> None:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            logger.info(
                "Chain completed (%s): %s/%s steps successful in %.2fms (stop_on_failure=%s)",
                exit_reason,
                success_count,
                n_actions,
                total_ms,
                stop_on,
                extra={
                    "nexa_event": "chain_summary",
                    "chain_exit_reason": exit_reason,
                    "chain_total_steps": n_actions,
                    "chain_success_count": success_count,
                    "chain_total_duration_ms": round(total_ms, 2),
                    "chain_stop_on_failure": stop_on,
                },
            )

        for i, step in enumerate(actions_in):
            merged = merge_chain_step(payload, step)
            iha = (merged.get("host_action") or "").strip().lower()
            merged_inner = dict(merged)
            merged_inner["_nexa_chain_inner_step"] = True
            step_start = time.perf_counter()
            try:
                out = execute_payload(merged_inner, db=db, job=job)
            except ValueError as e:
                step_ms = (time.perf_counter() - step_start) * 1000.0
                logger.info(
                    "Chain step %s/%s (%s) validation error",
                    i + 1,
                    n_actions,
                    iha,
                    extra={
                        "nexa_event": "chain_step",
                        "chain_step": i + 1,
                        "chain_total_steps": n_actions,
                        "host_action": iha,
                        "duration_ms": round(step_ms, 2),
                        "success": False,
                        "error": str(e)[:2000],
                    },
                )
                parts_out.append(f"### Step {i + 1} ({iha}) — error\n\n{e}")
                if stop_on:
                    parts_out.append("_Stopped (stop_on_failure=True)._")
                    _log_chain_summary(exit_reason="stop_on_failure_validation")
                    return _finalize_output("\n\n".join(parts_out))
                continue
            step_ms = (time.perf_counter() - step_start) * 1000.0
            step_ok = not chain_step_output_failed(out)
            if step_ok:
                success_count += 1
            err_snippet = (out or "")[:500] if not step_ok else None
            logger.info(
                "Chain step %s/%s (%s) done",
                i + 1,
                n_actions,
                iha,
                extra={
                    "nexa_event": "chain_step",
                    "chain_step": i + 1,
                    "chain_total_steps": n_actions,
                    "host_action": iha,
                    "duration_ms": round(step_ms, 2),
                    "success": step_ok,
                    "error": err_snippet,
                },
            )
            parts_out.append(f"### Step {i + 1} ({iha})\n\n{out}")
            if stop_on and chain_step_output_failed(out):
                parts_out.append("_Stopped (stop_on_failure=True) after a failed step._")
                _log_chain_summary(exit_reason="stop_on_failure_step")
                return _finalize_output("\n\n".join(parts_out))
        _log_chain_summary(exit_reason="complete")
        return _finalize_output("\n\n".join(parts_out))

    if action == "plugin_skill":
        from app.services.skills.plugin_skill_bridge import run_plugin_skill_sync

        name = (payload.get("skill_name") or "").strip()
        if not name:
            raise ValueError("plugin_skill requires skill_name")
        inp = payload.get("input")
        if inp is not None and not isinstance(inp, dict):
            raise ValueError("plugin_skill input must be an object")
        raw = run_plugin_skill_sync(name, dict(inp or {}))
        return _finalize_output(str(raw)[:24_000])

    if action in ("browser_open", "browser_click", "browser_fill", "browser_screenshot"):
        from app.services.browser_automation import run_browser_host_action_sync

        raw = run_browser_host_action_sync(action, dict(payload))
        return _finalize_output(str(raw)[:24_000])

    if action == "git_status":
        code, out, err = _run_argv(
            ["git", "status", "--short", "--branch"],
            cwd=exec_root,
            timeout=min(timeout, 60),
        )
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        if code != 0:
            return _finalize_output(f"(exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000] or "(empty)")

    if action == "run_command":
        command = (payload.get("command") or "").strip()
        if command:
            cwd_rel = str(payload.get("cwd_relative") or "").strip()
            if cwd_rel:
                if cwd_rel.startswith("/"):
                    command_cwd = str(_resolve_command_cwd(cwd_rel))
                else:
                    command_cwd = str(_safe_join_under_root(_command_work_dir(), cwd_rel))
            else:
                command_cwd = None
            result = _execute_command_sync(
                command,
                cwd=command_cwd,
                timeout=timeout,
                user_id=str(uid) if uid else None,
            )
            return _finalize_output(_format_command_result(result))
        name = (payload.get("run_name") or "").strip().lower()
        if name not in ALLOWED_RUN_COMMANDS:
            raise ValueError(
                f"unknown or disallowed run_name {name!r}; allowed: {sorted(ALLOWED_RUN_COMMANDS)}"
            )
        argv = list(ALLOWED_RUN_COMMANDS[name])
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=timeout)
        pieces = []
        if out.strip():
            pieces.append(out)
        if err.strip():
            pieces.append("STDERR:\n" + err)
        msg = "\n".join(pieces) if pieces else "(no output)"
        if code != 0:
            return _finalize_output(f"(exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000])

    if action == "file_read":
        rel = (payload.get("relative_path") or "").strip()
        if not rel:
            raise ValueError("file_read requires relative_path")
        path = _safe_join_under_root(root, rel)
        _path_allowed_for_io(path)
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if path.is_dir():
            raise ValueError(
                f"{path} is a folder, not a file. Use \"analyze folder {path}\" "
                "or list that path, or provide a specific file path."
            )
        if not path.is_file():
            raise ValueError(f"Not a readable file: {path}")
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise ValueError(f"file too large (max {max_bytes} bytes)")
        text = data.decode("utf-8", errors="replace")
        logger.info("host_executor file_read ok bytes=%s", len(data))
        return _finalize_output(text[:max_bytes])

    if action == "file_write":
        rel = (payload.get("relative_path") or "").strip()
        content = payload.get("content")
        if not rel or content is None:
            raise ValueError("file_write requires relative_path and content")
        path = _safe_join_under_root(root, rel)
        _path_allowed_for_io(path)
        if path.exists() and path.is_dir():
            raise ValueError("path is a directory")
        b = content if isinstance(content, bytes) else str(content).encode("utf-8")
        if len(b) > max_bytes:
            raise ValueError(f"content too large (max {max_bytes} bytes)")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b)
        logger.info("host_executor file_write ok path_suffix=%s", rel[-64:])
        return _finalize_output(f"✅ File created: **{rel}**\n📍 Location: `{path}`\n📦 Size: {len(b)} bytes")

    if action == "list_directory":
        raw_abs = payload.get("nexa_permission_abs_targets")
        if isinstance(raw_abs, list) and raw_abs:
            try:
                dirp = Path(str(raw_abs[0])).expanduser().resolve()
            except OSError as e:
                raise ValueError("invalid list_directory absolute target") from e
            _path_allowed_for_io(dirp)
        else:
            rel = (payload.get("relative_path") or ".").strip() or "."
            dirp = _safe_join_under_root(root, rel)
            _path_allowed_for_io(dirp)
        if not dirp.is_dir():
            raise ValueError("list_directory target must be a directory")
        lines: list[str] = []
        for i, ch in enumerate(sorted(dirp.iterdir(), key=lambda p: p.name.lower())):
            if i >= 200:
                lines.append("… (truncated at 200 entries)")
                break
            kind = "dir" if ch.is_dir() else "file"
            lines.append(f"{kind}\t{ch.name}")
        logger.info("host_executor list_directory entries=%s", min(len(lines), 200))
        return _finalize_output("\n".join(lines) if lines else "(empty)")

    if action == "find_files":
        rel = (payload.get("relative_path") or ".").strip() or "."
        pat = (payload.get("glob") or payload.get("pattern") or "*").strip()
        if len(pat) > 120 or "/" in pat or "\\" in pat:
            raise ValueError("glob pattern too large or contains path separators")
        if not re.match(r"^[A-Za-z0-9_.*?\-\[\]]+$", pat):
            raise ValueError("invalid glob pattern")
        base = _safe_join_under_root(root, rel)
        _path_allowed_for_io(base)
        if not base.is_dir():
            raise ValueError("find_files base must be a directory")
        found: list[str] = []
        ext_raw = payload.get("extensions")
        ext_filter: frozenset[str] | None = None
        if isinstance(ext_raw, list) and ext_raw:
            ext_filter = frozenset(
                (e if str(e).startswith(".") else f".{str(e).lower()}").lower()
                for e in ext_raw
                if str(e).strip()
            )
        for i, p in enumerate(sorted(base.glob(pat), key=lambda x: str(x).lower())):
            if ext_filter is not None and p.suffix.lower() not in ext_filter:
                continue
            if i >= 500:
                found.append("… (truncated at 500 matches)")
                break
            try:
                rp = p.resolve().relative_to(root)
                found.append(str(rp).replace("\\", "/"))
            except ValueError:
                continue
        logger.info("host_executor find_files matches=%s", min(len(found), 500))
        return _finalize_output("\n".join(found) if found else "(no matches)")

    if action == "read_multiple_files":
        logger.info(
            "READ_MULTIPLE_FILES base=%s abs_targets=%s",
            payload.get("base"),
            payload.get("nexa_permission_abs_targets"),
        )
        max_files = min(
            max(int(getattr(s, "host_executor_read_multiple_max_files", 20)), 1),
            50,
        )
        total_cap = min(max_bytes * max_files, 2_500_000)
        keyword = (payload.get("keyword") or "").strip().lower()

        ext_raw = payload.get("extensions")
        if isinstance(ext_raw, list) and ext_raw:
            ext_set = frozenset(
                (e if str(e).startswith(".") else f".{str(e)}").lower()
                for e in ext_raw
                if str(e).strip()
            )
        else:
            ext_set = TEXT_INTEL_EXTENSIONS

        explicit = payload.get("relative_paths")
        chunks_out: list[str] = []
        bytes_used = 0

        def add_file(rel_display: str, fp: Path) -> bool:
            nonlocal bytes_used
            _path_allowed_for_io(fp)
            if not fp.is_file():
                return True
            if fp.suffix.lower() not in ext_set:
                return True
            data = fp.read_bytes()
            if b"\x00" in data[:8000]:
                chunks_out.append(f"=== FILE: {rel_display} ===\n[skipped: binary]\n")
                return True
            text = data.decode("utf-8", errors="replace")
            if keyword and keyword not in text.lower():
                return True
            take = text[:max_bytes]
            piece = f"=== FILE: {rel_display} ===\n{take}"
            if bytes_used + len(piece.encode("utf-8", errors="replace")) > total_cap:
                chunks_out.append(
                    "[Bundle cap reached — remaining files omitted. Narrow the folder or extensions.]"
                )
                return False
            chunks_out.append(piece)
            bytes_used += len(piece.encode("utf-8", errors="replace"))
            return True

        if isinstance(explicit, list) and explicit:
            for rp in explicit[:max_files]:
                rs = str(rp).strip().replace("\\", "/").lstrip("/")
                if not rs:
                    continue
                fp = _safe_join_under_root(root, rs)
                if not add_file(rs, fp):
                    break
        else:
            raw_abs = payload.get("nexa_permission_abs_targets")
            has_abs = isinstance(raw_abs, list) and raw_abs and str(raw_abs[0]).strip()
            if has_abs:
                b_raw = payload.get("base")
                if not b_raw or not str(b_raw).strip():
                    raise ValueError(
                        "read_multiple_files missing base (required when nexa_permission_abs_targets is set)"
                    )
                try:
                    ref = Path(str(raw_abs[0]).strip()).expanduser().resolve()
                    dirp = Path(str(b_raw).strip()).expanduser().resolve()
                except OSError as e:
                    raise ValueError(
                        "invalid read_multiple base or nexa_permission_abs_targets[0]"
                    ) from e
                if dirp != ref:
                    raise ValueError(
                        "read_multiple_files base must match nexa_permission_abs_targets[0]"
                    )
            elif payload.get("base") and str(payload.get("base")).strip():
                try:
                    dirp = Path(str(payload["base"]).strip()).expanduser().resolve()
                except OSError as e:
                    raise ValueError("invalid read_multiple base path") from e
                try:
                    dirp.relative_to(root.resolve())
                except ValueError as e:
                    raise ValueError(
                        "read_multiple_files base must be under host_executor_work_root"
                    ) from e
            else:
                rel_base = (
                    payload.get("relative_path") or payload.get("relative_dir") or "."
                ).strip() or "."
                dirp = _safe_join_under_root(root, rel_base).resolve()

            _path_allowed_for_io(dirp)
            if not dirp.exists():
                raise ValueError(f"Base path does not exist: {dirp}")
            if not dirp.is_dir():
                if dirp.is_file():
                    raise ValueError(
                        f"{dirp} is a file, not a folder. Use \"read\" with that file path "
                        "instead of folder analysis."
                    )
                raise ValueError(f"Base path must be a directory: {dirp}")

            glob_pat = (payload.get("glob") or "*").strip()
            if len(glob_pat) > 120 or "/" in glob_pat or "\\" in glob_pat:
                raise ValueError("glob invalid for read_multiple_files")
            if glob_pat != "*" and not re.match(r"^[A-Za-z0-9_.*?\-\[\]]+$", glob_pat):
                raise ValueError("invalid glob pattern")

            collected: list[Path] = []
            for p in sorted(dirp.rglob(glob_pat), key=lambda x: str(x).lower()):
                if len(collected) >= max_files * 4:
                    break
                if not p.is_file():
                    continue
                if p.suffix.lower() not in ext_set:
                    continue
                collected.append(p)
                if len(collected) >= max_files:
                    break

            for fp in collected:
                try:
                    rel_disp = str(fp.resolve().relative_to(dirp)).replace("\\", "/")
                except ValueError:
                    continue
                if not add_file(rel_disp, fp):
                    break

        logger.info(
            "host_executor read_multiple_files parts=%s bytes_used=%s",
            len(chunks_out),
            bytes_used,
        )
        return _finalize_output(
            ("\n\n".join(chunks_out) if chunks_out else "(no files matched filters)")[: total_cap + 4000]
        )

    if action == "git_commit":
        msg = (payload.get("commit_message") or "").strip()
        if not msg or len(msg) > 240:
            raise ValueError("commit_message required, max 240 characters")
        if re.search(r"[`$;|&]", msg):
            raise ValueError("commit_message contains forbidden characters")
        code, out, err = _run_argv(["git", "add", "-A"], cwd=exec_root, timeout=60)
        if code != 0:
            return _finalize_output(f"git add failed (exit {code})\n{(out + err)[:4000]}")
        code2, out2, err2 = _run_argv(
            ["git", "commit", "-m", msg],
            cwd=exec_root,
            timeout=120,
        )
        tail = "\n".join(x for x in [out2, err2] if x.strip())
        logger.info("host_executor git_commit ok exit=%s", code2)
        if code2 != 0:
            return _finalize_output(f"git commit failed (exit {code2})\n{tail[:6000]}")
        return _finalize_output((tail or "Committed.")[:8000])

    if action == "git_push":
        argv = argv_for_git_push(payload)
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=min(timeout, 300))
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        logger.info("host_executor git_push ok exit=%s", code)
        if code != 0:
            return _finalize_output(f"git push failed (exit {code})\n{msg}"[:8000])
        return _finalize_output((msg or "Pushed.")[:8000])

    if action == "vercel_projects_list":
        code, out, err = _run_argv(
            ["vercel", "projects", "list"],
            cwd=exec_root,
            timeout=min(timeout, 120),
        )
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        if code != 0:
            return _finalize_output(f"vercel projects list failed (exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000] or "(empty)")

    if action == "vercel_remove":
        argv = argv_for_vercel_remove(payload)
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=min(timeout, 180))
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        logger.info("host_executor vercel_remove ok exit=%s", code)
        if code != 0:
            return _finalize_output(f"vercel remove failed (exit {code})\n{msg}"[:8000])
        return _finalize_output((msg or "Removed.")[:8000])

    raise ValueError(
        f"unknown host_action {action!r}; try: plugin_skill, chain, git_status, run_command, file_read, file_write, "
        "git_commit, git_push, vercel_projects_list, vercel_remove, list_directory, find_files, "
        "read_multiple_files, browser_open, browser_click, browser_fill, browser_screenshot"
    )


def execute_host_executor_job(job: Any) -> str:
    """Entry point from local_tool_worker for ``host-executor`` jobs.

    Validation failures raise ``ValueError`` so the worker marks the job failed.
    """
    from app.core.db import SessionLocal
    from app.services.local_file_intel import maybe_finalize_intel_result

    db = SessionLocal()
    try:
        pl = dict(getattr(job, "payload_json", None) or {})
        raw = execute_payload(pl, db=db, job=job)
        return maybe_finalize_intel_result(pl, raw)
    finally:
        db.close()


def proposed_risk_level(payload: dict[str, Any]) -> str:
    """Suggest risk for UI / policy (all host-executor jobs still require approval in AgentJobService)."""
    action = (payload.get("host_action") or "").strip().lower()
    if action == "chain":
        return "high"
    if action in ("file_write", "git_commit", "git_push", "vercel_remove"):
        return "high"
    if action == "vercel_projects_list":
        return "normal"
    if action == "run_command":
        if (payload.get("command") or "").strip():
            return "high"
        return "normal"
    if action in ("list_directory", "find_files"):
        return "low"
    if action == "show_workspace_root":
        return "low"
    if action == "read_multiple_files":
        return "normal"
    if action in ("browser_open",):
        return "high"
    if action in ("browser_click", "browser_fill", "browser_screenshot"):
        return "normal"
    return "low"
