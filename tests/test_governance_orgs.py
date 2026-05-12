# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance organizations API — orgs, memberships, roles, overview, org-scoped audit export."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, ensure_schema
from app.core.security import get_valid_web_user_id
from app.main import app
from app.models.audit_log import AuditLog


def _patch_gov(monkeypatch: pytest.MonkeyPatch, **kwargs) -> None:
    ns = SimpleNamespace(
        nexa_governance_enabled=kwargs.get("nexa_governance_enabled", True),
        nexa_default_organization_id=kwargs.get("nexa_default_organization_id"),
        nexa_auto_create_default_org=kwargs.get("nexa_auto_create_default_org", False),
    )

    def _gs():
        return ns

    monkeypatch.setattr("app.api.routes.governance_api.get_settings", _gs)
    monkeypatch.setattr("app.services.governance.service.get_settings", _gs)


@pytest.fixture
def owner_client(monkeypatch: pytest.MonkeyPatch):
    ensure_schema()
    uid = f"gov_owner_{uuid.uuid4().hex[:10]}"
    _patch_gov(monkeypatch)
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def test_create_org_creates_owner_membership(owner_client: tuple[TestClient, str]) -> None:
    client, uid = owner_client
    oid = f"org_t_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/governance/organizations", json={"id": oid, "name": "Test Org"})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == oid
    r2 = client.get(f"/api/v1/governance/organizations/{oid}/members")
    assert r2.status_code == 200
    members = r2.json()["members"]
    assert any(m["user_id"] == uid and m["role"] == "owner" for m in members)


def test_list_orgs_returns_membership(owner_client: tuple[TestClient, str]) -> None:
    client, _uid = owner_client
    oid = f"org_t_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/governance/organizations", json={"id": oid, "name": "L"})
    r = client.get("/api/v1/governance/organizations")
    assert r.status_code == 200
    ids = {o["id"] for o in r.json()["organizations"]}
    assert oid in ids


def test_owner_adds_member(owner_client: tuple[TestClient, str]) -> None:
    client, _uid = owner_client
    oid = f"org_t_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/governance/organizations", json={"id": oid, "name": "M"})
    r = client.post(
        f"/api/v1/governance/organizations/{oid}/members",
        json={"user_id": "member_x_1", "role": "member"},
    )
    assert r.status_code == 200, r.text
    m = client.get(f"/api/v1/governance/organizations/{oid}/members").json()["members"]
    assert any(x["user_id"] == "member_x_1" for x in m)


def test_member_cannot_add_member(owner_client: tuple[TestClient, str]) -> None:
    client, owner_uid = owner_client
    oid = f"org_t_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/governance/organizations", json={"id": oid, "name": "R"})
    client.post(
        f"/api/v1/governance/organizations/{oid}/members",
        json={"user_id": "lowly_member", "role": "member"},
    )
    app.dependency_overrides[get_valid_web_user_id] = lambda: "lowly_member"
    try:
        r = client.post(
            f"/api/v1/governance/organizations/{oid}/members",
            json={"user_id": "other", "role": "member"},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides[get_valid_web_user_id] = lambda: owner_uid


def test_governance_feature_disabled_returns_403(monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_schema()
    uid = f"gov_x_{uuid.uuid4().hex[:8]}"
    _patch_gov(monkeypatch, nexa_governance_enabled=False)
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    try:
        c = TestClient(app)
        r = c.get("/api/v1/governance/organizations")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_overview_and_audit_export_scoped(owner_client: tuple[TestClient, str]) -> None:
    client, uid = owner_client
    oid = f"org_t_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/governance/organizations", json={"id": oid, "name": "O"})
    r = client.get(f"/api/v1/governance/organizations/{oid}/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["organization"]["id"] == oid
    assert o["current_user_role"] == "owner"

    other = f"org_other_{uuid.uuid4().hex[:6]}"
    client.post("/api/v1/governance/organizations", json={"id": other, "name": "Other"})

    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                user_id=uid,
                event_type="test.org_a",
                actor="test",
                message="a",
                metadata_json={"organization_id": oid},
            )
        )
        db.add(
            AuditLog(
                user_id=uid,
                event_type="test.org_b",
                actor="test",
                message="b",
                metadata_json={"organization_id": other},
            )
        )
        db.commit()
    finally:
        db.close()

    ex = client.get(f"/api/v1/governance/organizations/{oid}/audit/export.json")
    assert ex.status_code == 200
    data = json.loads(ex.text)
    types = {e.get("event_type") for e in data.get("events", [])}
    assert "test.org_a" in types
    assert "test.org_b" not in types


def test_me_auto_creates_default_org(owner_client: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _uid = owner_client
    oid = f"org_auto_{uuid.uuid4().hex[:6]}"
    _patch_gov(
        monkeypatch,
        nexa_auto_create_default_org=True,
        nexa_default_organization_id=oid,
    )
    r = client.get("/api/v1/governance/me")
    assert r.status_code == 200
    body = r.json()
    assert body["governance_enabled"] is True
    ids = {o["id"] for o in body["organizations"]}
    assert oid in ids
