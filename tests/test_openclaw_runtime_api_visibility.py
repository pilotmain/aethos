# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations


def test_runtime_api_sessions_metrics_health(api_client) -> None:
    client, uid = api_client
    for path in (
        "/api/v1/runtime/sessions",
        "/api/v1/runtime/metrics",
        "/api/v1/runtime/queues",
        "/api/v1/runtime/health",
        "/api/v1/runtime/integrity",
        "/api/v1/runtime/events",
        "/api/v1/runtime/artifacts",
        "/api/v1/deployments",
        "/api/v1/environments",
        "/api/v1/operations",
        "/api/v1/runtime/supervisors",
        "/api/v1/runtime/loops",
        "/api/v1/runtime/agents/",
        "/api/v1/runtime/planning",
        "/api/v1/runtime/reasoning",
        "/api/v1/runtime/optimization",
        "/api/v1/runtime/replanning",
        "/api/v1/runtime/recovery",
        "/api/v1/runtime/backups",
        "/api/v1/runtime/corruption",
    ):
        r = client.get(path)
        assert r.status_code == 200, path


def test_runtime_planning_show_unknown_returns_404(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/runtime/planning/pln_does_not_exist_zz")
    assert r.status_code == 404
