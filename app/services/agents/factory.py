# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Create lightweight agent specs for orchestration (handles unknown user-defined agents)."""

from __future__ import annotations

from typing import Any


def create_agent(handle: str, role: str, tools: list[str]) -> dict[str, Any]:
    """Return a serializable agent descriptor (roles/tools only — runtime supplies tasks)."""
    h = (handle or "").strip().lstrip("@").replace(" ", "_").lower()
    return {
        "handle": h or "agent",
        "role": (role or "").strip() or h or "agent",
        "tools": [str(t).strip() for t in (tools or []) if str(t).strip()],
    }


__all__ = ["create_agent"]
