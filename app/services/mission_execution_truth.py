# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Detect non-verifying mission agent outputs (e.g. heartbeat stubs) — P0 execution truth.
"""

from __future__ import annotations

from typing import Any


def agent_output_is_unverified_stub(output: Any) -> bool:
    """
    True when output does not constitute evidence of real work (blocked counts as real signal).

    Heartbeat-only JSON success is **not** proof of hosted-service remediation.
    """
    if output is None:
        return True
    if isinstance(output, dict):
        if output.get("type") == "blocked":
            return False
        if output.get("type") == "heartbeat" and output.get("ok") is True:
            return True
        if output.get("type") == "empty":
            return True
        # Any other structured payload counts as non-stub for mission UX.
        return False
    # Non-dict outputs treated as carrying content.
    return False


def mission_agents_execution_verified(agents: list[dict[str, Any]]) -> bool:
    """True if at least one agent produced non-stub output."""
    if not agents:
        return False
    return any(not agent_output_is_unverified_stub(a.get("output")) for a in agents)


__all__ = ["agent_output_is_unverified_stub", "mission_agents_execution_verified"]
