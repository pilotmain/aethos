"""
**Team member** view model — wraps :class:`~app.services.sub_agent_registry.SubAgent`.

Technical ``SubAgent`` → user-facing **Team Member** (name, role, skills, status).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.sub_agent_registry import AgentStatus, SubAgent
from app.services.team.roles import role_label
from app.services.team.skills import format_skills_phrase


def _status_display(status: AgentStatus) -> tuple[str, str]:
    """(emoji, short user-facing phrase)."""
    if status == AgentStatus.IDLE:
        return "🟢", "Available"
    if status == AgentStatus.BUSY:
        return "🔴", "Busy"
    if status == AgentStatus.ERROR:
        return "⚠️", "Needs attention"
    if status == AgentStatus.TERMINATED:
        return "⚫", "Removed"
    return "⚪", status.value


@dataclass(slots=True)
class TeamMember:
    """Serializable Mission Control row for one orchestration agent."""

    member_id: str
    display_name: str
    role_key: str
    role_title: str
    skills: list[str]
    skills_phrase: str
    status: AgentStatus
    status_emoji: str
    status_text: str
    chat_scope_id: str
    work_hours_used: int
    work_hours_cap: int
    current_task: str | None
    trusted: bool
    metadata: dict[str, Any]

    @classmethod
    def from_sub_agent(
        cls,
        agent: SubAgent,
        *,
        work_hours_used: int = 0,
        work_hours_cap: int = 1000,
    ) -> TeamMember:
        emoji, text = _status_display(agent.status)
        md = agent.metadata or {}
        task = md.get("current_task")
        if isinstance(task, str) and task.strip():
            current_task: str | None = task.strip()
        else:
            current_task = None
        skills = list(agent.capabilities or [])
        return cls(
            member_id=agent.id,
            display_name=agent.name,
            role_key=agent.domain,
            role_title=role_label(agent.domain),
            skills=skills,
            skills_phrase=format_skills_phrase(skills),
            status=agent.status,
            status_emoji=emoji,
            status_text=text,
            chat_scope_id=agent.parent_chat_id,
            work_hours_used=max(0, int(work_hours_used)),
            work_hours_cap=max(1, int(work_hours_cap)),
            current_task=current_task,
            trusted=bool(agent.trusted),
            metadata=dict(md),
        )

    def one_line_summary(self) -> str:
        """Single-line summary for compact listings."""
        task = f' — "{self.current_task}"' if self.current_task else ""
        return f"{self.status_emoji} {self.display_name} ({self.role_title}){task}"

    def to_public_dict(self) -> dict[str, Any]:
        """JSON-friendly payload for APIs (no secrets)."""
        return {
            "member_id": self.member_id,
            "display_name": self.display_name,
            "role_key": self.role_key,
            "role_title": self.role_title,
            "skills": self.skills,
            "skills_phrase": self.skills_phrase,
            "status": self.status.value,
            "status_emoji": self.status_emoji,
            "status_text": self.status_text,
            "chat_scope_id": self.chat_scope_id,
            "work_hours_used": self.work_hours_used,
            "work_hours_cap": self.work_hours_cap,
            "current_task": self.current_task,
            "trusted": self.trusted,
        }


__all__ = ["TeamMember"]
