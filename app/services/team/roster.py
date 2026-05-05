"""
**Team roster** — user-facing API over :class:`~app.services.sub_agent_registry.AgentRegistry`.

Technical ``AgentRegistry`` → **Team Roster** (list, add, remove members per chat scope).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent
from app.services.team.member import TeamMember
from app.services.team.roles import normalize_role_key
from app.services.team.skills import default_skills_for_role, merge_skills


class TeamRoster:
    """
    Mission Control facade: add/remove/list **team members** backed by the orchestration registry.

    * **Add member** → ``spawn_agent``
    * **Remove member** → ``terminate_agent`` (hidden from active roster)
    """

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry if registry is not None else AgentRegistry()

    def add_member(
        self,
        name: str,
        role: str,
        chat_id: str,
        skills: list[str] | None = None,
        extra_skills: list[str] | None = None,
        *,
        trusted: bool = False,
    ) -> TeamMember | None:
        """
        Invite a team member: ``role`` is the specialization (git / vercel / …).

        ``extra_skills`` are merged onto defaults when ``skills`` is None.
        """
        role_key = normalize_role_key(role)
        if skills is None:
            caps = default_skills_for_role(role_key)
            caps = merge_skills(caps, list(extra_skills or []))
        else:
            caps = merge_skills(list(skills), list(extra_skills or []))

        sub = self._registry.spawn_agent(
            name.strip(),
            role_key,
            chat_id,
            capabilities=caps,
            trusted=trusted,
        )
        return TeamMember.from_sub_agent(sub) if sub else None

    def remove_member(self, member_id: str) -> bool:
        """Remove a member from the active team (terminates orchestration handle)."""
        return self._registry.terminate_agent(member_id)

    def get_member(self, member_id: str) -> TeamMember | None:
        sub = self._registry.get_agent(member_id)
        if sub is None or sub.status == AgentStatus.TERMINATED:
            return None
        return TeamMember.from_sub_agent(sub)

    def get_member_by_name(self, name: str, chat_id: str) -> TeamMember | None:
        sub = self._registry.get_agent_by_name(name.strip(), chat_id)
        if sub is None or sub.status == AgentStatus.TERMINATED:
            return None
        return TeamMember.from_sub_agent(sub)

    def list_members(self, chat_id: str, *, include_removed: bool = False) -> list[TeamMember]:
        """All team members in this chat scope."""
        raw = self._registry.list_agents(chat_id)
        if not include_removed:
            raw = [a for a in raw if a.status != AgentStatus.TERMINATED]
        return [TeamMember.from_sub_agent(a) for a in raw]

    def set_member_task(self, member_id: str, description: str | None) -> bool:
        """Attach a user-visible *current task* string (stored in agent metadata)."""
        agent = self._registry.get_agent(member_id)
        if not agent or agent.status == AgentStatus.TERMINATED:
            return False
        md = dict(agent.metadata or {})
        if description and description.strip():
            md["current_task"] = description.strip()
        else:
            md.pop("current_task", None)
        agent.metadata = md
        agent.touch()
        return True

    def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Detailed agent status for Mission Control / APIs (includes current task line)."""
        agent = self._registry.get_agent(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        md = dict(agent.metadata or {})
        cur = md.get("current_task")
        la = getattr(agent, "last_active", None)
        last_active_iso = None
        if isinstance(la, (int, float)):
            last_active_iso = datetime.fromtimestamp(float(la), tz=timezone.utc).isoformat()
        created_iso = None
        ca = getattr(agent, "created_at", None)
        if isinstance(ca, (int, float)):
            created_iso = datetime.fromtimestamp(float(ca), tz=timezone.utc).isoformat()
        return {
            "id": agent.id,
            "name": agent.name,
            "domain": agent.domain,
            "status": agent.status.value,
            "current_task": cur,
            "last_active": last_active_iso,
            "created_at": created_iso,
            "capabilities": list(agent.capabilities or []),
        }

    def stats(self, chat_id: str | None = None) -> dict[str, Any]:
        """Passthrough orchestration stats (technical keys preserved)."""
        return self._registry.get_stats(chat_id)

    def format_roster_message(
        self,
        chat_id: str,
        *,
        team_hours_used: int | None = None,
        team_hours_cap: int | None = None,
    ) -> str:
        """
        Paperclip-style Mission Control text for ``/team`` style commands.

        Work hours are placeholders until Phase 28 connects real usage meters.
        """
        members = self.list_members(chat_id)
        lines: list[str] = [
            "👥 YOUR AI TEAM",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]
        if not members:
            lines.extend(
                [
                    "No team members yet.",
                    "",
                    "Add members when orchestration is enabled (spawn from gateway or API).",
                    "",
                ]
            )
        for m in members:
            lines.append(f"🤖 {m.display_name} — {m.role_title}")
            lines.append(f"   Skills: {m.skills_phrase}")
            if m.current_task:
                lines.append(f"   Status: {m.status_emoji} {m.status_text} — \"{m.current_task}\"")
            else:
                lines.append(f"   Status: {m.status_emoji} {m.status_text}")
            lines.append(f"   Work hours: {m.work_hours_used}/{m.work_hours_cap} this month")
            lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if team_hours_used is not None and team_hours_cap is not None:
            pct = int(100 * team_hours_used / team_hours_cap) if team_hours_cap else 0
            lines.extend(
                [
                    "",
                    f"📊 This month: {team_hours_used} / {team_hours_cap} team hours used",
                    f"💰 Budget remaining: {max(0, 100 - pct)}%",
                    "",
                ]
            )
        lines.extend(
            [
                "Commands (conceptual):",
                "  /team add — add a member",
                "  /team remove — remove a member",
                "  /task assign — assign work (Phase 27)",
                "  /project new — start a project (Phase 27)",
            ]
        )
        return "\n".join(lines)


__all__ = ["TeamRoster"]
