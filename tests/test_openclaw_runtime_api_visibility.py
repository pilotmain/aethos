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
        "/api/v1/runtime/events",
        "/api/v1/runtime/artifacts",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
