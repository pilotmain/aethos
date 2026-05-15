"""Deterministic operator text → execution plan steps (OpenClaw workflow parity, Phase 1)."""

from __future__ import annotations

import re
import uuid
from typing import Any


def _shell_step(command: str, *, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "shell",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "shell", "input": {"command": command}},
        "retryable": True,
        "max_retries": 3,
    }


def _noop_step(*, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "noop",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "noop", "input": {}},
        "retryable": False,
    }


def _list_step(*, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "workspace_list",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "workspace_list", "input": {}},
        "retryable": False,
    }


def _search_step(sub: str, *, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "workspace_search",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "workspace_search", "input": {"substring": sub}},
        "retryable": False,
    }


def _deploy_step(*, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "deploy",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "deploy", "input": {"stage": "apply"}},
        "retryable": False,
    }


def _write_step(path: str, content: str, *, step_id: str | None = None) -> dict[str, Any]:
    sid = step_id or f"s_{uuid.uuid4().hex[:12]}"
    return {
        "step_id": sid,
        "type": "file_write",
        "status": "queued",
        "depends_on": [],
        "tool": {"name": "file_write", "input": {"path": path, "content": content}},
        "retryable": False,
    }


def build_steps_from_operator_text(text: str) -> list[dict[str, Any]]:
    raw = (text or "").strip()
    low = raw.lower()

    if raw.lower().startswith("workflow:"):
        raw = raw[len("workflow:") :].strip()
        low = raw.lower()

    if not raw:
        return [_noop_step()]

    if "compileall" in low:
        return [_shell_step("python -m compileall -q app")]

    if "list workspace" in low or low in ("workspace list", "list files", "ls workspace"):
        return [_list_step()]

    m = re.search(r"search\s+workspace\s+for\s+(.+)", low)
    if m:
        return [_search_step(m.group(1).strip().strip("'\""))]

    if low.startswith("write file "):
        rest = raw[len("write file ") :].strip()
        parts = rest.split(None, 1)
        if len(parts) == 2:
            return [_write_step(parts[0], parts[1])]

    if low == "deploy" or low.startswith("deploy "):
        return [_deploy_step()]

    if low.startswith("echo ") or low == "echo":
        return [_shell_step(raw if low.startswith("echo ") else "echo")]

    return [_shell_step(f"echo {raw[:500]}")]
