# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime calmness copy lock — replace panic wording (Phase 4 Step 21)."""

from __future__ import annotations

import re
from typing import Any

REPLACEMENTS = {
    "failed": "needs attention",
    "error": "operational notice",
    "fatal": "unrecoverable",
    "crashed": "stopped unexpectedly",
    "broken": "temporarily unavailable",
}


def calm_operator_message(message: str) -> str:
    out = message
    for src, dst in REPLACEMENTS.items():
        out = re.sub(rf"\b{src}\b", dst, out, flags=re.I)
    return out


def build_runtime_calmness_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    resilience = truth.get("runtime_resilience") or {}
    status = resilience.get("status") or "healthy"
    narrative = "AethOS runtime is operating normally."
    if status in ("degraded", "partial", "stale"):
        narrative = "Mission Control is operating in partial readiness while runtime intelligence stabilizes."
    if truth.get("db_lock_waiting"):
        narrative = "AethOS is waiting for database coordination — other panels may still be available."
    return {
        "runtime_calmness_lock": {
            "calm_narrative": narrative,
            "avoid_panic_wording": True,
            "preferred_phrases": [
                "recovering",
                "reconnecting",
                "partial readiness",
                "stabilizing",
                "waiting for runtime ownership",
            ],
            "status": status,
            "locked": True,
            "phase": "phase4_step21",
            "bounded": True,
        }
    }
