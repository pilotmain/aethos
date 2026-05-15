# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Typed environment variables bag (non-secret metadata; operator-provided)."""

from __future__ import annotations

from typing import Any

from app.environments.environment_registry import ensure_environment


def set_variables(st: dict[str, Any], environment_id: str, variables: dict[str, Any]) -> dict[str, Any]:
    row = ensure_environment(st, str(environment_id))
    cur = row.setdefault("variables", {})
    if not isinstance(cur, dict):
        row["variables"] = {}
        cur = row["variables"]
    for k, v in (variables or {}).items():
        cur[str(k)[:200]] = v
    return cur


def get_variables(st: dict[str, Any], environment_id: str) -> dict[str, Any]:
    row = ensure_environment(st, str(environment_id))
    v = row.get("variables")
    return dict(v) if isinstance(v, dict) else {}
