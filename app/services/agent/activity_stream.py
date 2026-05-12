# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control activity feed — delegates to :class:`~app.services.agent.activity_tracker.AgentActivityTracker`."""

from __future__ import annotations

from typing import Any

from app.services.agent.activity_tracker import get_activity_tracker


def recent_activity_for_agents(
    agent_ids: list[str],
    *,
    hours: int = 24,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Latest orchestration actions across the given agent ids."""
    return get_activity_tracker().get_global_activity(agent_ids, hours=hours, limit=limit)


__all__ = ["recent_activity_for_agents"]
