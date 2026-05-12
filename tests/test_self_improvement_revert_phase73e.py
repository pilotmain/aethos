# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73e — auto-revert monitor + /health/detailed + cooldown tests.

Coverage:

* :class:`SystemStateStore` — touch/get/age, cooldown window, process-start.
* :class:`ProposalStore` — 73e additive columns + ``set_auto_revert_*`` setters
  + ``list_recent_merged_within`` window scoping + ``set_github_state``
  side-effects (merged_at + auto_revert_state seeded).
* :func:`fetch_error_rate_window` — empty store, mixed success/failure rows.
* :class:`RevertMonitor.scan_once` —
  - skips when post-restart grace not elapsed,
  - skips when min-sample not met,
  - skips when below threshold,
  - fires when both met → opens revert PR + records cooldown stamp,
  - opt-out: ``auto_revert_disabled`` is honoured,
  - opt-out: ``revert_pr_open`` proposals get cleared instead of re-fired,
  - swallows :class:`GitHubError`,
  - skip if no merge_commit_sha.
* :class:`CiMonitor.scan_once` — pauses auto-merge during the 73e cooldown.
* :mod:`app.api.routes.self_improvement` — capabilities exposes
  ``auto_revert``; ``/{id}/auto-revert`` toggle; ``/-/revert-scan-now`` 200
  when enabled, ``status="disabled"`` when off.
* :mod:`app.api.routes.health` — ``/health/detailed`` shape + degrade.

No real network is used: the GitHub client surface is faked. We never
exit the process. Every test creates a fresh tmp ``ProposalStore`` and
``SystemStateStore`` so DB state never bleeds across cases.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api.routes.health as health_route
import app.api.routes.self_improvement as si_router
import app.core.restart as restart_mod
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.agent import system_state as system_state_mod
from app.services.self_improvement import ci_monitor as ci_mod
from app.services.self_improvement import github_client as gh_mod
from app.services.self_improvement import proposal as si_proposal
from app.services.self_improvement import revert_monitor as rm_mod


_VALID_DIFF = """diff --git a/app/services/foo.py b/app/services/foo.py
--- a/app/services/foo.py
+++ b/app/services/foo.py
@@ -1,3 +1,4 @@
 def foo():
     pass
+# improved 73e
+

"""


# --- Settings + fixtures --------------------------------------------------


class _Settings:
    nexa_self_improvement_enabled = True
    nexa_self_improvement_max_files_per_proposal = 5
    nexa_self_improvement_max_diff_lines = 400
    nexa_self_improvement_sandbox_timeout_s = 30
    nexa_self_improvement_allowed_paths = "app/services/,app/api/routes/,docs/"
    nexa_self_improvement_github_enabled = True
    nexa_self_improvement_github_token = "ghp_FAKE_FOR_TESTS_xxxxxxxxxxxxxxxxxxxx"
    nexa_self_improvement_github_owner = "pilotmain"
    nexa_self_improvement_github_repo = "aethos"
    nexa_self_improvement_github_base_branch = "main"
    nexa_self_improvement_github_pr_title_prefix = "[self-improvement]"
    nexa_self_improvement_github_branch_prefix = "self-improvement/"
    nexa_self_improvement_github_merge_method = "squash"
    nexa_self_improvement_wait_for_ci = True
    nexa_self_improvement_ci_poll_interval_seconds = 30
    nexa_self_improvement_ci_max_age_seconds = 21600
    nexa_self_improvement_auto_restart = False
    nexa_self_improvement_auto_restart_method = "noop"
    # 73e knobs
    nexa_self_improvement_auto_revert_enabled = True
    nexa_self_improvement_revert_health_check_interval_seconds = 30
    nexa_self_improvement_revert_error_rate_threshold = 0.3
    nexa_self_improvement_revert_min_observation_window_seconds = 300
    nexa_self_improvement_revert_min_sample_size = 10
    nexa_self_improvement_revert_post_restart_grace_seconds = 0  # off by default in tests
    nexa_self_improvement_revert_cooldown_minutes = 30
    nexa_heartbeat_enabled = False
    nexa_heartbeat_interval_seconds = 300
    nexa_data_dir = ""
    app_name = "AethOS-test"
    app_env = "test"


@pytest.fixture
def settings(monkeypatch) -> _Settings:
    s = _Settings()
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    monkeypatch.setattr(si_proposal, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "get_settings", lambda: s)
    monkeypatch.setattr(ci_mod, "get_settings", lambda: s)
    monkeypatch.setattr(rm_mod, "get_settings", lambda: s)
    monkeypatch.setattr(restart_mod, "get_settings", lambda: s)
    monkeypatch.setattr(system_state_mod, "get_settings", lambda: s)
    monkeypatch.setattr(health_route, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "_github_client", None, raising=False)
    monkeypatch.setattr(ci_mod, "_monitor", None, raising=False)
    monkeypatch.setattr(rm_mod, "_monitor", None, raising=False)
    monkeypatch.setattr(system_state_mod, "_store", None, raising=False)
    return s


@pytest.fixture
def fresh_store(tmp_path, monkeypatch) -> si_proposal.ProposalStore:
    db = tmp_path / "audit_test_73e.db"
    store = si_proposal.ProposalStore(db_path=db)
    monkeypatch.setattr(si_proposal, "_proposal_store", store, raising=False)
    return store


@pytest.fixture
def fresh_system_state(tmp_path, monkeypatch) -> system_state_mod.SystemStateStore:
    """Independent system-state store backed by its own DB.

    The default singleton uses ``settings.nexa_data_dir`` which we override
    via the ``settings`` fixture's ``""`` to an empty string → ``data/``.
    Tests that need a clean store should depend on this fixture explicitly.
    """
    db = tmp_path / "audit_test_73e_sysstate.db"
    store = system_state_mod.SystemStateStore(db_path=db)
    monkeypatch.setattr(system_state_mod, "_store", store, raising=False)
    return store


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


# =============================================================================
# SystemStateStore
# =============================================================================


def test_system_state_set_get_roundtrip(tmp_path) -> None:
    store = system_state_mod.SystemStateStore(db_path=tmp_path / "ss.db")
    assert store.get("missing") is None
    store.set("k1", "v1")
    got = store.get("k1")
    assert got is not None
    assert got[0] == "v1"
    # updated_at is a SQLite timestamp string; we don't pin its format.
    assert got[1]
    assert store.get_value("k1") == "v1"


def test_system_state_touch_heartbeat_age(tmp_path) -> None:
    store = system_state_mod.SystemStateStore(db_path=tmp_path / "ss.db")
    assert store.heartbeat_age_seconds() is None
    store.touch_heartbeat()
    age = store.heartbeat_age_seconds()
    assert age is not None
    assert 0.0 <= age < 5.0


def test_system_state_in_auto_revert_cooldown(tmp_path) -> None:
    store = system_state_mod.SystemStateStore(db_path=tmp_path / "ss.db")
    # No record → never in cooldown.
    assert store.in_auto_revert_cooldown(30) is False
    store.mark_auto_revert(proposal_id="abc")
    assert store.in_auto_revert_cooldown(30) is True
    # Cooldown of 0 disables the gate explicitly.
    assert store.in_auto_revert_cooldown(0) is False


def test_system_state_process_age(tmp_path) -> None:
    store = system_state_mod.SystemStateStore(db_path=tmp_path / "ss.db")
    assert store.process_age_seconds() is None
    store.mark_process_started()
    age = store.process_age_seconds()
    assert age is not None
    assert age >= 0.0


# =============================================================================
# Proposal store: 73e columns + setters
# =============================================================================


def _make_pending(store: si_proposal.ProposalStore, *, title: str = "t") -> si_proposal.Proposal:
    return store.create(
        title=title, problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )


def test_proposal_columns_default_to_none_or_false(fresh_store) -> None:
    p = _make_pending(fresh_store)
    refreshed = fresh_store.get(p.id)
    assert refreshed is not None
    assert refreshed.auto_revert_state is None
    assert refreshed.auto_revert_decided_at is None
    assert refreshed.auto_revert_disabled is False
    assert refreshed.merged_at is None


def test_set_github_state_to_merged_seeds_watching_and_merged_at(fresh_store) -> None:
    p = _make_pending(fresh_store)
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=1, pr_url="u", github_branch="b",
    )
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_MERGED,
        merge_commit_sha="abc123",
    )
    refreshed = fresh_store.get(p.id)
    assert refreshed.status == si_proposal.STATUS_MERGED
    assert refreshed.merged_at is not None
    assert refreshed.auto_revert_state == "watching"


def test_set_github_state_to_merged_respects_pre_disabled(fresh_store) -> None:
    p = _make_pending(fresh_store)
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_auto_revert_disabled(p.id, disabled=True)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=1, pr_url="u", github_branch="b",
    )
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_MERGED,
        merge_commit_sha="abc",
    )
    refreshed = fresh_store.get(p.id)
    # disabled stays disabled; the state column reflects that.
    assert refreshed.auto_revert_disabled is True
    assert refreshed.auto_revert_state == "disabled"


def test_set_auto_revert_disabled_flips_state(fresh_store) -> None:
    p = _make_pending(fresh_store)
    fresh_store.set_auto_revert_disabled(p.id, disabled=True)
    r1 = fresh_store.get(p.id)
    assert r1.auto_revert_disabled is True
    assert r1.auto_revert_state == "disabled"
    # Re-arming → state becomes 'watching' again.
    fresh_store.set_auto_revert_disabled(p.id, disabled=False)
    r2 = fresh_store.get(p.id)
    assert r2.auto_revert_disabled is False
    assert r2.auto_revert_state == "watching"


def test_set_auto_revert_disabled_does_not_clobber_terminal_states(fresh_store) -> None:
    """Re-arm after a revert/clear must NOT downgrade to 'watching'."""
    p = _make_pending(fresh_store)
    fresh_store.set_auto_revert_state(p.id, state="reverted")
    fresh_store.set_auto_revert_disabled(p.id, disabled=False)
    refreshed = fresh_store.get(p.id)
    assert refreshed.auto_revert_state == "reverted"


def test_list_recent_merged_within_filters_by_window(fresh_store) -> None:
    # No merged proposals yet.
    assert fresh_store.list_recent_merged_within(window_seconds=300) == []
    p = _make_pending(fresh_store)
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=1, pr_url="u", github_branch="b",
    )
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_MERGED,
        merge_commit_sha="abc",
    )
    rows = fresh_store.list_recent_merged_within(window_seconds=300)
    assert len(rows) == 1
    assert rows[0].id == p.id
    # Backdate merged_at way past the window.
    with fresh_store._connect() as conn:
        conn.execute(
            "UPDATE self_improvement_proposals SET merged_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", p.id),
        )
    rows2 = fresh_store.list_recent_merged_within(window_seconds=300)
    assert rows2 == []


def test_list_recent_merged_within_includes_revert_pr_open(fresh_store) -> None:
    """Once we move to revert_pr_open the monitor still sees the row so it
    can mark it 'cleared' and stop polling."""
    p = _make_pending(fresh_store)
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=1, pr_url="u", github_branch="b",
    )
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_MERGED, merge_commit_sha="abc",
    )
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_REVERT_PR_OPEN,
        revert_pr_number=99, revert_pr_url="urev",
    )
    rows = fresh_store.list_recent_merged_within(window_seconds=300)
    assert len(rows) == 1
    assert rows[0].status == si_proposal.STATUS_REVERT_PR_OPEN


# =============================================================================
# fetch_error_rate_window (querying agent_audit.db)
# =============================================================================


def test_fetch_error_rate_window_returns_zeros_when_no_db(settings, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "nexa_data_dir", str(tmp_path / "missing"))
    out = rm_mod.fetch_error_rate_window(window_seconds=300)
    assert out == {"total": 0, "errors": 0, "error_rate": 0.0, "window_seconds": 300}


def test_fetch_error_rate_window_aggregates_recent_rows(settings, tmp_path, monkeypatch) -> None:
    """Seed the agent_audit.db ``agent_actions`` table directly and verify
    the rolling window aggregator reports the right counts.

    The activity-tracker singleton resolves its DB path from the *real*
    ``get_settings()`` at construction time, so we patch its module-level
    name explicitly (the global ``settings`` fixture only patches the
    aggregator's view).
    """
    import sqlite3

    monkeypatch.setattr(settings, "nexa_data_dir", str(tmp_path))
    db_path = tmp_path / "agent_audit.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                agent_name TEXT,
                action_type TEXT NOT NULL,
                input TEXT, output TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                error TEXT, duration_ms REAL, metadata TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        for _ in range(7):
            conn.execute(
                "INSERT INTO agent_actions (agent_id, action_type, success) VALUES (?, ?, ?)",
                ("a", "x", 1),
            )
        for _ in range(3):
            conn.execute(
                "INSERT INTO agent_actions (agent_id, action_type, success, error) VALUES (?, ?, ?, ?)",
                ("a", "x", 0, "boom"),
            )
        conn.commit()
    finally:
        conn.close()
    out = rm_mod.fetch_error_rate_window(window_seconds=600)
    assert out["total"] == 10
    assert out["errors"] == 3
    assert abs(out["error_rate"] - 0.3) < 1e-6


# =============================================================================
# RevertMonitor.scan_once
# =============================================================================


class _FakeRevertGitHub:
    def __init__(self, *, raise_on_open: gh_mod.GitHubError | None = None) -> None:
        self.enabled = True
        self.has_token = True
        self.opened: list[dict[str, Any]] = []
        self._raise = raise_on_open

    async def open_revert_pr(self, *, merge_commit_sha: str, title: str, body: str):
        if self._raise is not None:
            raise self._raise
        self.opened.append(
            {"merge_commit_sha": merge_commit_sha, "title": title, "body": body}
        )

        class _PR:
            number = 999
            url = "https://example/pr/999"
            head_branch = "self-improvement/revert-x"
            base_branch = "main"

        return _PR()


def _seed_merged(store: si_proposal.ProposalStore) -> si_proposal.Proposal:
    p = _make_pending(store)
    store.set_status(p.id, si_proposal.STATUS_APPROVED)
    store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=42, pr_url="u", github_branch="b",
    )
    store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_MERGED,
        merge_commit_sha="merge_sha_xyz",
    )
    return store.get(p.id)


def test_scan_once_no_merged_proposals_returns_zero_counters(
    settings, fresh_store, fresh_system_state
) -> None:
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=_FakeRevertGitHub())
    counters = asyncio.run(monitor.scan_once())
    assert counters["scanned"] == 0
    assert counters["reverted"] == 0


def test_scan_once_skips_when_post_restart_grace_not_elapsed(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_post_restart_grace_seconds = 60
    fresh_system_state.mark_process_started()  # process age ~ 0s
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    # Force enough errors to trip the threshold.
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 50, "errors": 25, "error_rate": 0.5,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["scanned"] == 1
    assert counters["skipped_grace"] == 1
    assert counters["reverted"] == 0
    assert fake.opened == []


def test_scan_once_skips_when_below_min_sample(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_min_sample_size = 10
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 8, "errors": 8, "error_rate": 1.0,  # 100% but only 8 mistakes
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["skipped_low_sample"] == 1
    assert counters["reverted"] == 0
    refreshed = fresh_store.get(p.id)
    assert refreshed.auto_revert_state == "watching"
    assert fake.opened == []


def test_scan_once_skips_when_below_threshold(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_min_sample_size = 5
    settings.nexa_self_improvement_revert_error_rate_threshold = 0.5
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 100, "errors": 20, "error_rate": 0.2,  # 20% < 50%
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["skipped_below_threshold"] == 1
    assert counters["reverted"] == 0
    refreshed = fresh_store.get(p.id)
    assert refreshed.auto_revert_state == "watching"


def test_scan_once_fires_revert_when_all_gates_pass(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_min_sample_size = 5
    settings.nexa_self_improvement_revert_error_rate_threshold = 0.3
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 30, "errors": 15, "error_rate": 0.5,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["reverted"] == 1
    assert len(fake.opened) == 1
    assert fake.opened[0]["merge_commit_sha"] == "merge_sha_xyz"
    refreshed = fresh_store.get(p.id)
    assert refreshed.status == si_proposal.STATUS_REVERT_PR_OPEN
    assert refreshed.revert_pr_number == 999
    assert refreshed.auto_revert_state == "reverted"
    # System state cooldown stamp recorded.
    assert fresh_system_state.last_auto_revert_age_seconds() is not None


def test_scan_once_honours_per_proposal_disable(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_min_sample_size = 1
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    fresh_store.set_auto_revert_disabled(p.id, disabled=True)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 20, "errors": 20, "error_rate": 1.0,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["skipped_disabled"] == 1
    assert counters["reverted"] == 0
    assert fake.opened == []


def test_scan_once_marks_revert_pr_open_as_cleared_and_stops(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    """If a proposal is already in ``revert_pr_open`` we don't fire again."""
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_REVERT_PR_OPEN,
        revert_pr_number=11, revert_pr_url="urev",
    )
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 100, "errors": 100, "error_rate": 1.0,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["cleared"] == 1
    assert counters["reverted"] == 0
    refreshed = fresh_store.get(p.id)
    assert refreshed.auto_revert_state == "cleared"


def test_scan_once_swallows_github_error_and_increments_counter(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_revert_min_sample_size = 1
    fake = _FakeRevertGitHub(
        raise_on_open=gh_mod.GitHubError("open_pr_failed_500", "boom")
    )
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    _seed_merged(fresh_store)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 10, "errors": 10, "error_rate": 1.0,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["revert_errors"] == 1
    assert counters["reverted"] == 0


def test_scan_once_clears_when_no_merge_commit_sha(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    """Defensive: a merged row with empty merge_commit_sha cannot be reverted."""
    settings.nexa_self_improvement_revert_min_sample_size = 1
    fake = _FakeRevertGitHub()
    monitor = rm_mod.RevertMonitor(store=fresh_store, client=fake)
    p = _seed_merged(fresh_store)
    with fresh_store._connect() as conn:
        conn.execute(
            "UPDATE self_improvement_proposals SET merge_commit_sha = '' WHERE id = ?",
            (p.id,),
        )
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 10, "errors": 10, "error_rate": 1.0,
            "window_seconds": window_seconds,
        },
    )
    counters = asyncio.run(monitor.scan_once())
    assert counters["cleared"] == 1
    assert fake.opened == []


# =============================================================================
# CiMonitor cooldown gate (73e × 73d integration)
# =============================================================================


class _FakeCi:
    def __init__(self, state: str) -> None:
        self.state = state
        self.head_sha = "h"
        self.checks: list = []
        self.total_count = 0


class _FakeMerge:
    merge_commit_sha = "auto_merged_xxx"
    merged = True


class _FakeCiMonitorGitHub:
    def __init__(self) -> None:
        self.enabled = True
        self.has_token = True
        self.pr_title_prefix = "[self-improvement]"
        self.merge_calls: list[int] = []

    async def get_pr_ci_status(self, pr_number: int) -> _FakeCi:
        return _FakeCi("success")

    async def merge_pull_request(self, pr_number: int, *, commit_title=None, commit_message=None):
        self.merge_calls.append(pr_number)
        return _FakeMerge()


def test_ci_monitor_pauses_auto_merge_during_revert_cooldown(
    settings, fresh_store, fresh_system_state
) -> None:
    """When system_state.last_auto_revert is fresh, ci_monitor must NOT
    auto-merge even if CI is green and sandbox is fresh."""
    fake = _FakeCiMonitorGitHub()
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pending(fresh_store)
    fresh_store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.0})
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=42, pr_url="u", github_branch="b",
    )
    fresh_store.set_auto_merge_on_ci(p.id, enabled=True)
    # Trip the cooldown.
    fresh_system_state.mark_auto_revert(proposal_id="other-id")
    counters = asyncio.run(monitor.scan_once())
    # ci_state recorded as success; the cooldown gate keeps merge_calls empty.
    refreshed = fresh_store.get(p.id)
    assert refreshed.ci_state == "success"
    assert fake.merge_calls == []
    assert counters["merged"] == 0


def test_ci_monitor_auto_merges_after_cooldown_expires(
    settings, fresh_store, fresh_system_state
) -> None:
    settings.nexa_self_improvement_revert_cooldown_minutes = 0  # cooldown disabled
    fake = _FakeCiMonitorGitHub()
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pending(fresh_store)
    fresh_store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.0})
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=42, pr_url="u", github_branch="b",
    )
    fresh_store.set_auto_merge_on_ci(p.id, enabled=True)
    fresh_system_state.mark_auto_revert(proposal_id="other-id")
    counters = asyncio.run(monitor.scan_once())
    assert counters["merged"] == 1
    assert fake.merge_calls == [42]


# =============================================================================
# API: capabilities, /{id}/auto-revert, /-/revert-scan-now
# =============================================================================


def test_capabilities_exposes_auto_revert_block(settings, fresh_store, fresh_system_state) -> None:
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/-/capabilities")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "auto_revert" in body
        assert body["auto_revert"]["enabled"] is True
        assert body["auto_revert"]["threshold"] == pytest.approx(0.3)
        assert body["auto_revert"]["min_sample_size"] == 10
        assert body["auto_revert"]["cooldown_minutes"] == 30
        assert body["auto_revert"]["in_cooldown"] is False
    finally:
        app.dependency_overrides.clear()


def test_set_auto_revert_disabled_endpoint_owner_only(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = _make_pending(fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(
            f"/api/v1/self_improvement/{p.id}/auto-revert",
            json={"disabled": True},
        )
        assert r.status_code == 200, r.text
        assert r.json()["auto_revert_disabled"] is True
        assert r.json()["proposal"]["auto_revert_disabled"] is True
        # Re-enable.
        r2 = client.post(
            f"/api/v1/self_improvement/{p.id}/auto-revert",
            json={"disabled": False},
        )
        assert r2.json()["auto_revert_disabled"] is False
    finally:
        app.dependency_overrides.clear()


def test_set_auto_revert_endpoint_403_for_non_owner(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "member")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = _make_pending(fresh_store)
    _override_user("tg_member")
    try:
        client = TestClient(app)
        r = client.post(
            f"/api/v1/self_improvement/{p.id}/auto-revert",
            json={"disabled": True},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_revert_scan_now_returns_disabled_when_global_flag_off(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_self_improvement_auto_revert_enabled = False
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post("/api/v1/self_improvement/-/revert-scan-now")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "disabled"
        assert body["counters"] is None
    finally:
        app.dependency_overrides.clear()


def test_revert_scan_now_returns_counters_when_enabled(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    # Patch the singleton so the endpoint uses our store + a fake client.
    fake = _FakeRevertGitHub()
    monkeypatch.setattr(
        rm_mod, "_monitor",
        rm_mod.RevertMonitor(store=fresh_store, client=fake),
        raising=False,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post("/api/v1/self_improvement/-/revert-scan-now")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "scanned"
        assert isinstance(body["counters"], dict)
        assert "scanned" in body["counters"]
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# /health/detailed endpoint
# =============================================================================


def test_health_detailed_shape(settings, fresh_store, fresh_system_state, monkeypatch) -> None:
    fresh_system_state.mark_process_started()
    fresh_system_state.touch_heartbeat()
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 12, "errors": 2, "error_rate": 12 / 100,  # use mismatch to verify wiring
            "window_seconds": window_seconds,
        },
    )
    _override_user("tg_user")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["app"] == "AethOS-test"
        assert body["env"] == "test"
        # Process / heartbeat present.
        assert body["process"]["age_seconds"] is not None
        assert body["heartbeat"]["age_seconds"] is not None
        assert body["heartbeat"]["stale"] is False
        # Errors reflect the patched aggregator.
        assert body["errors"]["total_actions"] == 12
        assert body["errors"]["errors"] == 2
        # Auto-revert wiring.
        assert body["auto_revert"]["enabled"] is True
        assert body["auto_revert"]["threshold"] == pytest.approx(0.3)
        assert body["auto_revert"]["in_cooldown"] is False
        # No deploy in window → null.
        assert body["last_deploy"] is None
    finally:
        app.dependency_overrides.clear()


def test_health_detailed_reports_last_deploy_when_within_window(
    settings, fresh_store, fresh_system_state, monkeypatch
) -> None:
    p = _seed_merged(fresh_store)
    monkeypatch.setattr(
        rm_mod, "fetch_error_rate_window",
        lambda window_seconds: {
            "total": 0, "errors": 0, "error_rate": 0.0,
            "window_seconds": window_seconds,
        },
    )
    _override_user("tg_user")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["last_deploy"] is not None
        assert body["last_deploy"]["proposal_id"] == p.id
        assert body["last_deploy"]["merge_commit_sha"] == "merge_sha_xyz"
        assert body["last_deploy"]["auto_revert_state"] == "watching"
        # The remaining-window value should be > 0 (we just merged).
        assert body["last_deploy"]["observation_window_remaining_seconds"] > 0
    finally:
        app.dependency_overrides.clear()


def test_health_detailed_in_cooldown_after_revert(
    settings, fresh_store, fresh_system_state
) -> None:
    fresh_system_state.mark_auto_revert(proposal_id="abc")
    _override_user("tg_user")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/health/detailed")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["auto_revert"]["in_cooldown"] is True
        assert body["auto_revert"]["last_auto_revert_age_seconds"] is not None
        assert body["auto_revert"]["last_auto_revert_proposal_id"] == "abc"
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# Phase 73e integration: heartbeat persists last_heartbeat_at
# =============================================================================


def test_heartbeat_cycle_persists_last_heartbeat_at(
    settings, fresh_system_state, monkeypatch
) -> None:
    settings.nexa_heartbeat_enabled = True
    # The heartbeat module reads its own get_settings; patch it for the test.
    import app.services.scheduler.heartbeat as hb_mod
    monkeypatch.setattr(hb_mod, "get_settings", lambda: settings)
    out = hb_mod.run_heartbeat_cycle()
    assert out.get("ok") is True
    age = fresh_system_state.heartbeat_age_seconds()
    assert age is not None
    assert age < 5.0
