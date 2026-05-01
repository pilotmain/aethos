"""Phase 6 — artifacts persisted in DB and visible across sessions."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.services.artifacts.store import read_artifacts
from app.services.gateway.runtime import NexaGateway


def test_artifacts_readable_after_new_db_session(nexa_runtime_clean) -> None:
    text = """Researcher: find robotics persistence proof here today"""
    out = NexaGateway().handle_message(text, "u_persist")
    assert out["status"] == "completed"
    mission_id = out["result"][0]["mission_id"]

    with SessionLocal() as s2:
        chain = read_artifacts(s2, mission_id)
        assert len(chain) == 1
        assert chain[0]["artifact"]["type"] == "research_notes"
