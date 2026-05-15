# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cooperative pause/cancel checks for long dev runs (OpenClaw-style run steering)."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun

SteeringOutcome = str  # ok | cancelled | paused_timeout | missing


def cooperate_run_steering(
    db: Session,
    run_id: str,
    *,
    wait_on_paused: bool = True,
    max_wait_seconds: float = 86_400.0,
    poll_seconds: float = 0.5,
) -> SteeringOutcome:
    """
    Honor ``paused`` / ``cancelled`` on a dev run.

    When ``wait_on_paused`` is true, blocks until resumed, cancelled, or timeout.
    """
    started = time.monotonic()
    while True:
        db.expire_all()
        run = db.get(NexaDevRun, run_id)
        if run is None:
            return "missing"
        status = (run.status or "").strip().lower()
        if status == "cancelled":
            return "cancelled"
        if status != "paused":
            return "ok"
        if not wait_on_paused:
            return "paused_timeout"
        if time.monotonic() - started >= max_wait_seconds:
            return "paused_timeout"
        time.sleep(max(poll_seconds, 0.05))


__all__ = ["cooperate_run_steering"]
