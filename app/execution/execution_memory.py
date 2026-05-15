"""Persistent execution memory (outputs + continuation context)."""

from __future__ import annotations

from typing import Any

from app.execution import execution_plan


def memory_store(st: dict[str, Any]) -> dict[str, Any]:
    root = execution_plan.execution_root(st)
    m = root.setdefault("memory", {})
    if not isinstance(m, dict):
        root["memory"] = {}
        return root["memory"]
    return m


def append_output(st: dict[str, Any], task_id: str, key: str, value: Any) -> None:
    m = memory_store(st)
    bucket = m.setdefault(task_id, {"outputs": [], "context": {}, "continuation": {}})
    if not isinstance(bucket, dict):
        m[task_id] = {"outputs": [], "context": {}, "continuation": {}}
        bucket = m[task_id]
    bucket.setdefault("outputs", []).append({"key": key, "value": value})


def set_continuation(st: dict[str, Any], task_id: str, **fields: Any) -> None:
    m = memory_store(st)
    b = m.setdefault(task_id, {"outputs": [], "context": {}, "continuation": {}})
    if not isinstance(b, dict):
        m[task_id] = {"outputs": [], "context": {}, "continuation": {}}
        b = m[task_id]
    cont = b.setdefault("continuation", {})
    if not isinstance(cont, dict):
        b["continuation"] = {}
        cont = b["continuation"]
    cont.update(fields)


def get_memory(st: dict[str, Any], task_id: str) -> dict[str, Any]:
    m = memory_store(st)
    b = m.get(task_id)
    return dict(b) if isinstance(b, dict) else {}
