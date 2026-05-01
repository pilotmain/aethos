"""
Mission text parser — strict ``@handle:`` documents first, then loose ``Role: task`` lines.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.swarm.mission_parser import parse_mission as strict_parse

_RE_LOOSE_AT_TASK = re.compile(r"^\s*@([\w-]{2,64})\s*:\s*(.+)$")


def parse_mission_text(text: str) -> dict[str, Any] | None:
    """Strict swarm format only (no loose fallback)."""
    return strict_parse(text)


def parse_loose_mission(text: str) -> dict[str, Any] | None:
    """Per-agent lines ``Role: task`` with optional ``Mission: \"title\"``; sequential dependencies."""
    lines = text.splitlines()

    tasks: list[dict[str, Any]] = []
    title = "Untitled Mission"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        low = line.lower()
        if low.startswith("mission:"):
            title = line.split(":", 1)[-1].strip().strip('"').strip("'")
            continue

        m_at = _RE_LOOSE_AT_TASK.match(line)
        if m_at:
            task_body = (m_at.group(2) or "").strip()
            if len(task_body) < 5:
                continue
            tasks.append(
                {
                    "role": m_at.group(1),
                    "task": task_body,
                    "depends_on": [],
                }
            )
            continue

        if ":" not in line:
            continue

        role, task = line.split(":", 1)
        role = role.strip()
        task = task.strip()

        if role.lower() == "mission":
            title = task.strip('"').strip("'") if task else title
            continue

        if len(task) < 5:
            continue

        tasks.append(
            {
                "role": role,
                "task": task,
                "depends_on": [],
            }
        )

    if not tasks:
        return None

    for i in range(1, len(tasks)):
        tasks[i]["depends_on"] = [tasks[i - 1]["role"]]

    return {
        "title": title,
        "single_cycle": True,
        "agents": tasks,
    }


def parse_mission(text: str) -> dict[str, Any] | None:
    """Strict mission document if possible; otherwise loose ``Role:`` lines."""
    mission = strict_parse(text or "")
    if mission:
        return mission
    return parse_loose_mission(text or "")
