# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 70 — :mod:`app.api.routes.approvals` smoke tests.

The endpoint reads the existing ``agent_jobs.awaiting_approval`` rows; approve
and deny still flow through the legacy ``/jobs/{id}/decision`` API. We assert
scoping (user_id), the settings flag gate, and that the response payload is
sanitized for the browser.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal
from app.core.security import get_current_user_id, get_valid_web_user_id
from app.main import app
from app.models.agent_job import AgentJob
from fastapi.testclient import TestClient


def _seed_pending_job(
    user_id: str,
    *,
    title: str = "Deploy to Vercel",
    payload: dict | None = None,
    risk_level: str | None = "high",
    awaiting: bool = True,
) -> int:
    payload = payload or {
        "host_action": "git_push",
        "remote": "origin",
        "ref": "main",
        "provider": "github",
        "secret_token": "shouldnt_appear_in_preview",
    }
    db = SessionLocal()
    try:
        job = AgentJob(
            user_id=user_id,
            source="web",
            kind="dev",
            worker_type="local_tool",
            title=title,
            instruction="Push current branch to origin/main and trigger redeploy.",
            command_type="host-executor",
            status="needs_approval" if awaiting else "queued",
            payload_json=payload,
            risk_level=risk_level,
            awaiting_approval=awaiting,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return int(job.id)
    finally:
        db.close()


def _delete_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(AgentJob, job_id)
        if row is not None:
            db.delete(row)
            db.commit()
    finally:
        db.close()


@pytest.fixture()
def approvals_client():
    uid = f"tg_{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    app.dependency_overrides[get_current_user_id] = lambda: uid
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def test_pending_returns_only_caller_jobs(approvals_client) -> None:
    client, uid = approvals_client
    other_uid = f"tg_other_{uuid.uuid4().hex[:8]}"
    mine = _seed_pending_job(uid, title="Mine awaiting")
    not_mine = _seed_pending_job(other_uid, title="Someone else's")
    not_awaiting = _seed_pending_job(uid, title="Mine but not awaiting", awaiting=False)
    try:
        r = client.get("/api/v1/approvals/pending")
        assert r.status_code == 200, r.text
        body = r.json()
        ids = {row["id"] for row in body["approvals"]}
        assert mine in ids
        assert not_mine not in ids
        assert not_awaiting not in ids
        assert body["count"] == len(body["approvals"])
    finally:
        for jid in (mine, not_mine, not_awaiting):
            _delete_job(jid)


def test_pending_payload_preview_strips_unknown_fields(approvals_client) -> None:
    client, uid = approvals_client
    payload = {
        "host_action": "vercel_deploy",
        "provider": "vercel",
        "service": "aethos-web",
        "secret_token": "must_not_leak",
        "raw_password": "must_not_leak",
    }
    jid = _seed_pending_job(uid, title="Deploy aethos-web", payload=payload)
    try:
        r = client.get("/api/v1/approvals/pending")
        assert r.status_code == 200, r.text
        rows = r.json()["approvals"]
        row = next((x for x in rows if x["id"] == jid), None)
        assert row is not None
        assert row["host_action"] == "vercel_deploy"
        assert row["target"] == "vercel"
        preview = row["payload_preview"]
        assert "secret_token" not in preview
        assert "raw_password" not in preview
        assert preview.get("service") == "aethos-web"
    finally:
        _delete_job(jid)


def test_pending_disabled_when_flag_off(approvals_client, monkeypatch) -> None:
    client, uid = approvals_client
    jid = _seed_pending_job(uid)
    try:
        from app.api.routes import approvals as approvals_module

        original_get_settings = approvals_module.get_settings

        class _StubSettings:
            nexa_approvals_panel_enabled = False

        monkeypatch.setattr(approvals_module, "get_settings", lambda: _StubSettings())
        try:
            r = client.get("/api/v1/approvals/pending")
            assert r.status_code == 503, r.text
            assert "disabled" in r.json()["detail"].lower()
        finally:
            monkeypatch.setattr(approvals_module, "get_settings", original_get_settings)
    finally:
        _delete_job(jid)


def test_risk_preview_uses_existing_policy(approvals_client) -> None:
    client, _uid = approvals_client
    r = client.get("/api/v1/approvals/risk-preview", params={"text": "rm -rf /"})
    assert r.status_code == 200, r.text
    assert r.json()["risk"] == "high"

    r2 = client.get("/api/v1/approvals/risk-preview", params={"text": "what is the weather"})
    assert r2.status_code == 200
    assert r2.json()["risk"] == "low"
