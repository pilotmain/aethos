# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 28 — OpenAPI includes core paths aligned with docs/API_CONTRACT.md."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_api_contract_file_exists() -> None:
    assert (ROOT / "docs" / "API_CONTRACT.md").is_file()


def test_openapi_has_core_contract_paths() -> None:
    c = TestClient(app)
    r = c.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths") or {}
    for rel in (
        "/api/v1/mission-control/state",
        "/api/v1/mission-control/graph",
        "/api/v1/custom-agents",
        "/api/v1/system/health",
        "/api/v1/nexa-memory",
        "/api/v1/web/memory",
        "/api/v1/web/memory/state",
        "/api/v1/dev/runs",
        "/api/v1/dev/workspaces",
    ):
        assert rel in paths, f"missing {rel}"
