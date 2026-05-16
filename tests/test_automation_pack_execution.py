# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import register_manifest


def test_mc_run_automation_pack(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    register_manifest(
        PluginManifest(
            plugin_id="api-run-pack",
            name="API Pack",
            capabilities=["automation_pack"],
            automation_pack="repair",
        )
    )
    r = client.post(
        "/api/v1/mission-control/automation-packs/api-run-pack/run",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
