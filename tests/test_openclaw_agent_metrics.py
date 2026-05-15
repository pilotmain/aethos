# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations


def test_runtime_metrics_include_coordination_keys(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/runtime/metrics")
    assert r.status_code == 200
    m = r.json().get("metrics") or {}
    assert "coordination_active_agents" in m
