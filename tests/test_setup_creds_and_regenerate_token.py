# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.setup_creds_file import write_setup_creds
from app.main import app


def test_get_setup_creds_empty_without_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AETHOS_SETUP_CREDS_FILE", str(tmp_path / "missing.json"))
    c = TestClient(app)
    r = c.get("/api/setup-creds")
    assert r.status_code == 200
    assert r.json() == {}


def test_get_setup_creds_reads_file(monkeypatch, tmp_path) -> None:
    p = tmp_path / "creds.json"
    monkeypatch.setenv("AETHOS_SETUP_CREDS_FILE", str(p))
    write_setup_creds(api_base="http://127.0.0.1:8010", user_id="web_setup_test", bearer_token="tok123")
    c = TestClient(app)
    r = c.get("/api/setup-creds")
    assert r.status_code == 200
    body = r.json()
    assert body.get("user_id") == "web_setup_test"
    assert body.get("bearer_token") == "tok123"
    assert body.get("api_base") == "http://127.0.0.1:8010"


def test_regenerate_token_ok_for_test_x_user(monkeypatch, db_session) -> None:
    monkeypatch.setenv("TEST_X_USER_ID", "web_setup_rot1")
    monkeypatch.setenv("NEXA_WEB_API_TOKEN", "secret_rotate_me")
    get_settings.cache_clear()

    recorded: list[tuple[str, str]] = []

    def capture(key: str, value: str, *, env_path=None) -> None:
        recorded.append((key, value))

    monkeypatch.setattr("app.api.routes.user_settings.update_repo_env_key", capture)

    c = TestClient(app)
    try:
        r = c.post(
            "/api/v1/user/regenerate-token",
            headers={"X-User-Id": "web_setup_rot1", "Authorization": "Bearer secret_rotate_me"},
        )
        assert r.status_code == 200
        new_tok = r.json().get("token")
        assert isinstance(new_tok, str) and len(new_tok) == 32
        assert new_tok != "secret_rotate_me"
        assert all(c.isascii() and (c.isalnum() or c in "-_") for c in new_tok)
        assert recorded == [("NEXA_WEB_API_TOKEN", new_tok)]
        assert (get_settings().nexa_web_api_token or "") == new_tok
    finally:
        monkeypatch.delenv("TEST_X_USER_ID", raising=False)
        monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
        get_settings.cache_clear()


def test_regenerate_token_forbidden_other_user(monkeypatch, db_session) -> None:
    monkeypatch.setenv("TEST_X_USER_ID", "web_setup_rot1")
    monkeypatch.setenv("NEXA_WEB_API_TOKEN", "secret_rotate_me")
    get_settings.cache_clear()

    def _fail_write(*_a, **_k) -> None:
        raise AssertionError("should not write")

    monkeypatch.setattr("app.api.routes.user_settings.update_repo_env_key", _fail_write)

    c = TestClient(app)
    try:
        r = c.post(
            "/api/v1/user/regenerate-token",
            headers={"X-User-Id": "web_other_user", "Authorization": "Bearer secret_rotate_me"},
        )
        assert r.status_code == 403
    finally:
        monkeypatch.delenv("TEST_X_USER_ID", raising=False)
        monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
        get_settings.cache_clear()
