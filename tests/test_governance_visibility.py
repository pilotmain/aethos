# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.services.runtime_governance import build_governance_timeline


def test_timeline_has_automation_kind() -> None:
    from app.plugins.plugin_manifest import PluginManifest
    from app.plugins.plugin_registry import register_manifest
    from app.runtime.automation_pack_runtime import run_automation_pack

    register_manifest(
        PluginManifest(
            plugin_id="gov-pack",
            name="Gov",
            capabilities=["automation_pack"],
            automation_pack="deployment",
        )
    )
    run_automation_pack("gov-pack")
    kinds = {e.get("kind") for e in build_governance_timeline(limit=50).get("timeline") or []}
    assert "automation_pack" in kinds or "governance" in kinds


def test_governance_risks_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/governance/risks", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "operational_risk" in r.json()
