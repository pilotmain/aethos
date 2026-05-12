# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73b — Self-Improvement (Genesis Loop) tests.

Covers:

* :mod:`app.services.self_improvement.context` — allowlist + denylist gates.
* :mod:`app.services.self_improvement.proposal` — diff validator (empty,
  no-headers, too-many-files, secret-scan, no-op, scorched-earth, allowlist),
  ``ProposalStore`` CRUD + status transitions + sandbox-result persistence,
  ``generate_proposal_diff`` LLM-call wiring.
* :mod:`app.services.self_improvement.sandbox` — harness paths exercised with
  a fake :func:`subprocess.run` so we don't actually create a worktree or run
  pytest inside CI.
* :mod:`app.api.routes.self_improvement` — disabled-flag returns 404,
  non-owner returns 403, propose / approve / reject / sandbox / apply
  happy-paths with the heavy services patched.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.routes.self_improvement as si_router
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.self_improvement import context as si_context
from app.services.self_improvement import proposal as si_proposal
from app.services.self_improvement import sandbox as si_sandbox


# --- Settings shim ---------------------------------------------------------


class _Settings:
    nexa_self_improvement_enabled = True
    nexa_self_improvement_max_files_per_proposal = 5
    nexa_self_improvement_max_diff_lines = 400
    nexa_self_improvement_sandbox_timeout_s = 30
    nexa_self_improvement_allowed_paths = "app/services/,app/api/routes/,docs/"
    nexa_data_dir = ""


@pytest.fixture
def settings_enabled(monkeypatch) -> _Settings:
    s = _Settings()
    monkeypatch.setattr(si_context, "get_settings", lambda: s)
    monkeypatch.setattr(si_proposal, "get_settings", lambda: s)
    monkeypatch.setattr(si_sandbox, "get_settings", lambda: s)
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    return s


@pytest.fixture
def fresh_store(tmp_path, monkeypatch) -> si_proposal.ProposalStore:
    """Force the singleton store to use a tmp path so tests don't touch the real db."""
    db = tmp_path / "audit_test.db"
    store = si_proposal.ProposalStore(db_path=db)
    monkeypatch.setattr(si_proposal, "_proposal_store", store, raising=False)
    return store


# --- context ---------------------------------------------------------------


def test_context_allowlist_accepts_app_services(settings_enabled) -> None:
    assert si_context.is_path_allowed("app/services/foo.py") is True
    assert si_context.is_path_allowed("app/services/sub/bar.py") is True
    assert si_context.is_path_allowed("docs/PHASE73B_SELF_IMPROVEMENT.md") is True


def test_context_denies_secrets_and_outside_allowlist(settings_enabled) -> None:
    assert si_context.is_path_allowed(".env") is False
    assert si_context.is_path_allowed(".env.example") is False
    assert si_context.is_path_allowed("app/core/secrets.py") is False
    assert si_context.is_path_allowed("app/core/config.py") is False  # outside allowlist
    assert si_context.is_path_allowed("data/some_credentials.json") is False
    assert si_context.is_path_allowed("path/to/private_key.pem") is False
    assert si_context.is_path_allowed("data/agent_audit.db") is False


def test_context_rejects_traversal_and_absolute(settings_enabled) -> None:
    with pytest.raises(si_context.ContextNotAllowedError):
        si_context.normalize_relpath("../etc/passwd")
    with pytest.raises(si_context.ContextNotAllowedError):
        si_context.normalize_relpath("/etc/passwd")
    assert si_context.is_path_allowed("../etc/passwd") is False


def test_context_fetch_reads_real_file(settings_enabled) -> None:
    """Sanity: fetching one of our own service modules works end-to-end."""
    ctx = si_context.fetch_context("app/services/self_improvement/proposal.py")
    assert ctx.path == "app/services/self_improvement/proposal.py"
    assert "ProposalStore" in ctx.content
    assert ctx.size_bytes > 0


def test_context_fetch_rejects_disallowed(settings_enabled) -> None:
    with pytest.raises(si_context.ContextNotAllowedError):
        si_context.fetch_context(".env")


# --- diff validator --------------------------------------------------------


_VALID_DIFF = """diff --git a/app/services/foo.py b/app/services/foo.py
--- a/app/services/foo.py
+++ b/app/services/foo.py
@@ -1,3 +1,4 @@
 def foo():
     pass
+# improved
+
"""


def test_validate_empty_diff(settings_enabled) -> None:
    r = si_proposal.validate_proposal_diff("")
    assert r.ok is False
    assert "empty_diff" in r.errors


def test_validate_no_headers(settings_enabled) -> None:
    r = si_proposal.validate_proposal_diff("not a diff at all\n")
    assert r.ok is False
    assert "no_diff_headers_found" in r.errors


def test_validate_happy_path(settings_enabled) -> None:
    r = si_proposal.validate_proposal_diff(_VALID_DIFF)
    assert r.ok, r.errors
    assert len(r.files) == 1
    assert r.files[0].path == "app/services/foo.py"
    assert r.total_added == 2
    assert r.total_removed == 0


def test_validate_rejects_path_outside_allowlist(settings_enabled) -> None:
    bad = _VALID_DIFF.replace("app/services/foo.py", "app/core/config.py")
    r = si_proposal.validate_proposal_diff(bad)
    assert r.ok is False
    assert any("path_not_allowed" in e for e in r.errors)


def test_validate_rejects_secret_in_added_line(settings_enabled) -> None:
    bad = _VALID_DIFF.replace("# improved", "API_KEY = 'sk-thisIsAFakeButLongEnoughKey1234567890'")
    r = si_proposal.validate_proposal_diff(bad)
    assert r.ok is False
    assert any("secret_pattern" in e for e in r.errors)


def test_validate_rejects_too_many_files(settings_enabled) -> None:
    parts: list[str] = []
    for i in range(7):
        parts.append(
            f"diff --git a/app/services/f{i}.py b/app/services/f{i}.py\n"
            f"--- a/app/services/f{i}.py\n"
            f"+++ b/app/services/f{i}.py\n"
            f"@@ -1 +1,2 @@\n"
            f" pass\n"
            f"+# add{i}\n"
        )
    big = "".join(parts)
    r = si_proposal.validate_proposal_diff(big)
    assert r.ok is False
    assert any(e.startswith("too_many_files") for e in r.errors)


def test_validate_rejects_pure_deletion_without_replacement(settings_enabled) -> None:
    pure_del = (
        "diff --git a/app/services/foo.py b/app/services/foo.py\n"
        "--- a/app/services/foo.py\n"
        "+++ b/app/services/foo.py\n"
        "@@ -1,2 +1 @@\n"
        " keep\n"
        "-drop\n"
    )
    r = si_proposal.validate_proposal_diff(pure_del)
    assert r.ok is False
    assert "pure_deletion_without_replacement" in r.errors


# --- ProposalStore ---------------------------------------------------------


def test_store_create_get_list_status_transitions(fresh_store, settings_enabled) -> None:
    p = fresh_store.create(
        title="t1",
        problem_statement="boom",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
        rationale="why",
        created_by="tg_owner",
    )
    assert p.status == si_proposal.STATUS_PENDING
    got = fresh_store.get(p.id)
    assert got is not None and got.title == "t1"

    rows = fresh_store.list_proposals()
    assert len(rows) == 1 and rows[0].id == p.id

    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    assert fresh_store.get(p.id).status == si_proposal.STATUS_APPROVED

    fresh_store.set_status(
        p.id,
        si_proposal.STATUS_APPLIED,
        applied_commit_sha="deadbeef" * 5,
    )
    refreshed = fresh_store.get(p.id)
    assert refreshed.status == si_proposal.STATUS_APPLIED
    assert refreshed.applied_commit_sha == "deadbeef" * 5


def test_store_record_sandbox_result_and_freshness(fresh_store, settings_enabled) -> None:
    p = fresh_store.create(
        title="t2",
        problem_statement="x",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
    )
    fresh_store.record_sandbox_result(p.id, {"success": True, "duration_s": 1.2})
    age = fresh_store.get_sandbox_run_age_seconds(p.id)
    assert age is not None and age >= 0.0
    refreshed = fresh_store.get(p.id)
    assert refreshed.sandbox_result == {"success": True, "duration_s": 1.2}


# --- generate_proposal_diff (LLM wiring) ----------------------------------


def test_generate_diff_invokes_llm_with_task_type(settings_enabled, monkeypatch) -> None:
    captured = {}

    def fake_complete(messages, **kwargs):
        captured["task_type"] = kwargs.get("task_type")
        captured["messages_len"] = len(messages)
        return _VALID_DIFF

    monkeypatch.setattr(si_proposal, "primary_complete_messages", fake_complete)
    diff, ctxs = si_proposal.generate_proposal_diff(
        problem_statement="please fix",
        target_paths=["app/services/self_improvement/proposal.py"],
        extra_context_paths=["docs/PHASE73B_SELF_IMPROVEMENT.md"],  # may not exist
    )
    assert diff.startswith("diff --git")
    assert captured["task_type"] == "self_improvement_diff"
    assert captured["messages_len"] == 2
    assert any(c.path == "app/services/self_improvement/proposal.py" for c in ctxs)


def test_generate_diff_rejects_disallowed_target(settings_enabled, monkeypatch) -> None:
    monkeypatch.setattr(si_proposal, "primary_complete_messages", lambda *_a, **_k: _VALID_DIFF)
    with pytest.raises(ValueError):
        si_proposal.generate_proposal_diff(
            problem_statement="x",
            target_paths=["app/core/config.py"],  # outside allowlist
        )


def test_generate_diff_strips_markdown_fence(settings_enabled, monkeypatch) -> None:
    fenced = f"```diff\n{_VALID_DIFF}```"
    monkeypatch.setattr(si_proposal, "primary_complete_messages", lambda *_a, **_k: fenced)
    diff, _ = si_proposal.generate_proposal_diff(
        problem_statement="x",
        target_paths=["app/services/self_improvement/proposal.py"],
    )
    assert diff.startswith("diff --git")


# --- sandbox harness (mocked subprocess) ----------------------------------


class _FakeRun:
    """Stub for ``subprocess.run`` that returns a configurable script of results."""

    def __init__(self, script: list[dict]) -> None:
        self.script = list(script)
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if not self.script:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        spec = self.script.pop(0)
        if spec.get("raise"):
            raise spec["raise"]
        return SimpleNamespace(
            returncode=spec.get("rc", 0),
            stdout=spec.get("stdout", b"ok"),
            stderr=spec.get("stderr", b""),
        )


def test_sandbox_happy_path(settings_enabled, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(si_sandbox, "_sandbox_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(si_sandbox, "repo_root", lambda: tmp_path / "repo")
    (tmp_path / "repo").mkdir()
    fake = _FakeRun(
        [
            {"rc": 0},  # git worktree add
            {"rc": 0},  # git apply --check
            {"rc": 0},  # git apply
            {"rc": 0},  # compileall
            {"rc": 0},  # pytest
            {"rc": 0},  # worktree remove cleanup
            {"rc": 0},  # worktree prune cleanup
        ]
    )

    def fake_run(cmd, **kwargs):
        spec_proc = fake(cmd, **kwargs)
        return spec_proc

    monkeypatch.setattr(si_sandbox.subprocess, "run", fake_run)
    monkeypatch.setattr(
        si_sandbox.Path,
        "write_text",
        lambda self, *_a, **_k: None,
    )
    result = si_sandbox.run_sandbox(proposal_id="prop-x", diff_text=_VALID_DIFF)
    assert result.success is True, result.error
    assert any(s.name == "compileall_app" for s in result.steps)
    assert any(s.name == "pytest" for s in result.steps)
    assert result.error is None


def test_sandbox_apply_check_failure_returns_clean_error(
    settings_enabled, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(si_sandbox, "_sandbox_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(si_sandbox, "repo_root", lambda: tmp_path / "repo")
    (tmp_path / "repo").mkdir()
    monkeypatch.setattr(si_sandbox.Path, "write_text", lambda self, *_a, **_k: None)
    fake = _FakeRun(
        [
            {"rc": 0},  # worktree add
            {"rc": 1, "stderr": b"patch does not apply"},  # apply --check FAILS
            {"rc": 0},  # cleanup remove
            {"rc": 0},  # cleanup prune
        ]
    )
    monkeypatch.setattr(si_sandbox.subprocess, "run", fake)
    result = si_sandbox.run_sandbox(proposal_id="prop-y", diff_text=_VALID_DIFF)
    assert result.success is False
    assert result.error == "diff_does_not_apply_cleanly"


def test_sandbox_worktree_create_failure(settings_enabled, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(si_sandbox, "_sandbox_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(si_sandbox, "repo_root", lambda: tmp_path / "repo")
    (tmp_path / "repo").mkdir()
    fake = _FakeRun(
        [
            {"rc": 1, "stderr": b"already exists"},  # worktree add fails
            {"rc": 0},  # cleanup
            {"rc": 0},  # prune
        ]
    )
    monkeypatch.setattr(si_sandbox.subprocess, "run", fake)
    result = si_sandbox.run_sandbox(proposal_id="prop-z", diff_text=_VALID_DIFF)
    assert result.success is False
    assert result.error == "worktree_create_failed"


# --- API routes ------------------------------------------------------------


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


def test_routes_404_when_disabled(monkeypatch) -> None:
    s = _Settings()
    s.nexa_self_improvement_enabled = False
    monkeypatch.setattr(si_router, "get_settings", lambda: s)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/")
        assert r.status_code == 404
        assert "disabled" in r.json().get("detail", "").lower()
    finally:
        app.dependency_overrides.clear()


def test_routes_propose_requires_owner(settings_enabled, monkeypatch) -> None:
    monkeypatch.setattr(
        si_router,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "guest",
    )
    _override_user("tg_other")
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/self_improvement/propose",
            json={
                "title": "t",
                "problem_statement": "boom",
                "target_paths": ["app/services/foo.py"],
            },
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_routes_propose_persists_when_owner(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "owner",
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    monkeypatch.setattr(
        si_router,
        "generate_proposal_diff",
        lambda **kw: (_VALID_DIFF, []),
    )
    monkeypatch.setattr(si_router, "validate_proposal_diff", si_proposal.validate_proposal_diff)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(
            "/api/v1/self_improvement/propose",
            json={
                "title": "fix the foo",
                "problem_statement": "foo flakes under load",
                "target_paths": ["app/services/foo.py"],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["proposal"]["status"] == "pending"
        assert body["proposal"]["title"] == "fix the foo"
        assert body["validation"]["total_added"] == 2
    finally:
        app.dependency_overrides.clear()


def test_routes_apply_requires_fresh_passing_sandbox(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "owner",
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = fresh_store.create(
        title="t",
        problem_statement="x",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
    )
    fresh_store.set_status(p.id, si_proposal.STATUS_APPROVED)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        # No sandbox run yet -> 412.
        r = client.post(f"/api/v1/self_improvement/{p.id}/apply")
        assert r.status_code == 412
        assert "sandbox" in r.json().get("detail", "")
    finally:
        app.dependency_overrides.clear()


def test_routes_revert_409_when_not_applied(
    settings_enabled, fresh_store, monkeypatch
) -> None:
    monkeypatch.setattr(
        si_router,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "owner",
    )
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    p = fresh_store.create(
        title="t",
        problem_statement="x",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.post(f"/api/v1/self_improvement/{p.id}/revert")
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_routes_get_404_for_unknown_proposal(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/no-such-id")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_routes_list_returns_recently_created(settings_enabled, fresh_store, monkeypatch) -> None:
    monkeypatch.setattr(si_router, "get_proposal_store", lambda: fresh_store)
    fresh_store.create(
        title="A",
        problem_statement="x",
        target_paths=["app/services/foo.py"],
        diff=_VALID_DIFF,
    )
    fresh_store.create(
        title="B",
        problem_statement="y",
        target_paths=["app/services/bar.py"],
        diff=_VALID_DIFF,
    )
    _override_user("tg_owner")
    try:
        client = TestClient(app)
        r = client.get("/api/v1/self_improvement/")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        titles = {p["title"] for p in body["proposals"]}
        assert {"A", "B"} <= titles
    finally:
        app.dependency_overrides.clear()


# Silence unused-import warning if a future refactor removes them.
_ = (json, time, Path, MagicMock)
