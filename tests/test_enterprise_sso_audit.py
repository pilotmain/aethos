# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient


def test_sso_status_public(api_client):
    client: TestClient
    client, _uid = api_client
    r = client.get("/api/v1/sso/status")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "sso_enabled" in body
    assert body.get("sso_enabled") in (True, False)


def test_sso_login_disabled_returns_503(api_client):
    client, _uid = api_client
    r = client.get("/api/v1/sso/login", follow_redirects=False)
    assert r.status_code == 503


def test_enterprise_audit_recent_owner_gated(api_client, monkeypatch, tmp_path):
    client, uid = api_client
    monkeypatch.setenv("AETHOS_OWNER_IDS", uid)
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        from app.services.jsonl_audit_log import log_jsonl_audit_event

        log_jsonl_audit_event(user_id=uid, action="pytest.enterprise", outcome="ok", details={"n": 1})
        r = client.get("/api/v1/enterprise-audit/recent?days=1&limit=20", headers={"X-User-Id": uid})
        assert r.status_code == 200
        j = r.json()
        assert j.get("enabled") is True
        ev = j.get("events") or []
        assert any((e or {}).get("action") == "pytest.enterprise" for e in ev)
    finally:
        get_settings.cache_clear()


def test_enterprise_audit_forbidden_without_owner(api_client, monkeypatch, tmp_path):
    client, uid = api_client
    monkeypatch.delenv("AETHOS_OWNER_IDS", raising=False)
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/enterprise-audit/recent", headers={"X-User-Id": uid})
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()
