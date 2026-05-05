"""
Phase 26 — **Team management** (Mission Control, user-friendly naming).

Maps orchestration primitives to product language:

* ``SubAgent`` → :class:`team.member.TeamMember`
* ``AgentRegistry`` → :class:`team.roster.TeamRoster`
* ``domain`` → roles (:mod:`team.roles`)
* ``capabilities`` → skills (:mod:`team.skills`)
"""

from app.services.team.member import TeamMember
from app.services.team.roster import TeamRoster
from app.services.team.roles import (
    KNOWN_ROLES,
    RoleDefinition,
    normalize_role_key,
    role_definition,
    role_label,
)
from app.services.team.skills import (
    SKILL_LABELS,
    default_skills_for_role,
    format_skills_phrase,
    merge_skills,
    skill_label,
)

__all__ = [
    "KNOWN_ROLES",
    "RoleDefinition",
    "SKILL_LABELS",
    "TeamMember",
    "TeamRoster",
    "default_skills_for_role",
    "format_skills_phrase",
    "merge_skills",
    "normalize_role_key",
    "role_definition",
    "role_label",
    "skill_label",
]
