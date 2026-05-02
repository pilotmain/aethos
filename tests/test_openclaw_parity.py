"""Phase 41 — OpenClaw parity surfaces: capabilities, channels, dev pipeline, memory, browser gates."""

from __future__ import annotations

import subprocess

import pytest

from app.core.config import get_settings
from app.services.agents.long_running import (
    LongRunningSession,
    register_session,
    tick_all_registered,
    unregister_session,
)
from app.services.channels.discord import DiscordChannel
from app.services.channels.router import route_inbound
from app.services.channels.slack import SlackChannel
from app.services.dev_runtime.service import DEV_PIPELINE_SEQUENCE, run_dev_mission
from app.services.dev_runtime.workspace import register_workspace
from app.services.memory.intelligence import prune_old_entries, score_entry
from app.services.memory.memory_store import MemoryStore
from app.services.system_access.browser_playwright import open_page
from app.services.system_identity.capabilities import CAPABILITIES, narrative_capability_answer


def test_capabilities_map_complete() -> None:
    assert CAPABILITIES.get("dev_execution") is True
    assert CAPABILITIES.get("multi_agent_dynamic") is True
    keys = set(CAPABILITIES.keys())
    assert "memory" in keys and "system_access" in keys


def test_identity_capability_reply_no_legacy_center() -> None:
    low = narrative_capability_answer().lower()
    assert "command center" not in low
    assert "route to specialists" not in low


def test_slack_and_discord_channels_route() -> None:
    assert SlackChannel().name == "slack"
    assert DiscordChannel().name == "discord"
    out = SlackChannel().receive({"text": "hi", "user_id": "sl_u1"}, db=None)
    assert isinstance(out, dict)
    assert "mode" in out or "text" in out


def test_route_inbound_web_default() -> None:
    out = route_inbound("hello", "parity_u1", db=None, channel="web")
    assert isinstance(out, dict)


def test_long_running_checkpoint_tick(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        sess = LongRunningSession("lr_u1", "sess_p41", "parity goal")
        register_session(sess)
        hits = tick_all_registered()
        mine = [
            h
            for h in hits
            if h.get("user_id") == "lr_u1"
            and (h.get("session_key") == "sess_p41" or h.get("session_id") == "sess_p41")
        ]
        assert len(mine) == 1
        assert mine[0].get("iteration") == 1
        cp = sess.load_checkpoint()
        assert cp.iteration >= 1
    finally:
        unregister_session("lr_u1", "sess_p41")
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()


def test_dev_pipeline_sequence_order() -> None:
    assert DEV_PIPELINE_SEQUENCE[0] == "analyze"
    assert "commit" in DEV_PIPELINE_SEQUENCE


def test_run_dev_mission_includes_pipeline(db_session, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "parity_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    get_settings.cache_clear()
    try:

        def pass_tests(_repo):
            return {"ok": True, "summary": "ok", "parsed": {}, "command_result": {"ok": True}}

        monkeypatch.setattr("app.services.dev_runtime.service.run_repo_tests", pass_tests)
        ws = register_workspace(db_session, "parity_dev_u1", "p", str(repo))
        out = run_dev_mission(db_session, "parity_dev_u1", ws.id, "parity goal", auto_pr=False)
        assert out.get("ok") is True
        pipe = out.get("pipeline") or {}
        assert pipe.get("sequence") == list(DEV_PIPELINE_SEQUENCE)
        assert (out.get("steps") or [])[0].get("pipeline_phase") == "analyze"
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_memory_score_and_prune(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """IDs are time-derived; force uniqueness so prune removes duplicate-second collisions."""
    ids = [f"p41_{i:03d}" for i in range(8)]

    def _fake_new_id(i: list[int]) -> str:
        idx = i[0]
        i[0] += 1
        return ids[idx]

    counter = [0]
    monkeypatch.setattr(
        "app.services.memory.memory_store._new_id",
        lambda: _fake_new_id(counter),
    )
    st = MemoryStore(base_dir=tmp_path)
    for i in range(8):
        st.append_entry("prune_u", kind="note", title=f"n{i}", body_md=f"body {i}")
    r = prune_old_entries("prune_u", max_entries=3, store=st)
    assert r.get("ok") is True
    assert r.get("removed", 0) >= 1
    assert len(st.list_entries("prune_u")) <= 3


def test_memory_mission_summary_scores_higher() -> None:
    a = score_entry({"type": "note", "ts": "2020-01-01T00:00:00+00:00"})
    b = score_entry(
        {
            "type": "mission_summary",
            "ts": "2025-01-01T00:00:00+00:00",
            "meta": {"mission_id": "m1"},
        }
    )
    assert b > a


def test_browser_open_page_respects_preview_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_BROWSER_PREVIEW_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = open_page("https://example.com/")
        assert r.get("ok") is False
        assert r.get("error") == "browser_preview_disabled"
    finally:
        monkeypatch.delenv("NEXA_BROWSER_PREVIEW_ENABLED", raising=False)
        get_settings.cache_clear()
