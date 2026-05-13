# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
End-to-end **product smoke** slice (CI-friendly).

Run::

    pytest tests/e2e/test_product_e2e_suite.py -m product_e2e

Or::

    ./scripts/run_product_e2e.sh

Checklist covered here:
  - Greeting (gateway ``Hi`` / ``Hello``)
  - Agent creation NL (orchestration spawn path)
  - File write (host executor approval gate)
  - Command execution (host executor approval gate)
  - Soul versioning (API update + snapshot on disk)
  - Plugin / builtin tools registry
  - Marketplace registry HTTP surface

Optional browser import check: ``tests/e2e/test_product_e2e_browser_optional.py`` (``-m product_e2e_browser`` + ``RUN_BROWSER_E2E=1``).
"""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.models.agent_job import AgentJob
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.plugins.registry import load_plugins
from app.services.tools.registry import TOOLS

from tests.e2e.support import patch_host_executor_for_e2e

pytestmark = [pytest.mark.product_e2e, pytest.mark.usefixtures("nexa_runtime_clean")]


@pytest.fixture
def e2e_client(api_client):
    """``TestClient`` + user id from shared ``api_client`` fixture."""
    client, uid = api_client
    return client, uid


def test_e2e_01_greeting_gateway(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    uid = f"e2e_hi_{uuid.uuid4().hex[:10]}"
    ctx = GatewayContext.from_channel(uid, "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "Hi!", db=nexa_runtime_clean)
    assert out.get("intent") == "greeting"
    text = out.get("text") or ""
    assert "AethOS" in text
    assert "What\u2019s on your mind" not in text  # U+2019 apostrophe
    assert "What's on your mind" not in text


def test_e2e_02_agent_nl_spawn(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "general_chat",
    )
    captured: dict[str, str] = {}

    def fake_spawn(db, uid, text, *, parent_chat_id: str) -> str:
        captured["uid"] = uid
        captured["text"] = text
        return "NL spawn ok."

    monkeypatch.setattr(
        "app.services.sub_agent_natural_creation.try_spawn_natural_sub_agents",
        fake_spawn,
    )
    uid = f"e2e_agent_{uuid.uuid4().hex[:10]}"
    ctx = GatewayContext.from_channel(uid, "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "Create a marketing agent", db=nexa_runtime_clean)
    assert out.get("intent") == "create_sub_agent"
    assert captured.get("uid") == uid


def test_e2e_03_file_write_queues_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    nexa_runtime_clean,
) -> None:
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    # Use a relative directory label only — absolute tmp_path often contains the
    # substring "pytest", which would match maybe_dev_gateway_hint's "pytest" cue.
    patch_host_executor_for_e2e(monkeypatch, tmp_path, include_enforcement_pipeline=True)
    # Unique uid + session so a stale ConversationContext row (not cleared by
    # clear_store_for_tests) cannot leave next_action_pending_inject_json set,
    # which would make may_run_pre_llm_deterministic_host False and skip the host path.
    uid = f"e2e_file_{uuid.uuid4().hex[:12]}"
    ctx = GatewayContext.from_channel(
        uid,
        "web",
        {"web_session_id": f"sess-e2e-file-{uuid.uuid4().hex[:8]}"},
    )
    phrase = "Create a file called e2e.txt with content 'ok' in e2e_workspace"
    out = NexaGateway().handle_message(ctx, phrase, db=nexa_runtime_clean)
    assert out.get("host_executor") is True
    assert out.get("intent") == "file_write"
    assert "Approval" in (out.get("text") or "")


def test_e2e_04_run_command_queues_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    nexa_runtime_clean,
) -> None:
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    patch_host_executor_for_e2e(monkeypatch, tmp_path, include_enforcement_pipeline=False)
    uid = f"e2e_cmd_{uuid.uuid4().hex[:12]}"
    ctx = GatewayContext.from_channel(
        uid,
        "web",
        {"web_session_id": f"sess-e2e-cmd-{uuid.uuid4().hex[:8]}"},
    )
    out = NexaGateway().handle_message(ctx, "run ls -la", db=nexa_runtime_clean)
    assert out.get("host_executor") is True
    assert out.get("intent") == "command_approval"
    assert "Approval" in (out.get("text") or "")
    out_yes = NexaGateway().handle_message(ctx, "yes", db=nexa_runtime_clean)
    assert out_yes.get("related_job_ids")
    job = nexa_runtime_clean.get(AgentJob, out_yes["related_job_ids"][0])
    assert job is not None
    assert (job.payload_json or {}).get("host_action") == "run_command"


def test_e2e_05_soul_snapshot_on_put(e2e_client, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client, uid = e2e_client
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    get_settings.cache_clear()
    try:
        r0 = client.put(
            "/api/v1/web/memory/soul",
            json={"content": "# Soul\n\nfirst line"},
            headers={"X-User-Id": uid},
        )
        assert r0.status_code == 200, r0.text
        r1 = client.put(
            "/api/v1/web/memory/soul",
            json={"content": "# Soul\n\nsecond line"},
            headers={"X-User-Id": uid},
        )
        assert r1.status_code == 200, r1.text
        from app.services.soul_manager import get_user_soul_history

        hist = get_user_soul_history(uid, limit=10)
        assert len(hist) >= 1
    finally:
        get_settings.cache_clear()


def test_e2e_06_plugin_builtin_tools() -> None:
    load_plugins()
    assert "web_search" in TOOLS


def test_e2e_07_marketplace_registry_status(e2e_client) -> None:
    client, _uid = e2e_client
    r = client.get("/api/v1/marketplace/-/registry-status")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


def test_e2e_08_soul_history_nl_gateway(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    monkeypatch.setattr(NexaGateway, "_maybe_auto_dev_investigation", lambda *a, **k: None)
    uid = f"e2e_soul_nl_{uuid.uuid4().hex[:10]}"
    ctx = GatewayContext.from_channel(uid, "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, "show soul history", db=nexa_runtime_clean)
    assert out.get("intent") == "soul_history"
    assert "history" in (out.get("text") or "").lower()
