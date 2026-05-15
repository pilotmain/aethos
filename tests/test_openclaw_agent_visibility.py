# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations


def test_agents_api_list_ok(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/runtime/agents/")
    assert r.status_code == 200
    assert "agents" in r.json()
