# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight corruption signals beyond full integrity DAG checks."""

from __future__ import annotations

from typing import Any

from app.orchestration import task_queue


def scan_queue_duplicates_and_shape(st: dict[str, Any]) -> dict[str, Any]:
    """Count duplicate task ids per queue and non-list queue shapes."""
    dup_total = 0
    bad_shape: list[str] = []
    per_queue: dict[str, int] = {}
    for name in task_queue.QUEUE_NAMES:
        q = st.get(name)
        if not isinstance(q, list):
            bad_shape.append(name)
            continue
        seen: set[str] = set()
        dups = 0
        for x in q:
            s = str(x)
            if not s:
                continue
            if s in seen:
                dups += 1
            else:
                seen.add(s)
        per_queue[name] = dups
        dup_total += dups
    return {
        "duplicate_queue_entries": dup_total,
        "per_queue_duplicates": per_queue,
        "non_list_queues": bad_shape,
    }
