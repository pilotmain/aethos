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
        "/api/v1/privacy/status",
        "/api/v1/privacy/policy",
        "/api/v1/privacy/audit",
        "/api/v1/privacy/scan",
        "/api/v1/privacy/redact",
        "/api/v1/privacy/evaluate-egress",
        "/api/v1/providers/",
        "/api/v1/providers/scan",
        "/api/v1/providers/{provider_id}",
        "/api/v1/providers/{provider_id}/projects",
        "/api/v1/projects/",
        "/api/v1/projects/scan",
        "/api/v1/projects/{project_id}",
        "/api/v1/projects/{project_id}/link",
        "/api/v1/projects/{project_id}/resolve",
        "/api/v1/projects/{project_id}/confidence",
        "/api/v1/projects/{project_id}/repair",
        "/api/v1/projects/{project_id}/fix-and-redeploy",
        "/api/v1/projects/{project_id}/repair-contexts",
        "/api/v1/projects/{project_id}/latest-repair",
        "/api/v1/providers/{provider_id}/redeploy",
        "/api/v1/providers/{provider_id}/restart",
        "/api/v1/providers/{provider_id}/deployments",
        "/api/v1/providers/{provider_id}/logs",
        "/api/v1/providers/{provider_id}/status",
    ):
        assert rel in paths, f"missing {rel}"
