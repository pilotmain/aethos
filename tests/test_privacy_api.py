# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_privacy_status_no_auth_required() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/privacy/status")
    assert r.status_code == 200
    data = r.json()
    assert "privacy_mode" in data


def test_privacy_scan_requires_auth() -> None:
    c = TestClient(app)
    r = c.post("/api/v1/privacy/scan", json={"text": "x"})
    assert r.status_code == 401


def test_privacy_scan_and_audit(
    api_client,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    get_settings.cache_clear()
    client, _uid = api_client
    body = {"text": "reach me at a@b.co please"}
    r = client.post("/api/v1/privacy/scan", json=body)
    assert r.status_code == 200
    js = r.json()
    assert js["count"] >= 1
    assert "email" in js["categories"]

    log = tmp_path / ".aethos" / "logs" / "privacy.log"
    assert log.is_file()
    last = log.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(last)
    assert row.get("event") == "pii_detected"

    ra = client.get("/api/v1/privacy/audit?limit=5")
    assert ra.status_code == 200
    evs = ra.json()["events"]
    assert any(e.get("event") == "pii_detected" for e in evs)

    get_settings.cache_clear()
