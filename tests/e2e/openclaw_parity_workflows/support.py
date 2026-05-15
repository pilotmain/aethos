# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Shared fixtures/helpers for OpenClaw parity workflow benchmarks."""

from __future__ import annotations

from typing import Any, Callable

from app.orchestration import runtime_dispatcher
from app.orchestration import task_registry
from app.runtime.runtime_state import save_runtime_state


def configure_isolated_runtime(monkeypatch: Any, tmp_path: Any) -> None:
    """Isolated ``aethos.json`` + workspace root (file/shell tools)."""
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(ws))


def dispatch_until_task_terminal(
    st: dict[str, Any],
    task_id: str,
    *,
    max_rounds: int = 80,
) -> str:
    """Drive ``dispatch_once`` until the task reaches a terminal workflow state."""
    for _ in range(max_rounds):
        runtime_dispatcher.dispatch_once(st)
        save_runtime_state(st)
        t = task_registry.get_task(st, task_id)
        if t and str(t.get("state") or "") in ("completed", "failed", "cancelled"):
            return str(t.get("state") or "")
    raise AssertionError(f"task {task_id} did not reach terminal state within {max_rounds} rounds")
