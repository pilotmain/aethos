# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 20 — authenticated routes reject missing identity headers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_user_settings_requires_auth() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/user/settings")
    assert r.status_code == 401


def test_mission_export_requires_auth() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/export/not-a-real-id")
    assert r.status_code == 401
