# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_setup_certify_api(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    for path in ("/api/v1/setup/status", "/api/v1/setup/one-curl", "/api/v1/setup/env-audit"):
        r = client.get(path)
        assert r.status_code == 200, path
    certify = client.get("/api/v1/setup/certify")
    assert certify.status_code == 200
    assert certify.json().get("phase") == "phase4_step11"
