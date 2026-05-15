# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous multi-agent coordination (OpenClaw parity — JSON-backed)."""

from app.agents import agent_assignment_policy
from app.agents import agent_coordination
from app.agents import agent_delegation
from app.agents import agent_events
from app.agents import agent_health
from app.agents import agent_loops
from app.agents import agent_recovery
from app.agents import agent_registry
from app.agents import agent_runtime
from app.agents import agent_supervisor

__all__ = [
    "agent_assignment_policy",
    "agent_coordination",
    "agent_delegation",
    "agent_events",
    "agent_health",
    "agent_loops",
    "agent_recovery",
    "agent_registry",
    "agent_runtime",
    "agent_supervisor",
]
