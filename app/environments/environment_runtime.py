# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight environment lifecycle touches (counts, timestamps)."""

from __future__ import annotations

from typing import Any

from app.environments.environment_registry import ensure_environment, get_environment
from app.runtime.runtime_state import utc_now_iso


def touch_deployment_count(st: dict[str, Any], environment_id: str, *, delta: int = 1) -> None:
    row = ensure_environment(st, str(environment_id))
    m = row.setdefault("metrics", {})
    if not isinstance(m, dict):
        row["metrics"] = {}
        m = row["metrics"]
    m["active_deployments"] = max(0, int(m.get("active_deployments") or 0) + int(delta))


def mark_updated(st: dict[str, Any], environment_id: str) -> None:
    row = get_environment(st, environment_id)
    if row:
        row["updated_at"] = utc_now_iso()
