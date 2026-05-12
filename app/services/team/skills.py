# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
**Skills** — user-facing wording for capability tokens stored on sub-agents.

Technical ``capabilities`` list → skills shown in Mission Control (commit, deploy, …).
"""

from __future__ import annotations

from typing import Final

from app.services.team.roles import role_definition

# Friendly labels for common capability tokens (extend as new domains add verbs).
SKILL_LABELS: Final[dict[str, str]] = {
    "status": "check status",
    "clone": "clone repos",
    "commit": "commit changes",
    "push": "push branches",
    "pull": "pull updates",
    "list": "list projects",
    "deploy": "deploy",
    "remove": "remove deployments",
    "logs": "view logs",
    "up": "start services",
    "down": "stop services",
    "pytest": "run pytest",
    "unit": "unit tests",
    "integration": "integration tests",
    "lint": "lint code",
    "plan": "plan work",
    "research": "research",
    "summarize": "summarize",
}


def default_skills_for_role(role_key: str) -> list[str]:
    """Capability tokens used when the user does not supply a custom list."""
    return list(role_definition(role_key).default_skills)


def merge_skills(base: list[str], extra: list[str]) -> list[str]:
    """Union preserve-order (first occurrence wins)."""
    out: list[str] = []
    seen: set[str] = set()
    for s in list(base) + list(extra):
        t = (s or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def skill_label(token: str) -> str:
    """Human label for one capability token."""
    t = (token or "").strip().lower()
    return SKILL_LABELS.get(t, t.replace("_", " ") if t else "")


def format_skills_phrase(skills: list[str]) -> str:
    """Comma-separated friendly skill list for UI copy."""
    labels = [skill_label(s) for s in skills if (s or "").strip()]
    return ", ".join(labels) if labels else "—"


__all__ = [
    "SKILL_LABELS",
    "default_skills_for_role",
    "format_skills_phrase",
    "merge_skills",
    "skill_label",
]
