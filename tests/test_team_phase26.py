# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 26 — Team roster / member / roles / skills (Mission Control naming)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.sub_agent_registry import AgentRegistry, AgentStatus
from app.services.team import TeamRoster, normalize_role_key, role_label
from app.services.team.skills import format_skills_phrase, merge_skills


class _S:
    def __init__(self, *, enabled: bool = True) -> None:
        self.nexa_agent_orchestration_enabled = enabled
        self.nexa_agent_max_per_chat = 5
        self.nexa_agent_idle_timeout_seconds = 3600


@pytest.fixture
def roster() -> TeamRoster:
    AgentRegistry.reset()
    return TeamRoster()


def test_normalize_role_aliases() -> None:
    assert normalize_role_key("GitHub") == "git"
    assert normalize_role_key("VERCEL") == "vercel"
    assert normalize_role_key("unknown_xyz") == "general"


def test_role_label() -> None:
    assert "Git" in role_label("git")
    assert "Vercel" in role_label("vercel")


def test_merge_skills_dedupes() -> None:
    assert merge_skills(["push", "pull"], ["push", "commit"]) == ["push", "pull", "commit"]


def test_format_skills_phrase() -> None:
    s = format_skills_phrase(["commit", "deploy"])
    assert "commit" in s.lower() or "changes" in s.lower()
    assert "deploy" in s.lower()


def test_roster_add_list_remove(roster: TeamRoster) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        m = roster.add_member("Architect", "git", "chat-1", extra_skills=["review"])
    assert m is not None
    assert m.display_name == "Architect"
    assert "review" in m.skills

    listed = roster.list_members("chat-1")
    assert len(listed) == 1
    assert listed[0].member_id == m.member_id

    assert roster.remove_member(m.member_id)
    active = roster.list_members("chat-1")
    assert len(active) == 0


def test_roster_format_message(roster: TeamRoster) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        m = roster.add_member("Dev", "vercel", "c99")
        assert m is not None
        roster.set_member_task(m.member_id, "Fix login bug")

    text = roster.format_roster_message("c99", team_hours_used=820, team_hours_cap=3000)
    assert "YOUR AI TEAM" in text
    assert "Dev" in text
    assert "Fix login bug" in text
    assert "820" in text and "3000" in text


def test_member_busy_status(roster: TeamRoster) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        m = roster.add_member("QA", "test", "c1")
        assert m is not None
    AgentRegistry().update_status(m.member_id, AgentStatus.BUSY)
    tm = roster.get_member(m.member_id)
    assert tm is not None
    assert tm.status_text == "Busy"


def test_roster_get_agent_status(roster: TeamRoster) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        m = roster.add_member("Ops", "git", "c2")
        assert m is not None
    roster.set_member_task(m.member_id, "Deploy")
    st = roster.get_agent_status(m.member_id)
    assert "error" not in st
    assert st.get("name") == "Ops"
    assert st.get("domain") == "git"
    assert st.get("current_task") == "Deploy"
    assert st.get("status") == "idle"

    assert roster.get_agent_status("bad-id-xyz").get("error") == "Agent not found"
