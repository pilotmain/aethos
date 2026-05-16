# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step15_setup_apis(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    for path in (
        "/api/v1/setup/continuity",
        "/api/v1/setup/operator-profile",
        "/api/v1/setup/experience",
        "/api/v1/setup/first-impression",
        "/api/v1/setup/status",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
