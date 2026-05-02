"""Phase 46C — agent intel JSON persistence beside memory."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.agents.agent_intel_store import list_agent_intel_profiles, record_agent_outcome


def test_record_and_list_agent_intel(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "mem"))
    get_settings.cache_clear()
    try:
        uid = f"agent_persist_{__import__('uuid').uuid4().hex[:8]}"
        record_agent_outcome(uid, "test_agent", success=True, meta={"task": "smoke"})
        record_agent_outcome(uid, "test_agent", success=False, meta={})
        rows = list_agent_intel_profiles(uid)
        assert len(rows) == 1
        assert rows[0]["handle"] == "test_agent"
        assert rows[0]["runs"] == 2
        assert rows[0]["successes"] == 1
        assert 0 <= float(rows[0]["performance_score"]) <= 1
    finally:
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()
