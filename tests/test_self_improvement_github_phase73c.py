# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73c — GitHub auto-merge flow tests.

Coverage:

* :mod:`app.services.self_improvement.github_client` — config plumbing,
  ``GitHubError`` HTTP-status mapping, redaction of the token in error
  messages, ``_safe_response_message`` extraction, and a happy-path
  ``open_pull_request`` call against a mocked ``httpx`` transport.
* :mod:`app.services.self_improvement.proposal` — new statuses, lazy
  schema migration adds the Phase 73c columns to a pre-existing 73b
  database, ``set_github_state`` updates only the supplied fields.
* :mod:`app.api.routes.self_improvement` — ``/_capabilities`` shape,
  ``/{id}/open-pr`` happy path with mocked GitHub client, gating
  (``404`` when GitHub disabled, ``403`` for non-owner, ``409`` /
  ``412`` from the state machine and freshness gate),
  ``/{id}/merge-pr`` only succeeds when mergeable + fresh sandbox,
  ``/{id}/revert-merge`` requires a recorded ``merge_commit_sha``.

We do **not** invoke any real ``git`` subprocesses or hit ``api.github.com``;
all network and process calls are stubbed at the boundary.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.routes.self_improvement as si_router
from app.core.security import get_valid_web_user_id
from app.main import app
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


# --- Settings shim ---------------------------------------------------------


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
    # Phase 73d added a CI gate to /merge-pr (default WAIT_FOR_CI=true). The
    # 73c suite predates it and tests the GitHub plumbing in isolation, so
    # disable the new gate here. The 73d suite covers the gate behaviour.
    nexa_self_improvement_wait_for_ci = False
    nexa_self_improvement_ci_poll_interval_seconds = 30
    nexa_self_improvement_ci_max_age_seconds = 21600
    nexa_self_improvement_auto_restart = False
    nexa_self_improvement_auto_restart_method = "noop"
    nexa_data_dir = ""


@pytest.fixture
def settings_enabled(monkeypatch) -> _Settings:
    s = _Settings()
    # Patch every module that resolves Settings at request time. Phase 73d
    # added `app.core.restart` which the capabilities endpoint reads via
    # restart_method() — patch it here too so 73c assertions stay stable.
    import app.core.restart as restart_mod
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    monkeypatch.setattr(si_proposal, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "get_settings", lambda: s)
    monkeypatch.setattr(restart_mod, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "_github_client", None, raising=False)
    return s


@pytest.fixture
def settings_github_off(monkeypatch) -> _Settings:
    s = _Settings()
    s.nexa_self_improvement_github_enabled = False
    s.nexa_self_improvement_github_token = ""
    import app.core.restart as restart_mod
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    monkeypatch.setattr(si_proposal, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "get_settings", lambda: s)
    monkeypatch.setattr(restart_mod, "get_settings", lambda: s)
    monkeypatch.setattr(gh_mod, "_github_client", None, raising=False)
    return s


@pytest.fixture
def fresh_store(tmp_path, monkeypatch) -> si_proposal.ProposalStore:
    db = tmp_path / "audit_test.db"
    store = si_proposal.ProposalStore(db_path=db)
    monkeypatch.setattr(si_proposal, "_proposal_store", store, raising=False)
    return store


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


# --- github_client ---------------------------------------------------------


def test_client_reads_settings(settings_enabled) -> None:
    c = gh_mod.GitHubClient()
    assert c.enabled is True
    assert c.has_token is True
    assert c.owner == "pilotmain"
    assert c.repo == "aethos"
    assert c.base_branch == "main"
    assert c.merge_method == "squash"


def test_merge_method_falls_back_for_invalid(settings_enabled) -> None:
    settings_enabled.nexa_self_improvement_github_merge_method = "weird-method"
    c = gh_mod.GitHubClient()
    assert c.merge_method == "squash"


def test_redact_token_strips_pat_from_error_messages(settings_enabled) -> None:
    text = (
        f"remote: error using token ghp_FAKE_TOKEN_FOR_TESTS_xxxxxxxxxxxxxxxxxxxx "
        f"please rotate"
    )
    redacted = gh_mod._redact_token(text, settings_enabled)
    assert "ghp_FAKE_TOKEN" not in redacted
    assert "<REDACTED-TOKEN>" in redacted


def test_safe_response_message_extracts_github_error_shape() -> None:
    r = httpx.Response(
        422,
        json={"message": "Validation Failed", "errors": [{"message": "head invalid"}]},
        request=httpx.Request("POST", "https://api.github.com/x"),
    )
    msg = gh_mod._safe_response_message(r)
    assert "Validation Failed" in msg
    assert "head invalid" in msg


def test_safe_response_message_handles_non_json() -> None:
    r = httpx.Response(
        500,
        text="<html>oops</html>",
        request=httpx.Request("POST", "https://api.github.com/x"),
    )
    msg = gh_mod._safe_response_message(r)
    assert "http 500" in msg


def test_open_pull_request_happy_path_via_mock_transport(
    settings_enabled, monkeypatch
) -> None:
    """Use httpx's MockTransport so the client never hits the real API."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        assert request.method == "POST"
        assert request.url.path == "/repos/pilotmain/aethos/pulls"
        body = json.loads(request.content.decode("utf-8"))
        assert body["head"] == "self-improvement/abc123"
        assert body["base"] == "main"
        return httpx.Response(
            201,
            json={
                "number": 42,
                "html_url": "https://github.com/pilotmain/aethos/pull/42",
                "head": {"ref": "self-improvement/abc123", "sha": "deadbeef"},
                "base": {"ref": "main"},
            },
        )

    async def _runner() -> Any:
        client = gh_mod.GitHubClient()
        client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer FAKE", "Accept": "application/vnd.github+json"},
        )
        try:
            return await client.open_pull_request(
                head_branch="self-improvement/abc123",
                title="x",
                body="y",
            )
        finally:
            await client.aclose()

    pr = asyncio.run(_runner())
    assert pr.number == 42
    assert pr.url.endswith("/pull/42")
    assert pr.head_branch == "self-improvement/abc123"


def test_open_pull_request_surfaces_github_error_codes(settings_enabled) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "Validation Failed"})

    async def _runner() -> Any:
        client = gh_mod.GitHubClient()
        client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer FAKE"},
        )
        try:
            await client.open_pull_request(head_branch="x", title="t", body="b")
        finally:
            await client.aclose()

    with pytest.raises(gh_mod.GitHubError) as exc_info:
        asyncio.run(_runner())
    assert "422" in exc_info.value.code or "open_pr_failed" in exc_info.value.code


def test_merge_pull_request_maps_409_and_405(settings_enabled) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(405, json={"message": "Pull Request is not mergeable"})

    async def _runner() -> Any:
        client = gh_mod.GitHubClient()
        client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
            base_url=gh_mod.GITHUB_API,
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer FAKE"},
        )
        try:
            await client.merge_pull_request(7)
        finally:
            await client.aclose()

    with pytest.raises(gh_mod.GitHubError) as exc_info:
        asyncio.run(_runner())
    assert exc_info.value.code == "not_mergeable"


# --- proposal.py ----------------------------------------------------------


def test_lazy_migration_adds_phase73c_columns_to_existing_73b_db(
    tmp_path,
) -> None:
    """An older 73b DB without the new columns should get them on reopen."""
    import sqlite3

    db = tmp_path / "audit_old.db"
    # Simulate an existing 73b schema (no 73c columns).
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE self_improvement_proposals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                problem_statement TEXT NOT NULL,
                target_paths TEXT NOT NULL,
                diff TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                rationale TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                sandbox_result TEXT,
                sandbox_run_at TEXT,
                applied_commit_sha TEXT,
                reverted_commit_sha TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            "INSERT INTO self_improvement_proposals (id, title, problem_statement, target_paths, diff) "
            "VALUES ('old-1', 'old', 'x', '[]', 'diff')"
        )

    # Opening the store triggers the lazy migration.
    store = si_proposal.ProposalStore(db_path=db)
    p = store.get("old-1")
    assert p is not None
    assert p.pr_number is None
    assert p.merge_commit_sha is None
    # New rows should be writable through the new field path.
    p2 = store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    out = store.set_github_state(
        p2.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=99,
        pr_url="https://example/pr/99",
        github_branch="self-improvement/abc",
    )
    assert out is not None
    assert out.status == si_proposal.STATUS_PR_OPEN
    assert out.pr_number == 99
    assert out.pr_url == "https://example/pr/99"
    assert out.github_branch == "self-improvement/abc"


def test_set_github_state_keeps_existing_when_value_is_none(fresh_store) -> None:
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    fresh_store.set_github_state(p.id, pr_number=11, pr_url="u1", github_branch="b1")
    fresh_store.set_github_state(p.id, merge_commit_sha="deadbeef")
    refreshed = fresh_store.get(p.id)
    assert refreshed.pr_number == 11
    assert refreshed.pr_url == "u1"
    assert refreshed.github_branch == "b1"
    assert refreshed.merge_commit_sha == "deadbeef"


def test_new_statuses_round_trip(fresh_store) -> None:
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    fresh_store.set_github_state(p.id, new_status=si_proposal.STATUS_PR_OPEN, pr_number=1)
    fresh_store.set_github_state(p.id, new_status=si_proposal.STATUS_MERGED, merge_commit_sha="abc")
    fresh_store.set_github_state(p.id, new_status=si_proposal.STATUS_REVERT_PR_OPEN, revert_pr_number=2)
    p2 = fresh_store.get(p.id)
    assert p2.status == si_proposal.STATUS_REVERT_PR_OPEN


# --- API: capabilities ----------------------------------------------------


def test_capabilities_endpoint_reports_github_state(settings_enabled) -> None:
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/-/capabilities")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["self_improvement"]["enabled"] is True
        assert body["github"]["enabled"] is True
        assert body["github"]["owner"] == "pilotmain"
        assert body["github"]["repo"] == "aethos"
        assert body["github"]["merge_method"] == "squash"
        # Phase 73d shape: auto_restart now reports method+valid_methods.
        assert body["auto_restart"]["enabled"] is False
        assert body["auto_restart"]["method"] == "noop"
        assert "noop" in body["auto_restart"]["valid_methods"]
    finally:
        app.dependency_overrides.clear()


def test_capabilities_when_github_off(settings_github_off) -> None:
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/-/capabilities")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["github"]["enabled"] is False
    finally:
        app.dependency_overrides.clear()


# --- API: open-pr ---------------------------------------------------------


class _FakeBranchPushResult:
    def __init__(self, branch: str, head_sha: str) -> None:
        self.branch = branch
        self.head_sha = head_sha


class _FakePullRequestInfo:
    def __init__(self, number: int, url: str, head_branch: str, base_branch: str) -> None:
        self.number = number
        self.url = url
        self.head_branch = head_branch
        self.base_branch = base_branch


class _FakeGitHubClient:
    """Stub for :class:`GitHubClient` that mimics the surface the router uses."""

    def __init__(self) -> None:
        self.enabled = True
        self.has_token = True
        self.owner = "pilotmain"
        self.repo = "aethos"
        self.base_branch = "main"
        self.branch_prefix = "self-improvement/"
        self.pr_title_prefix = "[self-improvement]"
        self.merge_method = "squash"
        self.last_push: dict[str, Any] | None = None
        self.last_pr: dict[str, Any] | None = None
        self.merge_responses: list[Any] = []
        self.status_responses: list[Any] = []

    async def push_diff_branch(
        self, *, proposal_id: str, diff_text: str, commit_message: str,
        author_name: str | None = None, author_email: str | None = None,
    ) -> _FakeBranchPushResult:
        self.last_push = {
            "proposal_id": proposal_id,
            "diff_len": len(diff_text),
            "commit_message": commit_message,
        }
        return _FakeBranchPushResult(
            branch=f"self-improvement/{proposal_id}-abc123",
            head_sha="deadbeef",
        )

    async def open_pull_request(
        self, *, head_branch: str, title: str, body: str, base_branch=None,
    ) -> _FakePullRequestInfo:
        self.last_pr = {"head_branch": head_branch, "title": title, "body": body}
        return _FakePullRequestInfo(
            number=101,
            url="https://github.com/pilotmain/aethos/pull/101",
            head_branch=head_branch,
            base_branch=base_branch or self.base_branch,
        )

    async def get_pull_request_status(self, pr_number: int):
        if self.status_responses:
            return self.status_responses.pop(0)

        class _S:
            number = pr_number
            state = "open"
            merged = False
            mergeable: bool | None = True
            mergeable_state: str | None = "clean"
            head_sha: str | None = "deadbeef"
            head_branch: str = "self-improvement/abc"
            base_branch: str = "main"
        return _S()

    async def merge_pull_request(
        self, pr_number: int, *, commit_title=None, commit_message=None,
    ):
        if self.merge_responses:
            r = self.merge_responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        class _M:
            merge_commit_sha = "merged123"
            merged = True
        return _M()

    async def open_revert_pr(self, *, merge_commit_sha: str, title: str, body: str):
        return _FakePullRequestInfo(
            number=202,
            url=f"https://github.com/pilotmain/aethos/pull/202",
            head_branch=f"self-improvement/revert-{merge_commit_sha[:8]}",
            base_branch="main",
        )


def _make_approved_with_fresh_sandbox(
    fresh_store: si_proposal.ProposalStore,
) -> si_proposal.Proposal:
    p = fresh_store.create(
        title="reduce dispatch dupes",
        problem_statement="dispatch path is racy",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
    )
    fresh_store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.2})
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    return p


def test_open_pr_happy_path(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeGitHubClient()
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)

    p = _make_approved_with_fresh_sandbox(fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/open-pr")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["proposal"]["status"] == "pr_open"
        assert body["pr"]["number"] == 101
        assert body["pr"]["head_branch"].startswith("self-improvement/")
        assert fake.last_push and fake.last_push["proposal_id"] == p.id
    finally:
        app.dependency_overrides.clear()


def test_open_pr_404_when_github_disabled(
    settings_github_off, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = _make_approved_with_fresh_sandbox(fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/open-pr")
        assert r.status_code == 404
        assert "github_self_improvement" in r.json().get("detail", "").lower() or "github" in r.json().get("detail", "").lower()
    finally:
        app.dependency_overrides.clear()


def test_open_pr_403_for_non_owner(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "guest"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = _make_approved_with_fresh_sandbox(fresh_store)
    _override_user("tg_other")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/open-pr")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_open_pr_409_when_not_approved(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/open-pr")
        assert r.status_code == 409
        assert "cannot_open_pr_from_status" in r.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_open_pr_412_without_passing_sandbox(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)  # no sandbox run yet
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/open-pr")
        assert r.status_code == 412
    finally:
        app.dependency_overrides.clear()


# --- API: pr-status / merge-pr / revert-merge ----------------------------


def test_pr_status_409_when_no_pr(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get(f"/api/v1/self_improvement/{p.id}/pr-status")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_happy_path(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeGitHubClient()
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)

    p = _make_approved_with_fresh_sandbox(fresh_store)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_PR_OPEN,
        pr_number=101,
        pr_url="https://example/pr/101",
        github_branch="self-improvement/abc",
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["proposal"]["status"] == "merged"
        assert body["merge_commit_sha"] == "merged123"
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_409_when_mergeable_false(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeGitHubClient()

    class _S:
        number = 101; state = "open"; merged = False
        mergeable: bool | None = False
        mergeable_state: str | None = "dirty"
        head_sha: str | None = "x"; head_branch: str = "h"; base_branch: str = "main"
    fake.status_responses.append(_S())
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)

    p = _make_approved_with_fresh_sandbox(fresh_store)
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_PR_OPEN, pr_number=101
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 409
        assert "pr_not_mergeable" in r.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_merge_pr_409_when_mergeability_still_computing(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeGitHubClient()

    class _S:
        number = 101; state = "open"; merged = False
        mergeable: bool | None = None
        mergeable_state: str | None = "unknown"
        head_sha: str | None = "x"; head_branch: str = "h"; base_branch: str = "main"
    fake.status_responses.append(_S())
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)

    p = _make_approved_with_fresh_sandbox(fresh_store)
    fresh_store.set_github_state(
        p.id, new_status=si_proposal.STATUS_PR_OPEN, pr_number=101
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/merge-pr")
        assert r.status_code == 409
        assert "computing" in r.json().get("detail", "").lower()
    finally:
        app.dependency_overrides.clear()


def test_revert_merge_happy_path(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fake = _FakeGitHubClient()
    monkeypatch.setattr(si_router, "get_github_client", lambda: fake)

    p = _make_approved_with_fresh_sandbox(fresh_store)
    fresh_store.set_github_state(
        p.id,
        new_status=si_proposal.STATUS_MERGED,
        pr_number=101,
        merge_commit_sha="abc12345",
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/revert-merge")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["proposal"]["status"] == "revert_pr_open"
        assert body["revert_pr"]["number"] == 202
    finally:
        app.dependency_overrides.clear()


def test_revert_merge_409_when_not_merged(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router, "get_telegram_role_for_app_user", lambda _db, _uid: "owner"
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(si_router, "get_github_client", lambda: _FakeGitHubClient())
    p = fresh_store.create(
        title="t", problem_statement="x",
        target_paths=["app/services/foo.py"], diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/revert-merge")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()
