# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace project registration — web channel users must not get false 403 (Phase 42)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, get_settings
from app.core.security import get_valid_web_user_id
from app.main import app


def test_web_channel_user_can_post_nexa_workspace_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    uid = "web_wp_gate_test"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    get_settings.cache_clear()
    subdir = Path(REPO_ROOT).resolve() / f"_pytest_wp_{uuid.uuid4().hex[:10]}"
    subdir.mkdir(parents=True, exist_ok=True)
    c = TestClient(app)
    try:
        r = c.post(
            f"{get_settings().api_v1_prefix}/web/workspace/nexa-projects",
            headers={"X-User-Id": uid},
            json={
                "path": str(subdir),
                "name": f"test_proj_{uuid.uuid4().hex[:8]}",
                "description": None,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("name")
        assert body.get("path_normalized")
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        try:
            subdir.rmdir()
        except OSError:
            pass


def test_telegram_guest_blocked_from_workspace_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """tg_* without owner/trusted role cannot register paths."""
    from unittest.mock import patch

    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    uid = "tg_999001999002999003"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    get_settings.cache_clear()
    subdir = Path(REPO_ROOT).resolve() / f"_pytest_wp_guest_{uuid.uuid4().hex[:8]}"
    subdir.mkdir(parents=True, exist_ok=True)
    c = TestClient(app)
    try:
        with patch(
            "app.services.user_capabilities.get_telegram_role_for_app_user",
            return_value="guest",
        ):
            r = c.post(
                f"{get_settings().api_v1_prefix}/web/workspace/nexa-projects",
                headers={"X-User-Id": uid},
                json={
                    "path": str(subdir),
                    "name": "guest_blocked",
                    "description": None,
                },
            )
            assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        try:
            subdir.rmdir()
        except OSError:
            pass
