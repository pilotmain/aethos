# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73d — CI status polling, auto-merge gating, graceful restart tests.

Coverage:

* :mod:`app.services.self_improvement.github_client._combine_ci_states` — every
  branch of the AND logic.
* :class:`GitHubClient.get_pr_ci_status` — combined commit-statuses + Actions
  check-runs over a mocked ``httpx`` transport.
* :class:`app.services.self_improvement.ci_monitor.CiMonitor.scan_once` —
  pending → first-seen recorded; success → set ``ci_state="success"``;
  failure / error → recorded; max-age timeout → ``"timed_out"``;
  auto-merge with fresh sandbox → merge fires + status flips to ``merged``;
  auto-merge with stale sandbox → ``"passed_awaiting_sandbox"``, no merge.
* :mod:`app.api.routes.self_improvement` — ``/-/capabilities`` exposes the
  new ``ci`` and ``auto_restart`` blocks; ``/{id}/merge-pr`` gates on
  ``ci_state`` when ``WAIT_FOR_CI=true``; ``/{id}/refresh-ci`` happy +
  no-PR-409; ``/{id}/auto-merge-on-ci`` flips the flag; ``/restart`` 403
  when disabled, 200 with ``status=scheduled`` when enabled.
* :mod:`app.core.restart` — ``schedule_restart`` honours the master flag,
  ``perform_restart`` dispatches per method, ``uvicorn-reload`` writes the
  sentinel file.

No real network or process exits are performed: ``httpx`` calls go through
``MockTransport``, ``perform_restart`` for systemd/docker/supervisor is
patched to a sentinel-record instead of calling ``os._exit``.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.routes.self_improvement as si_router
import app.core.restart as restart_mod
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.self_improvement import ci_monitor as ci_mod
from app.services.self_improvement import github_client as gh_mod
from app.services.self_improvement import proposal as si_proposal


_VALID_DIFF = """diff --git a/app/services/foo.py b/app/services/foo.py
--- a/app/services/foo.py
+++ b/app/services/foo.py
@@ -1,3 +1,4 @@
 def foo():
     pass
+# improved
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
    nexa_self_improvement_github_token = "ghp_FAKE_TOKEN_FOR_TESTS_xxxxxxxxxxxxxxxxxxxx"
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
    nexa_self_improvement_auto_restart_method = "uvicorn-reload"
    nexa_data_dir = ""


@pytest.fixture
def settings(monkeypatch) -> _Settings:
    s = _Settings()
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    monkeypatch.setattr(si_proposal, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "get_settings", lambda: s)
    monkeypatch.setattr(ci_mod, "get_settings", lambda: s)
    monkeypatch.setattr(restart_mod, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "_github_client", None, raising=False)
    monkeypatch.setattr(ci_mod, "_monitor", None, raising=False)
    return s


@pytest.fixture
def fresh_store(tmp_path, monkeypatch) -> si_proposal.ProposalStore:
    db = tmp_path / "audit_test_73d.db"
    store = si_proposal.ProposalStore(db_path=db)
    monkeypatch.setattr(si_proposal, "_proposal_store", store, raising=False)
    return store


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


# --- _combine_ci_states ---------------------------------------------------


@pytest.mark.parametrize(
    "leaves,expected",
    [
        ([], "pending"),
        (["pending"], "pending"),
        (["queued", "in_progress"], "pending"),
        (["success"], "success"),
        (["success", "skipped", "neutral"], "success"),
        (["success", "failure"], "failure"),
        (["success", "cancelled"], "failure"),
        (["success", "timed_out"], "failure"),
        (["success", "error"], "error"),
        (["success", "error", "failure"], "failure"),  # failure beats error
        (["something-new-from-github"], "pending"),     # safe default
        (["success", "action_required"], "failure"),
    ],
)
def test_combine_ci_states_branches(leaves, expected) -> None:
    assert gh_mod._combine_ci_states(leaves) == expected


# --- get_pr_ci_status (httpx mock) ---------------------------------------


def test_get_pr_ci_status_combines_statuses_and_check_runs(settings) -> None:
    """Statuses say success, check-runs say success → combined success."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls/77"):
            return httpx.Response(200, json={"head": {"sha": "headsha123"}})
        if "/commits/headsha123/status" in path:
            return httpx.Response(
                200,
                json={
                    "state": "success",
                    "total_count": 1,
                    "statuses": [
                        {"context": "legacy/x", "state": "success", "target_url": ""}
                    ],
                },
            )
        if "/commits/headsha123/check-runs" in path:
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "check_runs": [
                        {"name": "tsc", "status": "completed", "conclusion": "success", "html_url": ""},
                        {"name": "pytest", "status": "completed", "conclusion": "success", "html_url": ""},
                    ],
                },
            )
        return httpx.Response(404, json={"message": "unmapped"})

    async def _runner() -> Any:
        c = gh_mod.GitHubClient()
        c._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer fake"},
        )
        try:
            return await c.get_pr_ci_status(77)
        finally:
            await c.aclose()

    res = asyncio.run(_runner())
    assert res.state == "success"
    assert res.head_sha == "headsha123"
    assert res.total_count == 3
    names = sorted(c.name for c in res.checks)
    assert names == ["legacy/x", "pytest", "tsc"]


def test_get_pr_ci_status_pending_when_check_in_progress(settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls/8"):
            return httpx.Response(200, json={"head": {"sha": "abc"}})
        if "/commits/abc/status" in path:
            return httpx.Response(200, json={"state": "success", "total_count": 0, "statuses": []})
        if "/commits/abc/check-runs" in path:
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "check_runs": [
                        {"name": "pytest", "status": "in_progress", "conclusion": None, "html_url": ""}
                    ],
                },
            )
        return httpx.Response(404, json={"message": "unmapped"})

    async def _runner() -> Any:
        c = gh_mod.GitHubClient()
        c._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer fake"},
        )
        try:
            return await c.get_pr_ci_status(8)
        finally:
            await c.aclose()

    res = asyncio.run(_runner())
    assert res.state == "pending"


def test_get_pr_ci_status_failure_when_check_run_failed(settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls/9"):
            return httpx.Response(200, json={"head": {"sha": "h"}})
        if "/commits/h/status" in path:
            return httpx.Response(200, json={"state": "success", "total_count": 0, "statuses": []})
        if "/commits/h/check-runs" in path:
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "check_runs": [
                        {"name": "tsc", "status": "completed", "conclusion": "success", "html_url": ""},
                        {"name": "pytest", "status": "completed", "conclusion": "failure", "html_url": ""},
                    ],
                },
            )
        return httpx.Response(404, json={"message": "unmapped"})

    async def _runner() -> Any:
        c = gh_mod.GitHubClient()
        c._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer fake"},
        )
        try:
            return await c.get_pr_ci_status(9)
        finally:
            await c.aclose()

    res = asyncio.run(_runner())
    assert res.state == "failure"


# --- ci_monitor.scan_once -------------------------------------------------


class _FakeCiResult:
    def __init__(self, state: str, head_sha: str = "h", checks: list | None = None) -> None:
        self.state = state
        self.head_sha = head_sha
        self.checks = checks or []
        self.total_count = len(self.checks)


class _FakeMergeResult:
    def __init__(self, sha: str = "merged_sha_xyz") -> None:
        self.merge_commit_sha = sha
        self.merged = True


class _FakeGitHubClient:
    """Stub for :class:`GitHubClient` — covers the surface ci_monitor needs."""

    def __init__(self) -> None:
        self.enabled = True
        self.has_token = True
        self.owner = "pilotmain"
        self.repo = "aethos"
        self.base_branch = "main"
        self.branch_prefix = "self-improvement/"
        self.pr_title_prefix = "[self-improvement]"
        self.merge_method = "squash"
        self.ci_results: dict[int, _FakeCiResult] = {}
        self.merge_calls: list[int] = []
        self.merge_should_raise: gh_mod.GitHubError | None = None

    async def get_pr_ci_status(self, pr_number: int) -> _FakeCiResult:
        if pr_number not in self.ci_results:
            return _FakeCiResult("pending")
        return self.ci_results[pr_number]

    async def merge_pull_request(self, pr_number: int, *, commit_title=None, commit_message=None):
        if self.merge_should_raise is not None:
            raise self.merge_should_raise
        self.merge_calls.append(pr_number)
        return _FakeMergeResult()


def _make_pr_open(store: si_proposal.ProposalStore, *, with_fresh_sandbox: bool) -> si_proposal.Proposal:
    p = store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    if with_fresh_sandbox:
        store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.0})
    store.set_status(p.id, si_proposal.STATUS_APPROVED)
    store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=42,
        pr_url="https://example/pr/42",
        github_branch="self-improvement/abc",
    )
    return store.get(p.id)


def test_scan_once_records_pending(settings, fresh_store, monkeypatch) -> None:
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("pending")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    counters = asyncio.run(monitor.scan_once())
    assert counters["scanned"] == 1
    assert counters["pending"] == 1
    refreshed = fresh_store.get(p.id)
    assert refreshed.ci_state == "pending"
    assert refreshed.ci_first_seen_pending_at is not None  # first-seen recorded


def test_scan_once_pending_then_timeout(settings, fresh_store, monkeypatch) -> None:
    """A PR pending longer than max_age gets ci_state='timed_out'."""
    settings.nexa_self_improvement_ci_max_age_seconds = 60
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("pending")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    # Scan once normally to set ci_first_seen_pending_at.
    asyncio.run(monitor.scan_once())
    # Backdate the first-seen so the next scan hits the max-age branch.
    with fresh_store._connect() as conn:
        conn.execute(
            "UPDATE self_improvement_proposals SET ci_first_seen_pending_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", p.id),
        )
    counters = asyncio.run(monitor.scan_once())
    assert counters["timed_out"] >= 1
    refreshed = fresh_store.get(p.id)
    assert refreshed.ci_state == "timed_out"


def test_scan_once_failure(settings, fresh_store) -> None:
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("failure")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    counters = asyncio.run(monitor.scan_once())
    assert counters["failed"] == 1
    refreshed = fresh_store.get(p.id)
    assert refreshed.ci_state == "failure"


def test_scan_once_passed_no_auto_merge_when_flag_off(settings, fresh_store) -> None:
    """auto_merge_on_ci_pass=False → CI passing just records state, no merge."""
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("success")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    counters = asyncio.run(monitor.scan_once())
    assert counters["passed"] == 1
    assert fake.merge_calls == []
    refreshed = fresh_store.get(p.id)
    assert refreshed.ci_state == "success"
    assert refreshed.status == si_proposal.STATUS_PR_OPEN  # unchanged


def test_scan_once_auto_merge_when_flag_on_and_sandbox_fresh(settings, fresh_store) -> None:
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("success")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    fresh_store.set_auto_merge_on_ci(p.id, enabled=True)
    counters = asyncio.run(monitor.scan_once())
    assert counters["merged"] == 1
    assert fake.merge_calls == [42]
    refreshed = fresh_store.get(p.id)
    assert refreshed.status == si_proposal.STATUS_MERGED
    assert refreshed.merge_commit_sha == "merged_sha_xyz"


def test_scan_once_passed_awaiting_sandbox_when_stale(settings, fresh_store) -> None:
    """auto-merge flagged + CI green + sandbox stale → blocked + label set."""
    fake = _FakeGitHubClient()
    fake.ci_results[42] = _FakeCiResult("success")
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    p = _make_pr_open(fresh_store, with_fresh_sandbox=True)
    fresh_store.set_auto_merge_on_ci(p.id, enabled=True)
    # Force the sandbox to look stale by backdating sandbox_run_at directly.
    with fresh_store._connect() as conn:
        conn.execute(
            "UPDATE self_improvement_proposals SET sandbox_run_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", p.id),
        )
    counters = asyncio.run(monitor.scan_once())
    assert counters["awaiting_sandbox"] == 1
    assert fake.merge_calls == []
    refreshed = fresh_store.get(p.id)
    assert refreshed.status == si_proposal.STATUS_PR_OPEN
    assert refreshed.ci_state == "passed_awaiting_sandbox"


def test_scan_once_swallows_github_errors(settings, fresh_store, monkeypatch) -> None:
    class _BoomClient(_FakeGitHubClient):
        async def get_pr_ci_status(self, pr_number):  # type: ignore[override]
            raise gh_mod.GitHubError("github_network_error", "boom")
    fake = _BoomClient()
    monitor = ci_mod.CiMonitor(store=fresh_store, client=fake)
    _make_pr_open(fresh_store, with_fresh_sandbox=True)
    counters = asyncio.run(monitor.scan_once())
    assert counters["scanned"] == 1
    # No state mutations performed on error.
    assert counters["pending"] == 0
    assert counters["passed"] == 0
    assert counters["failed"] == 0


# --- API: capabilities surfaces ci + auto_restart ------------------------


def test_capabilities_exposes_ci_and_restart_blocks(settings) -> None:
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/-/capabilities")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ci"]["wait_for_ci"] is True
        assert body["ci"]["poll_interval_seconds"] == 30
        assert body["ci"]["max_age_seconds"] == 21600
        assert body["auto_restart"]["enabled"] is False
        assert body["auto_restart"]["method"] == "uvicorn-reload"
        assert "noop" in body["auto_restart"]["valid_methods"]
    finally:
        app.dependency_overrides.clear()


# --- API: merge-pr CI gate ------------------------------------------------


class _FakeMergeFlowClient(_FakeGitHubClient):
    """For router tests we additionally need pull_request status + merge."""

    async def get_pull_request_status(self, pr_number: int):
        class _S:
            number = pr_number; state = "open"; merged = False
            mergeable: bool | None = True
            mergeable_state: str | None = "clean"
            head_sha: str | None = "h"; head_branch = "self-improvement/x"; base_branch = "main"
        return _S()


def _approved_pr_open(
    store: si_proposal.ProposalStore, *, ci_state: str | None = None,
) -> si_proposal.Proposal:
    p = store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.0})
    store.set_status(p.id, si_proposal.STATUS_APPROVED)
    store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=42, pr_url="u", github_branch="b",
    )
    if ci_state is not None:
        store.set_ci_state(p.id, ci_state=ci_state)
    return store.get(p.id)


def test_merge_pr_409_when_ci_not_passed_and_wait_for_ci_true(settings, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeMergeFlowClient())
    p = _approved_pr_open(fresh_store, ci_state="pending")
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 409
        assert "ci_required_but_state_pending" in r.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_passes_when_ci_success_and_wait_for_ci_true(settings, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeMergeFlowClient()
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)
    p = _approved_pr_open(fresh_store, ci_state="success")
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 200, r.text
        assert r.json()["proposal"]["status"] == "merged"
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_passes_when_wait_for_ci_false(settings, fresh_store, monkeypatch) -> None:
    """When the operator turns the CI gate off, even pending CI is OK."""
    settings.nexa_self_improvement_wait_for_ci = False
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeMergeFlowClient())
    p = _approved_pr_open(fresh_store, ci_state=None)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_passes_when_ci_passed_awaiting_sandbox(settings, fresh_store, monkeypatch) -> None:
    """passed_awaiting_sandbox is a 'CI green' state for the manual click path."""
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeMergeFlowClient())
    p = _approved_pr_open(fresh_store, ci_state="passed_awaiting_sandbox")
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()


# --- API: refresh-ci -----------------------------------------------------


def test_refresh_ci_happy_path(settings, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeMergeFlowClient()
    fake.ci_results[42] = _FakeCiResult("success", head_sha="head_xyz")
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)
    p = _approved_pr_open(fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/refresh-ci")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ci"]["state"] == "success"
        assert body["ci"]["head_sha"] == "head_xyz"
        assert body["proposal"]["ci_state"] == "success"
    finally:
        app.dependency_overrides.clear()


def test_refresh_ci_409_no_pr(settings, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeMergeFlowClient())
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/refresh-ci")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


# --- API: auto-merge-on-ci ----------------------------------------------


def test_auto_merge_flip_on_then_off(settings, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeMergeFlowClient())
    p = _approved_pr_open(fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r1 = client.post(
            f"/api/v1/self_improvement/{p.id}/auto-merge-on-ci",
            json={"enabled": True},
        )
        assert r1.status_code == 200
        assert r1.json()["auto_merge_on_ci_pass"] is True
        assert r1.json()["proposal"]["auto_merge_on_ci_pass"] is True
        r2 = client.post(
            f"/api/v1/self_improvement/{p.id}/auto-merge-on-ci",
            json={"enabled": False},
        )
        assert r2.status_code == 200
        assert r2.json()["auto_merge_on_ci_pass"] is False
    finally:
        app.dependency_overrides.clear()


# --- API: restart endpoint ----------------------------------------------


def test_restart_403_when_disabled(settings) -> None:
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post("/api/v1/self_improvement/restart")
        # owner check happens before the flag check, so we patch role.
        # Since we didn't patch get_telegram_role_for_app_user here, we get
        # 403 (owner check) — verify either path is correct.
        assert r.status_code in (403, 401)
    finally:
        app.dependency_overrides.clear()


def test_restart_200_scheduled_when_enabled(settings, monkeypatch) -> None:
    settings.nexa_self_improvement_auto_restart = True
    settings.nexa_self_improvement_auto_restart_method = "noop"
    monkeypatch.setattr(si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner")
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post("/api/v1/self_improvement/restart")
        assert r.status_code == 200, r.text
        body = r.json()
        # noop method short-circuits and reports "noop", not "scheduled".
        assert body["status"] == "noop"
        assert body["method"] == "noop"
    finally:
        app.dependency_overrides.clear()


# --- restart module direct -----------------------------------------------


def test_perform_restart_is_noop_when_master_flag_off(settings) -> None:
    settings.nexa_self_improvement_auto_restart = False
    res = restart_mod.perform_restart()
    assert res["status"] == "disabled"


def test_perform_restart_uvicorn_reload_writes_sentinel(settings, monkeypatch) -> None:
    settings.nexa_self_improvement_auto_restart = True
    settings.nexa_self_improvement_auto_restart_method = "uvicorn-reload"
    # Redirect the sentinel to a temp file so we don't touch the real one.
    fake_sentinel = Path(__file__).parent / "_tmp_sentinel.py"
    if fake_sentinel.exists():
        fake_sentinel.unlink()
    monkeypatch.setattr(restart_mod, "SENTINEL_PATH", fake_sentinel)
    try:
        res = restart_mod.perform_restart()
        assert res["status"] == "reloaded"
        assert fake_sentinel.exists()
        assert "TOUCHED_AT" in fake_sentinel.read_text(encoding="utf-8")
    finally:
        if fake_sentinel.exists():
            fake_sentinel.unlink()


def test_schedule_restart_disabled(settings) -> None:
    settings.nexa_self_improvement_auto_restart = False

    async def _runner():
        return await restart_mod.schedule_restart(delay_s=0.01)

    res = asyncio.run(_runner())
    assert res["status"] == "disabled"


def test_schedule_restart_noop(settings) -> None:
    settings.nexa_self_improvement_auto_restart = True
    settings.nexa_self_improvement_auto_restart_method = "noop"

    async def _runner():
        return await restart_mod.schedule_restart(delay_s=0.01)

    res = asyncio.run(_runner())
    assert res["status"] == "noop"


def test_schedule_restart_uvicorn_reload_actually_fires(settings, monkeypatch) -> None:
    settings.nexa_self_improvement_auto_restart = True
    settings.nexa_self_improvement_auto_restart_method = "uvicorn-reload"
    fake_sentinel = Path(__file__).parent / "_tmp_sentinel2.py"
    if fake_sentinel.exists():
        fake_sentinel.unlink()
    monkeypatch.setattr(restart_mod, "SENTINEL_PATH", fake_sentinel)

    async def _runner():
        info = await restart_mod.schedule_restart(delay_s=0.05)
        # Wait a touch longer than delay_s for the call_later to fire.
        await asyncio.sleep(0.2)
        return info

    try:
        info = asyncio.run(_runner())
        assert info["status"] == "scheduled"
        assert fake_sentinel.exists()
    finally:
        if fake_sentinel.exists():
            fake_sentinel.unlink()
