# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 20 — persisted user settings API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import config as cfg
from app.main import app
from app.models.user_settings import NexaUserSettings
from app.services.user_settings.service import effective_privacy_mode


def test_get_post_user_settings_roundtrip(db_session, monkeypatch) -> None:
    from app.core.security import get_valid_web_user_id

    uid = "mc_user_settings_test_01"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    cfg.get_settings.cache_clear()
    try:
        c = TestClient(app)
        r0 = c.get("/api/v1/user/settings", headers={"X-User-Id": uid})
        assert r0.status_code == 200
        j0 = r0.json()
        assert j0["privacy_mode"] in ("standard", "strict", "paranoid")

        r1 = c.post(
            "/api/v1/user/settings",
            headers={"X-User-Id": uid},
            json={"privacy_mode": "strict", "ui_preferences": {"theme": "light", "auto_refresh": False}},
        )
        assert r1.status_code == 200
        j1 = r1.json()
        assert j1["privacy_mode"] == "strict"
        assert j1["ui_preferences"]["theme"] == "light"

        row = db_session.get(NexaUserSettings, uid)
        assert row is not None
        assert effective_privacy_mode(db_session, uid) == "strict"
    finally:
        app.dependency_overrides.clear()
        cfg.get_settings.cache_clear()
