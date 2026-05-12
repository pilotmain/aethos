# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 27 — legacy /memory returns 410; nexa-memory remains."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_legacy_api_v1_memory_is_gone() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/memory", headers={"X-User-Id": "u_mem"})
    assert r.status_code == 410


def test_nexa_memory_list_ok(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/nexa-memory")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
