"""P0 — hosted / URL paste must not create Agent Graph tasks (no @https nodes)."""

from __future__ import annotations

import uuid

from app.models.nexa_next_runtime import NexaMission, NexaMissionTask
from app.services.agent_runtime.chat_tools import detect_valid_bounded_mission
from app.services.cleanup.url_scheme_impostors import purge_scheme_impostor_tasks
from app.services.hosted_service_mission_gate import hosted_service_mission_blocked
from app.services.intent_classifier import get_intent
from app.services.missions.parser import parse_mission
from app.services.runtime_agents.factory import create_runtime_agents
from app.services.swarm.mission_parser import parse_mission as strict_parse_mission


BOUNDED_WITH_RAILWAY_AND_FAKE_SCHEME = """
@boss run mission "Debug hosted worker"
single-cycle bounded mission

Team initialization — supervised.

Authorization & scope: read-only hosted checks.

@https: //railway.app/project/foo/services

@researcher-pro: summarize logs from the workspace only.
"""


def test_hosted_service_blocked_flags_scheme_agent_lines() -> None:
    assert hosted_service_mission_blocked("@https: //railway.app/x") is True


def test_detect_valid_bounded_mission_none_when_hosted_blocked() -> None:
    assert detect_valid_bounded_mission(BOUNDED_WITH_RAILWAY_AND_FAKE_SCHEME) is None


def test_strict_parse_skips_https_handle_only_mission() -> None:
    doc = (
        '@boss run mission "Hosted worker triage"\n'
        "single-cycle bounded mission\n\n"
        "@https: //railway.app/project/foo/services\n"
    )
    assert strict_parse_mission(doc) is None


def test_create_runtime_agents_drops_scheme_handles() -> None:
    agents = create_runtime_agents(
        {
            "title": "t",
            "agents": [
                {"role": "https", "task": "//evil.example/x", "depends_on": []},
                {"role": "worker", "task": "real task line here", "depends_on": []},
            ],
        },
        "u1",
    )
    assert len(agents) == 1
    assert agents[0]["handle"] == "worker"


def test_parse_mission_none_for_railway_url_line_missions() -> None:
    assert parse_mission("Mission: \"x\"\nhttps://railway.app/z\nalpha: do something real") is None


def test_intent_railway_dashboard_url_maps_external_execution_not_investigation() -> None:
    assert (
        get_intent("Why unhealthy https://railway.app/project/abc/services") == "external_execution"
    )


def test_intent_plain_https_not_upgraded_without_provider_host() -> None:
    assert get_intent("Why https://example.com/foo broken") == "external_investigation"


def test_purge_removes_https_tasks_and_orphan_mission(db_session, nexa_runtime_clean) -> None:
    uid = f"purge_{uuid.uuid4().hex[:8]}"
    mid = f"m_{uuid.uuid4().hex[:12]}"
    db_session.add(NexaMission(id=mid, user_id=uid, title="bad", status="completed"))
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="https",
            role="https",
            task="//railway.app/x",
            status="completed",
            depends_on=[],
            output_json={"type": "heartbeat", "ok": True},
        )
    )
    db_session.commit()

    stats = purge_scheme_impostor_tasks(db_session)
    db_session.commit()

    assert stats["tasks_deleted"] >= 1
    assert stats["missions_deleted"] >= 1
    assert db_session.get(NexaMission, mid) is None
