# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import register_manifest


def test_e2e_automation_pack_run(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    register_manifest(
        PluginManifest(
            plugin_id="e2e-pack",
            name="E2E",
            capabilities=["automation_pack"],
            automation_pack="monitoring",
        )
    )
    r = client.post(
        "/api/v1/mission-control/automation-packs/e2e-pack/run",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200
