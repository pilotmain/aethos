"""Strict swarm mission_parser — explicit task lines and titles only."""

from __future__ import annotations

from app.services.swarm.mission_parser import parse_mission

DOC_MISSION = """
@boss run mission "Robotics Research"

@researcher-pro: find 3 breakthroughs in autonomous robotics.
@analyst-pro: write a 3-paragraph forecast based on @researcher-pro output.
@qa: review the output from @analyst-pro and list risks.

single-cycle.
""".strip()


def test_parse_mission_doc_example() -> None:
    m = parse_mission(DOC_MISSION)
    assert m is not None
    assert m["title"] == "Robotics Research"
    assert m["single_cycle"] is True
    assert len(m["tasks"]) == 3
    assert m["tasks"][0]["agent_handle"] == "researcher_pro"
    assert "breakthroughs" in m["tasks"][0]["task"].lower()
    assert m["tasks"][0]["depends_on"] == []
    assert "researcher_pro" in m["tasks"][1]["depends_on"]
    assert "analyst_pro" in m["tasks"][2]["depends_on"]


def test_parse_mission_returns_none_without_title() -> None:
    body = """
@researcher-pro: do something with enough text here.

single-cycle.
""".strip()
    assert parse_mission(body) is None


def test_parse_mission_returns_none_without_tasks() -> None:
    body = """
@boss run mission "Only Title"

single-cycle.
""".strip()
    assert parse_mission(body) is None
