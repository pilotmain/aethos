"""
User-friendly **roles** (maps to orchestration ``domain`` keys on :class:`~app.services.sub_agent_registry.SubAgent`).

Technical term ``domain`` → user-facing **Role** (what a team member specializes in).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """A specialization area (git, Vercel, …) shown as a *role* in Mission Control."""

    key: str
    user_label: str
    description: str
    default_skills: tuple[str, ...]


# Keys must stay aligned with spawn_agent ``domain`` + sub_agent_registry defaults where possible.
KNOWN_ROLES: Final[dict[str, RoleDefinition]] = {
    "git": RoleDefinition(
        key="git",
        user_label="Git & repositories",
        description="Branches, commits, pushes, and Git hosting workflows.",
        default_skills=("status", "clone", "commit", "push", "pull"),
    ),
    "vercel": RoleDefinition(
        key="vercel",
        user_label="Vercel & deployments",
        description="Preview and production deploys, project settings, logs.",
        default_skills=("list", "deploy", "remove", "logs"),
    ),
    "railway": RoleDefinition(
        key="railway",
        user_label="Railway & infra",
        description="Service lifecycle and operational checks on Railway.",
        default_skills=("up", "down", "logs", "status"),
    ),
    "test": RoleDefinition(
        key="test",
        user_label="Tests & quality",
        description="Running and interpreting automated tests.",
        default_skills=("pytest", "unit", "integration", "lint"),
    ),
    "general": RoleDefinition(
        key="general",
        user_label="General assistant",
        description="Flexible support without a fixed toolchain.",
        default_skills=("plan", "research", "summarize"),
    ),
}


def normalize_role_key(raw: str) -> str:
    """Normalize user or internal input to a registry ``domain`` key."""
    k = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not k:
        return "general"
    aliases = {
        "github": "git",
        "gh": "git",
        "deploy": "vercel",
        "qa": "test",
        "quality": "test",
    }
    k = aliases.get(k, k)
    return k if k in KNOWN_ROLES else "general"


def role_definition(key: str) -> RoleDefinition:
    """Return the definition for ``key``, falling back to **general**."""
    k = normalize_role_key(key)
    return KNOWN_ROLES.get(k) or KNOWN_ROLES["general"]


def role_label(key: str) -> str:
    """Short user-facing title for a role key."""
    return role_definition(key).user_label


__all__ = [
    "KNOWN_ROLES",
    "RoleDefinition",
    "normalize_role_key",
    "role_definition",
    "role_label",
]
