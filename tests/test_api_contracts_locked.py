# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 15 — frozen Mission Control HTTP/WebSocket contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

PREFIX = "/api/v1/mission-control"


def test_locked_get_endpoints_exist() -> None:
    c = TestClient(app)
    for path, params in (
        (f"{PREFIX}/state", None),
        (f"{PREFIX}/graph", None),
        (f"{PREFIX}/events/timeline", None),
    ):
        r = c.get(path, params=params)
        assert r.status_code != 404, path


def test_locked_gateway_run_accepts_post() -> None:
    c = TestClient(app)
    r = c.post(f"{PREFIX}/gateway/run", json={"text": "", "user_id": "contract_test_user"})
    assert r.status_code != 404


def test_locked_gateway_run_accepts_raw_only_body() -> None:
    """Clients that only send ``raw`` must not hit *Input should be a valid dictionary*."""
    c = TestClient(app)
    r = c.post(
        f"{PREFIX}/gateway/run",
        json={"raw": "ping", "user_id": "contract_test_user"},
    )
    assert r.status_code != 404
    assert r.status_code != 422, r.text


def test_locked_websocket_connects() -> None:
    c = TestClient(app)
    with c.websocket_connect(f"{PREFIX}/events/ws") as ws:
        ws.send_text("ping")


def test_openapi_lists_locked_paths() -> None:
    c = TestClient(app)
    r = c.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths") or {}
    for p in (
        f"{PREFIX}/state",
        f"{PREFIX}/graph",
        f"{PREFIX}/gateway/run",
        f"{PREFIX}/events/timeline",
    ):
        assert p in paths, p
