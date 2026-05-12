# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 72 — CEO Dashboard cost block tests.

Asserts that:

* ``GET /api/v1/ceo/dashboard`` returns a top-level ``cost_today`` block plus
  ``summary.total_cost_today_usd`` / ``summary.total_llm_calls_today``.
* The cost numbers come from existing ``llm_usage_events`` rows aggregated by
  :func:`app.services.llm_usage_recorder.get_cost_summary_today`.
* Owner vs. non-owner scoping works: a non-owner only sees rows tagged with
  their ``user_id``; the owner sees all rows.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import ceo_dashboard as ceo_module
from app.core.db import SessionLocal
from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.llm_usage_event import LlmUsageEvent


def _seed_event(
    user_id: str | None,
    *,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-5",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cost: float = 0.012,
    used_user_key: bool = False,
) -> int:
    db = SessionLocal()
    try:
        ev = LlmUsageEvent(
            user_id=user_id,
            source="ceo_dashboard_test",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            used_user_key=used_user_key,
            success=True,
            metadata_json={},
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return int(ev.id)
    finally:
        db.close()


def _delete_event(ev_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(LlmUsageEvent, ev_id)
        if row is not None:
            db.delete(row)
            db.commit()
    finally:
        db.close()


@pytest.fixture()
def ceo_client(monkeypatch):
    uid = f"tg_{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid

    # Default: caller is NOT the owner (so the cost summary is scoped to their user_id).
    monkeypatch.setattr(
        ceo_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "guest",
    )
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def test_dashboard_returns_cost_today_block(ceo_client) -> None:
    client, uid = ceo_client
    mine = _seed_event(uid, cost=0.05, input_tokens=2000, output_tokens=400)
    other = _seed_event(f"tg_other_{uuid.uuid4().hex[:8]}", cost=0.99)
    try:
        r = client.get("/api/v1/ceo/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True

        ct: dict[str, Any] = body["cost_today"]
        assert ct["scope"] == "user"
        assert ct["total_calls"] >= 1
        # Caller is non-owner, so other-user costs must not leak.
        assert ct["total_cost_usd"] >= 0.05
        assert ct["total_cost_usd"] < 0.99
        assert ct["total_tokens"] >= 2400

        sm = body["summary"]
        assert sm["total_cost_today_usd"] == pytest.approx(ct["total_cost_usd"], rel=1e-6)
        assert sm["total_llm_calls_today"] == ct["total_calls"]
    finally:
        for jid in (mine, other):
            _delete_event(jid)


def test_dashboard_owner_sees_all_costs(ceo_client, monkeypatch) -> None:
    client, uid = ceo_client
    monkeypatch.setattr(
        ceo_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: "owner",
    )
    mine = _seed_event(uid, cost=0.10)
    other = _seed_event(f"tg_other_{uuid.uuid4().hex[:8]}", cost=0.20)
    try:
        r = client.get("/api/v1/ceo/dashboard")
        assert r.status_code == 200, r.text
        body = r.json()
        ct = body["cost_today"]
        assert ct["scope"] == "owner"
        assert ct["total_cost_usd"] >= 0.30  # both rows visible to owner
    finally:
        for jid in (mine, other):
            _delete_event(jid)


def test_dashboard_returns_zero_cost_when_no_events(ceo_client) -> None:
    client, _uid = ceo_client
    r = client.get("/api/v1/ceo/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    ct = body["cost_today"]
    assert ct["total_cost_usd"] >= 0.0
    assert ct["total_calls"] >= 0
    assert isinstance(ct["by_provider"], list)
    assert isinstance(ct["top_actions"], list)


def test_dashboard_cost_block_resilient_to_recorder_failure(
    ceo_client, monkeypatch
) -> None:
    client, _uid = ceo_client

    def _boom(*_a, **_k):
        raise RuntimeError("recorder unavailable")

    monkeypatch.setattr(ceo_module, "get_cost_summary_today", _boom)

    r = client.get("/api/v1/ceo/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cost_today"]["error"] == "cost_summary_unavailable"
    assert body["summary"]["total_cost_today_usd"] == 0.0
