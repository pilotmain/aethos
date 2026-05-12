# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73 — Self-healing agents (Genesis Loop) tests.

Covers:

* :mod:`app.services.agent.learning` — fingerprinting + mistake memory
  persistence in an isolated SQLite file.
* :mod:`app.services.agent.self_diagnosis` — cause classification heuristics
  with an injected tracker (no real DB or LLM).
* :mod:`app.services.agent.recovery` — strategy dispatch, attempt cap,
  metadata patching, mistake memory + tracker logging.
* :mod:`app.services.agent.supervisor` — ``_run_self_healing`` end-to-end with
  threshold gating and escalation.
* :mod:`app.api.routes.agent_health` — auth scoping (user vs. owner) and
  manual diagnose / recover endpoints.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import agent_health as agent_health_module
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.agent.learning import (
    MistakeMemory,
    fingerprint_error,
)
from app.services.agent.recovery import (
    STRATEGY_CAPPED,
    STRATEGY_LLM_FALLBACK,
    STRATEGY_NONE,
    STRATEGY_STATE_RESET,
    RecoveryHandler,
)
from app.services.agent.self_diagnosis import (
    CAUSE_NO_FAILURES,
    CAUSE_REPEATED_LLM_ERROR,
    CAUSE_STATE_CORRUPTED,
    CAUSE_TRANSIENT,
    CAUSE_UNKNOWN,
    SelfDiagnosis,
)
from app.services.agent.supervisor import AgentSupervisor
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent


# ---------------------------------------------------------------------------
# Shared in-memory fakes


class _FakeTracker:
    """Drop-in for AgentActivityTracker.get_agent_history / log_action."""

    def __init__(self) -> None:
        self.history_by_agent: dict[str, list[dict[str, Any]]] = {}
        self.logged: list[dict[str, Any]] = []

    def set_history(self, agent_id: str, rows: list[dict[str, Any]]) -> None:
        self.history_by_agent[agent_id] = list(rows)

    def get_agent_history(
        self, agent_id: str, *, hours: int = 24, limit: int = 100
    ) -> list[dict[str, Any]]:
        return list(self.history_by_agent.get(agent_id, []))[:limit]

    def get_agent_statistics(self, agent_id: str, *, days: int = 30) -> dict[str, Any]:
        rows = self.history_by_agent.get(agent_id, [])
        total = len(rows)
        succ = sum(1 for r in rows if r.get("success"))
        return {
            "total_actions": total,
            "successful_actions": succ,
            "failed_actions": total - succ,
            "success_rate": (succ / total * 100.0) if total else 100.0,
            "avg_duration_ms": 0.0,
        }

    def log_action(self, **kwargs: Any) -> None:
        self.logged.append(kwargs)


class _InMemoryRegistry:
    """Minimal AgentRegistry stand-in — same surface the recovery handler uses."""

    def __init__(self) -> None:
        self._agents: dict[str, SubAgent] = {}

    def add(self, agent: SubAgent) -> SubAgent:
        self._agents[agent.id] = agent
        return agent

    def get_agent(self, agent_id: str) -> SubAgent | None:
        return self._agents.get(agent_id)

    def list_agents(self, _scope: Any = None) -> list[SubAgent]:
        return list(self._agents.values())

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        a = self._agents.get(agent_id)
        if not a:
            return False
        a.status = status
        if status == AgentStatus.IDLE:
            a.last_active = time.time()
        return True

    def touch_agent(self, agent_id: str) -> bool:
        a = self._agents.get(agent_id)
        if not a:
            return False
        a.last_active = time.time()
        return True

    def patch_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        domain: str | None = None,
        capabilities: list[str] | None = None,
        status: AgentStatus | None = None,
        trusted: bool | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> SubAgent | None:
        a = self._agents.get(agent_id)
        if not a:
            return None
        if status is not None:
            a.status = status
        if metadata_patch is not None:
            md = dict(a.metadata or {})
            md.update(metadata_patch)
            a.metadata = md
        return a


def _make_agent(
    *,
    agent_id: str | None = None,
    name: str = "test_agent",
    domain: str = "qa",
    status: AgentStatus = AgentStatus.IDLE,
    last_active: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> SubAgent:
    return SubAgent(
        id=agent_id or f"a{uuid.uuid4().hex[:8]}",
        name=name,
        domain=domain,
        capabilities=[],
        parent_chat_id=f"tg_{uuid.uuid4().hex[:6]}",
        status=status,
        last_active=last_active if last_active is not None else time.time(),
        metadata=dict(metadata or {}),
    )


# ---------------------------------------------------------------------------
# learning.py


def test_fingerprint_collapses_numbers_and_quoting() -> None:
    a = fingerprint_error("Anthropic 429 'rate_limit' on req 12345abcdef")
    b = fingerprint_error("anthropic 503 'rate_limit' on req 99999bcdef")
    # Numbers and long hex blobs collapse so the two errors share the same head.
    assert a.startswith("anthropic")
    assert b.startswith("anthropic")
    assert "rate_limit" in a
    assert "N" in a and "N" in b


def test_fingerprint_empty_for_none() -> None:
    assert fingerprint_error(None) == ""
    assert fingerprint_error("") == ""


def test_mistake_memory_round_trip(tmp_path) -> None:
    db = tmp_path / "audit.db"
    mm = MistakeMemory(db_path=db)
    rid = mm.record_mistake(
        agent_id="a1",
        error="Anthropic 429 rate_limit",
        cause_class=CAUSE_REPEATED_LLM_ERROR,
        recovery_strategy=STRATEGY_LLM_FALLBACK,
        recovery_succeeded=True,
        context={"foo": "bar"},
    )
    assert rid is not None and rid > 0
    similar = mm.get_similar_mistakes(error="Anthropic 503 rate_limit")
    assert len(similar) == 1
    row = similar[0]
    assert row["cause_class"] == CAUSE_REPEATED_LLM_ERROR
    assert row["recovery_strategy"] == STRATEGY_LLM_FALLBACK
    assert row["recovery_succeeded"] is True
    assert row["context"]["foo"] == "bar"

    # successful_strategy_for picks up the same fingerprint.
    fp = fingerprint_error("Anthropic 429 rate_limit")
    assert mm.successful_strategy_for(fp) == STRATEGY_LLM_FALLBACK


def test_mistake_memory_get_similar_returns_empty_for_no_fingerprint(
    tmp_path,
) -> None:
    mm = MistakeMemory(db_path=tmp_path / "audit.db")
    assert mm.get_similar_mistakes(error=None) == []
    assert mm.get_similar_mistakes(fingerprint="") == []


# ---------------------------------------------------------------------------
# self_diagnosis.py


@pytest.fixture()
def diag_env(tmp_path) -> tuple[_FakeTracker, MistakeMemory, SelfDiagnosis]:
    tracker = _FakeTracker()
    mm = MistakeMemory(db_path=tmp_path / "audit.db")
    diag = SelfDiagnosis(tracker=tracker, mistake_memory=mm, clock=lambda: 1_000_000.0)
    return tracker, mm, diag


def test_diagnose_no_failures_short_circuits(diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent()
    tracker.set_history(agent.id, [{"success": True, "error": None}])
    out = diag.diagnose(agent, use_llm=False)
    assert out.cause_class == CAUSE_NO_FAILURES
    assert out.error_count == 0


def test_diagnose_state_corrupted_when_busy_too_long(diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent(status=AgentStatus.BUSY, last_active=1_000_000.0 - 1200.0)
    tracker.set_history(
        agent.id,
        [
            {"success": False, "error": "task already running on this agent"},
            {"success": False, "error": "task already running on this agent"},
        ],
    )
    out = diag.diagnose(agent, use_llm=False)
    assert out.cause_class == CAUSE_STATE_CORRUPTED
    assert out.error_count == 2


def test_diagnose_repeated_llm_error(diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent()
    tracker.set_history(
        agent.id,
        [
            {"success": False, "error": "Anthropic 429 rate_limit hit"},
            {"success": False, "error": "openai timeout reading response"},
            {"success": False, "error": "anthropic 503 service unavailable"},
        ],
    )
    out = diag.diagnose(agent, use_llm=False)
    assert out.cause_class == CAUSE_REPEATED_LLM_ERROR
    assert out.error_count == 3
    assert out.fingerprint  # fingerprinted dominant error


def test_diagnose_transient_when_scattered(diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent()
    tracker.set_history(
        agent.id,
        [
            {"success": False, "error": "ValueError: bad input"},
            {"success": False, "error": "FileNotFoundError: missing config.json"},
            {"success": False, "error": "PermissionError: cannot write"},
            {"success": False, "error": "KeyError: 'name'"},
        ],
    )
    out = diag.diagnose(agent, use_llm=False)
    assert out.cause_class == CAUSE_TRANSIENT


def test_diagnose_unknown_when_one_repeated_non_llm_error(diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent()
    tracker.set_history(
        agent.id,
        [
            {"success": False, "error": "RuntimeError: weird thing"},
            {"success": False, "error": "RuntimeError: weird thing"},
        ],
    )
    out = diag.diagnose(agent, use_llm=False)
    assert out.cause_class == CAUSE_UNKNOWN


def test_diagnose_llm_summary_failure_does_not_break(monkeypatch, diag_env) -> None:
    tracker, _mm, diag = diag_env
    agent = _make_agent()
    tracker.set_history(
        agent.id, [{"success": False, "error": "RuntimeError: x"}] * 2
    )
    monkeypatch.setattr(
        "app.services.llm.completion.primary_complete_messages",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no llm")),
    )
    out = diag.diagnose(agent, use_llm=True)
    assert out.used_llm is False
    assert out.llm_summary is None
    assert out.cause_class in (CAUSE_UNKNOWN, CAUSE_TRANSIENT)


# ---------------------------------------------------------------------------
# recovery.py


@pytest.fixture()
def recovery_env(tmp_path) -> tuple[_InMemoryRegistry, _FakeTracker, MistakeMemory, RecoveryHandler]:
    registry = _InMemoryRegistry()
    tracker = _FakeTracker()
    mm = MistakeMemory(db_path=tmp_path / "audit.db")
    handler = RecoveryHandler(
        registry=registry,  # type: ignore[arg-type]
        tracker=tracker,  # type: ignore[arg-type]
        mistake_memory=mm,
        clock=lambda: 2_000_000.0,
    )
    return registry, tracker, mm, handler


def _diag(agent: SubAgent, cause: str, fingerprint: str = "fp1", top: list[dict[str, Any]] | None = None):
    from app.services.agent.self_diagnosis import Diagnosis

    return Diagnosis(
        agent_id=agent.id,
        cause_class=cause,
        summary=f"summary for {cause}",
        error_count=3,
        window_minutes=60,
        top_errors=list(top or [{"error": "Anthropic 429 rate_limit", "count": 3}]),
        fingerprint=fingerprint,
    )


def test_recovery_no_failures_returns_none_strategy(recovery_env) -> None:
    registry, _tracker, _mm, handler = recovery_env
    agent = registry.add(_make_agent())
    out = handler.attempt(agent, _diag(agent, CAUSE_NO_FAILURES))
    assert out.strategy == STRATEGY_NONE
    assert out.succeeded is True
    assert out.escalate is False


def test_recovery_state_corrupted_resets_busy_to_idle(recovery_env) -> None:
    registry, tracker, _mm, handler = recovery_env
    agent = registry.add(
        _make_agent(status=AgentStatus.BUSY, metadata={"current_task": "old work"})
    )
    out = handler.attempt(agent, _diag(agent, CAUSE_STATE_CORRUPTED))
    assert out.strategy == STRATEGY_STATE_RESET
    assert out.succeeded is True
    refreshed = registry.get_agent(agent.id)
    assert refreshed is not None
    assert refreshed.status == AgentStatus.IDLE
    assert "current_task" not in (refreshed.metadata or {})
    assert int(refreshed.metadata["recovery_attempts"]) == 1
    # Tracker received the recovery + mistake-memory side effects.
    assert any(r.get("action_type") == "self_heal_recovery" for r in tracker.logged)


def test_recovery_llm_fallback_sets_metadata(recovery_env) -> None:
    registry, _tracker, _mm, handler = recovery_env
    agent = registry.add(_make_agent(status=AgentStatus.IDLE))
    out = handler.attempt(agent, _diag(agent, CAUSE_REPEATED_LLM_ERROR))
    assert out.strategy == STRATEGY_LLM_FALLBACK
    assert out.succeeded is True
    refreshed = registry.get_agent(agent.id)
    assert refreshed is not None
    assert (refreshed.metadata or {}).get("fallback_llm")  # default ollama
    assert (refreshed.metadata or {}).get("fallback_llm_set_at") is not None


def test_recovery_attempt_cap_escalates(recovery_env) -> None:
    registry, _tracker, _mm, handler = recovery_env
    agent = registry.add(
        _make_agent(metadata={"recovery_attempts": 3})  # at cap (default 3)
    )
    out = handler.attempt(agent, _diag(agent, CAUSE_REPEATED_LLM_ERROR))
    assert out.strategy == STRATEGY_CAPPED
    assert out.succeeded is False
    assert out.escalate is True
    assert out.attempts_used == 3


def test_recovery_prefers_known_good_strategy_from_mistake_memory(
    recovery_env,
) -> None:
    registry, _tracker, mm, handler = recovery_env
    agent = registry.add(_make_agent())
    # Seed memory with a previously successful state_reset for this fingerprint.
    mm.record_mistake(
        agent_id=agent.id,
        error="some earlier error",
        cause_class=CAUSE_UNKNOWN,
        recovery_strategy=STRATEGY_STATE_RESET,
        recovery_succeeded=True,
    )
    fp = fingerprint_error("some earlier error")
    diag = _diag(agent, CAUSE_REPEATED_LLM_ERROR, fingerprint=fp)
    out = handler.attempt(agent, diag)
    # Even though cause says LLM, memory's known-good strategy wins.
    assert out.strategy == STRATEGY_STATE_RESET


def test_reset_recovery_attempts_clears_metadata(recovery_env) -> None:
    registry, _tracker, _mm, handler = recovery_env
    agent = registry.add(
        _make_agent(
            metadata={
                "recovery_attempts": 2,
                "last_recovery_strategy": STRATEGY_STATE_RESET,
                "last_recovery_at": 12345.6,
            }
        )
    )
    handler.reset_recovery_attempts(agent.id)
    refreshed = registry.get_agent(agent.id)
    assert refreshed is not None
    md = refreshed.metadata or {}
    assert "recovery_attempts" not in md
    assert "last_recovery_strategy" not in md


# ---------------------------------------------------------------------------
# supervisor.py — _run_self_healing


def test_supervisor_self_heal_skips_below_threshold(monkeypatch, recovery_env) -> None:
    registry, tracker, _mm, _handler = recovery_env
    agent = registry.add(_make_agent())
    tracker.set_history(
        agent.id, [{"success": False, "error": "x"}] * 1
    )  # below default threshold of 3

    sup = AgentSupervisor()
    sup.tracker = tracker  # type: ignore[assignment]
    sup.registry = registry  # type: ignore[assignment]

    out = sup._run_self_healing(agent, {})
    assert out is None


def test_supervisor_self_heal_runs_diagnose_and_recover(
    monkeypatch, recovery_env
) -> None:
    registry, tracker, mm, _handler = recovery_env
    agent = registry.add(_make_agent(status=AgentStatus.BUSY))
    tracker.set_history(
        agent.id,
        [{"success": False, "error": "Anthropic 429 rate_limit"}] * 4,
    )

    # Wire singletons to our injected fakes so the supervisor sees them.
    monkeypatch.setattr(
        "app.services.agent.self_diagnosis.get_activity_tracker",
        lambda: tracker,
    )
    monkeypatch.setattr(
        "app.services.agent.self_diagnosis.get_mistake_memory",
        lambda: mm,
    )
    monkeypatch.setattr(
        "app.services.agent.recovery.get_recovery_handler",
        lambda: RecoveryHandler(
            registry=registry,  # type: ignore[arg-type]
            tracker=tracker,  # type: ignore[arg-type]
            mistake_memory=mm,
            clock=lambda: 3_000_000.0,
        ),
    )
    # Reset diagnosis singleton so it picks up our patched factories.
    monkeypatch.setattr(
        "app.services.agent.self_diagnosis._self_diagnosis", None, raising=False
    )

    sup = AgentSupervisor()
    sup.tracker = tracker  # type: ignore[assignment]
    sup.registry = registry  # type: ignore[assignment]

    out = sup._run_self_healing(agent, {})
    assert out is not None
    assert out["cause_class"] == CAUSE_REPEATED_LLM_ERROR
    assert out["strategy"] == STRATEGY_LLM_FALLBACK
    assert out["succeeded"] is True
    assert out["escalate"] is False
    # Tracker received both diagnosis + recovery breadcrumbs.
    action_types = {r.get("action_type") for r in tracker.logged}
    assert "self_heal_diagnosis" in action_types
    assert "self_heal_recovery" in action_types


def test_supervisor_escalation_logs_when_chat_id_unset(
    monkeypatch, recovery_env
) -> None:
    registry, tracker, _mm, _handler = recovery_env
    agent = registry.add(_make_agent())

    sup = AgentSupervisor()
    sup.tracker = tracker  # type: ignore[assignment]
    sup.registry = registry  # type: ignore[assignment]

    diag = {
        "cause_class": CAUSE_REPEATED_LLM_ERROR,
        "summary": "rate-limited",
        "fingerprint": "fp",
    }
    res = {
        "strategy": STRATEGY_CAPPED,
        "succeeded": False,
        "attempts_used": 3,
    }
    sup._escalate_self_heal(agent, diag, res)
    assert any(r.get("action_type") == "self_heal_escalation" for r in tracker.logged)


# ---------------------------------------------------------------------------
# /api/v1/agent/health


@pytest.fixture()
def real_agent_in_registry():
    """Insert a real SubAgent into the AgentRegistry singleton for the API tests."""
    AgentRegistry.reset()
    reg = AgentRegistry()
    chat = f"tg_{uuid.uuid4().hex[:8]}"
    agent = SubAgent(
        id=f"h{uuid.uuid4().hex[:8]}",
        name="health_test",
        domain="qa",
        capabilities=[],
        parent_chat_id=chat,
        status=AgentStatus.IDLE,
    )
    reg._agents[agent.id] = agent  # type: ignore[attr-defined]
    yield agent, chat
    AgentRegistry.reset()


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


def _override_scopes(monkeypatch, scopes: list[str]) -> None:
    monkeypatch.setattr(
        "app.api.routes.agent_health._api_orchestration_scopes",
        lambda _uid: list(scopes),
    )


def test_health_get_requires_agent_in_scope(monkeypatch, real_agent_in_registry) -> None:
    agent, _chat = real_agent_in_registry
    _override_user("tg_other")
    _override_scopes(monkeypatch, ["tg_other"])
    monkeypatch.setattr(
        agent_health_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "guest",
    )
    try:
        client = TestClient(app)
        r = client.get(f"/api/v1/agent/health/{agent.id}")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_health_get_returns_payload_when_in_scope(
    monkeypatch, real_agent_in_registry
) -> None:
    agent, chat = real_agent_in_registry
    _override_user(chat)
    _override_scopes(monkeypatch, [chat])
    try:
        client = TestClient(app)
        r = client.get(f"/api/v1/agent/health/{agent.id}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["agent"]["id"] == agent.id
        assert body["self_healing"]["enabled"] is True
        assert body["failures"]["in_24h_count"] >= 0
    finally:
        app.dependency_overrides.clear()


def test_health_diagnose_requires_owner(monkeypatch, real_agent_in_registry) -> None:
    agent, chat = real_agent_in_registry
    _override_user(chat)
    _override_scopes(monkeypatch, [chat])
    monkeypatch.setattr(
        agent_health_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "guest",
    )
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/agent/health/{agent.id}/diagnose")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_health_recover_owner_runs_full_loop(monkeypatch, real_agent_in_registry) -> None:
    agent, chat = real_agent_in_registry
    _override_user(chat)
    _override_scopes(monkeypatch, [chat])
    monkeypatch.setattr(
        agent_health_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "owner",
    )
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/agent/health/{agent.id}/recover")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["agent_id"] == agent.id
        assert "diagnosis" in body and "recovery" in body
        assert body["recovery"]["agent_id"] == agent.id
    finally:
        app.dependency_overrides.clear()


def test_health_disabled_returns_404(monkeypatch, real_agent_in_registry) -> None:
    agent, chat = real_agent_in_registry
    _override_user(chat)
    _override_scopes(monkeypatch, [chat])
    monkeypatch.setattr(
        "app.api.routes.agent_health.get_settings",
        lambda: type("S", (), {"nexa_self_healing_enabled": False})(),
    )
    try:
        client = TestClient(app)
        r = client.get(f"/api/v1/agent/health/{agent.id}")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
