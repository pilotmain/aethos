# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive retry bookkeeping (works with execution retry scheduler)."""

from __future__ import annotations

from typing import Any

from app.planning import replanning_runtime


def notify_retry_scheduled(
    st: dict[str, Any],
    *,
    task_id: str,
    plan_id: str,
    step_id: str,
    reason: str,
) -> None:
    replanning_runtime.on_adaptive_retry(st, task_id=task_id, plan_id=plan_id, step_id=step_id, reason=reason)
