# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Allowlisted actions and commands for approved sandbox execution (workspace-scoped)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# First argv token after shlex split (no shell).
_ALLOWED_ARGV0: frozenset[str] = frozenset(
    {
        "npm",
        "npx",
        "yarn",
        "pnpm",
        "git",
        "python",
        "python3",
        "node",
        "ls",
        "cat",
        "echo",
        "mkdir",
        "touch",
        "cp",
        "mv",
        "pwd",
        "head",
        "tail",
        "wc",
    }
)

_BLOCKED_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("rm -rf", "rm -rf"),
    ("rm ", "rm "),  # any rm — too destructive for v1
    ("sudo", "sudo"),
    ("chmod 777", "chmod 777"),
    ("dd if=", "dd"),
    ("mkfs", "mkfs"),
    ("curl", "curl"),
    ("wget", "wget"),
    ("bash -c", "bash -c"),
    ("sh -c", "sh -c"),
    ("eval(", "eval"),
    ("$(", "command substitution"),
    ("`", "backtick"),
    ("|", "pipe"),
    (";", "semicolon"),
    ("&&", "&&"),
    ("||", "||"),
    ("\n", "newline"),
    ("\r", "newline"),
)

_ALLOWED_ACTION_TYPES: frozenset[str] = frozenset(
    {"read_file", "write_file", "run_command", "open_browser"}
)


def _under_workspace(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _safe_rel_path(raw: str, root: Path) -> tuple[Path | None, str]:
    p = (raw or "").strip().replace("\\", "/").lstrip("/")
    if not p or ".." in Path(p).parts:
        return None, "Path must be relative and cannot contain '..'"
    full = (root / p).resolve()
    if not _under_workspace(full, root):
        return None, "Path escapes workspace root"
    return full, "OK"


def is_action_allowed(
    action_type: str,
    params: dict[str, Any],
    *,
    workspace_root: Path,
    max_file_bytes: int,
) -> tuple[bool, str]:
    if action_type not in _ALLOWED_ACTION_TYPES:
        return False, f"Action type {action_type!r} is not allowed"

    if action_type in ("read_file", "write_file"):
        rel = str(params.get("path") or "").strip()
        target, err = _safe_rel_path(rel, workspace_root)
        if target is None:
            return False, err
        if action_type == "write_file":
            content = params.get("content")
            if not isinstance(content, str):
                return False, "write_file requires string content"
            if len(content.encode("utf-8", errors="replace")) > max_file_bytes:
                return False, f"Content exceeds max size ({max_file_bytes} bytes)"
        return True, "OK"

    if action_type == "run_command":
        cmd = str(params.get("command") or "").strip()
        if not cmd:
            return False, "Empty command"
        low = cmd.lower()
        for needle, label in _BLOCKED_SUBSTRINGS:
            if needle.lower() in low:
                return False, f"Blocked pattern: {label}"
        import shlex

        try:
            parts = shlex.split(cmd)
        except ValueError as e:
            return False, f"Invalid command quoting: {e}"
        if not parts:
            return False, "Could not parse command"
        argv0 = parts[0].lower()
        if argv0 not in _ALLOWED_ARGV0:
            return False, f"Command {argv0!r} is not in the allowlist"
        cwd_raw = str(params.get("cwd") or "").strip() or "."
        cwd_full, cerr = _safe_rel_path(cwd_raw, workspace_root)
        if cwd_full is None:
            return False, cerr
        if not cwd_full.is_dir():
            return False, "cwd is not a directory under the workspace"
        return True, "OK"

    if action_type == "open_browser":
        url = str(params.get("url") or "").strip()
        if not url:
            return False, "Empty URL"
        lowu = url.lower()
        if lowu.startswith("file://"):
            rest = url[7:]
            if rest.startswith("//"):
                rest = rest[2:]
            path = Path(rest.split("?", 1)[0])
            if not path.is_absolute():
                path = (workspace_root / path).resolve()
            if not _under_workspace(path, workspace_root):
                return False, "file:// URL must stay under the workspace"
            return True, "OK"
        if "localhost" in lowu or "127.0.0.1" in lowu:
            if re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?(/|$)", lowu):
                return True, "OK"
            return False, "URL host must be localhost or 127.0.0.1 only for this action"
        return False, "open_browser only allows localhost / 127.0.0.1 / file:// under workspace"

    return False, "Unknown action"


def validate_plan_actions(
    plan: dict[str, Any],
    *,
    workspace_root: Path,
    max_file_bytes: int,
) -> tuple[bool, list[str]]:
    """Validate every action in a plan before any mutation."""
    errs: list[str] = []
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        errs.append("Plan must contain a non-empty actions array")
        return False, errs
    for i, act in enumerate(actions):
        if not isinstance(act, dict):
            errs.append(f"Action {i} is not an object")
            continue
        typ = str(act.get("type") or "").strip()
        params = act.get("params")
        if not isinstance(params, dict):
            errs.append(f"Action {i} ({typ}) missing params object")
            continue
        ok, reason = is_action_allowed(typ, params, workspace_root=workspace_root, max_file_bytes=max_file_bytes)
        if not ok:
            errs.append(f"Action {i} ({typ}): {reason}")
    return (len(errs) == 0, errs)
