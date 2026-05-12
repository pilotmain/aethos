# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Delegation caps and gateway line parsing (Phase 16a)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.custom_agents import normalize_agent_key

logger = logging.getLogger(__name__)

_HANDLE_TOKEN = re.compile(r"^@([a-zA-Z][a-zA-Z0-9_-]{0,62})$")


@dataclass(frozen=True)
class OrchestrationPolicy:
    max_delegates: int
    max_parallel: int
    timeout_ms: int
    require_approval: bool


def load_policy() -> OrchestrationPolicy:
    s = get_settings()
    return OrchestrationPolicy(
        max_delegates=min(max(int(getattr(s, "nexa_orchestration_max_delegates", 5) or 5), 1), 24),
        max_parallel=min(max(int(getattr(s, "nexa_orch_max_parallel_agents", 3) or 3), 1), 12),
        timeout_ms=min(max(int(getattr(s, "nexa_orch_delegation_timeout_ms", 30000) or 30000), 1000), 600_000),
        require_approval=bool(getattr(s, "nexa_orch_require_approval", False)),
    )


def normalize_agent_handles(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for r in raw:
        h = normalize_agent_key((r or "").strip())
        if not h or h in seen:
            continue
        seen.add(h)
        out.append(h)
    return out


def validate_handles(handles: list[str], *, policy: OrchestrationPolicy | None = None) -> tuple[list[str], str | None]:
    """Return (normalized list, error message) — error when invalid."""
    pol = policy or load_policy()
    norm = normalize_agent_handles(handles)
    if len(norm) < 2:
        return [], "At least two distinct agent handles are required."
    if len(norm) > pol.max_delegates:
        return [], f"Too many agents (max {pol.max_delegates} per delegation)."
    return norm, None


def parse_gateway_delegate(text: str) -> tuple[list[str], str, bool] | None:
    """
    Parse `/delegate [parallel] @a @b … goal text`.

    Returns None when this is not a delegate command.
    """
    t = (text or "").strip()
    if not t.lower().startswith("/delegate"):
        return None
    rest = t[len("/delegate") :].strip()
    if not rest:
        return None

    parallel = False
    low = rest.lower()
    if low.startswith("parallel"):
        parallel = True
        rest = rest[8:].strip()

    parts = rest.split()
    handles: list[str] = []
    idx = 0
    for i, p in enumerate(parts):
        m = _HANDLE_TOKEN.match(p.strip())
        if m:
            handles.append(m.group(1))
            idx = i + 1
        else:
            break

    if len(handles) < 2:
        return None

    goal = " ".join(parts[idx:]).strip()
    if not goal and "\n" in text:
        goal = text.split("\n", 1)[1].strip()
    if not goal:
        goal = "(no goal text — refine your /delegate message)"

    norm, err = validate_handles(handles)
    if err:
        logger.info(
            "orchestration gateway parse rejected: %s",
            err,
            extra={"nexa_event": "orchestration_parse_reject"},
        )
        return None

    return norm, goal, parallel


__all__ = [
    "OrchestrationPolicy",
    "load_policy",
    "normalize_agent_handles",
    "parse_gateway_delegate",
    "validate_handles",
]
