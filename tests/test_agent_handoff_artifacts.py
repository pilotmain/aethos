"""Phase 5–6 — artifacts propagate between dependent agents (DB-backed)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.nexa_next_runtime import NexaArtifact
from app.services.artifacts.store import read_artifacts
from app.services.gateway.runtime import NexaGateway


def test_researcher_produces_artifact_analyst_and_qa_receive_prior_outputs(nexa_runtime_clean) -> None:
    text = """Mission: "Handoff chain"

Researcher: find robotics breakthroughs here today
Analyst: write forecast using Researcher output here today
QA: review Analyst output carefully today"""
    out = NexaGateway().handle_message(text, "u_handoff")
    assert out["status"] == "completed"

    agents = out["result"]
    mission_id = agents[0].get("mission_id")
    assert mission_id

    chain = read_artifacts(nexa_runtime_clean, mission_id)
    assert len(chain) == 3

    assert chain[0]["agent"] == "researcher"
    assert chain[0]["artifact"]["type"] == "research_notes"

    assert chain[1]["agent"] == "analyst"
    analyst_out = agents[1]["output"]
    assert isinstance(analyst_out, dict)
    assert analyst_out["type"] == "forecast"
    assert "Based on inputs:" in analyst_out.get("text", "")

    assert chain[2]["agent"] == "qa"
    qa_out = agents[2]["output"]
    assert isinstance(qa_out, dict)
    assert qa_out["type"] == "qa_report"
    qa_text = qa_out.get("text", "")
    assert "Reviewing outputs" in qa_text
    assert "researcher" in qa_text.lower() and "analyst" in qa_text.lower()

    n = nexa_runtime_clean.scalar(select(func.count()).select_from(NexaArtifact))
    assert n == 3


def test_artifact_store_accumulates_per_mission(nexa_runtime_clean) -> None:
    text = """Researcher: find robotics research topics here
Analyst: write forecast summary here"""
    out = NexaGateway().handle_message(text, "u2")
    assert out["status"] == "completed"
    mid = out["result"][0]["mission_id"]
    assert len(read_artifacts(nexa_runtime_clean, mid)) == 2
