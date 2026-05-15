# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight dependency inference for linear and fan-out step lists."""

from __future__ import annotations

from typing import Any


def add_linear_dependencies(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chain ``depends_on`` so each step waits on the previous step_id (best-effort)."""
    out: list[dict[str, Any]] = []
    prev: str | None = None
    for s in steps:
        if not isinstance(s, dict):
            continue
        row = dict(s)
        deps = list(row.get("depends_on") or []) if isinstance(row.get("depends_on"), list) else []
        if prev and prev not in deps:
            deps.append(prev)
        row["depends_on"] = deps
        out.append(row)
        prev = str(row.get("step_id") or "") or prev
    return out
