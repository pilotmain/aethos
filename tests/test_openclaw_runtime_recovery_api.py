# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations


def test_runtime_recovery_backups_corruption_endpoints(api_client) -> None:
    client, _uid = api_client
    for path in (
        "/api/v1/runtime/recovery",
        "/api/v1/runtime/backups",
        "/api/v1/runtime/corruption",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        data = r.json()
        assert isinstance(data, dict)
