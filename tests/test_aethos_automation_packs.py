# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.automation_packs import list_automation_packs_with_health, set_automation_pack_enabled


def test_automation_pack_enable_toggle() -> None:
    out = set_automation_pack_enabled("deployment-automation-pack", enabled=False)
    assert out.get("enabled") is False
    set_automation_pack_enabled("deployment-automation-pack", enabled=True)


def test_packs_have_health() -> None:
    from app.plugins.plugin_manifest import PluginManifest
    from app.plugins.plugin_registry import register_manifest

    register_manifest(
        PluginManifest(
            plugin_id="test-automation-pack",
            name="Test Pack",
            capabilities=["automation_pack"],
            automation_pack="deployment",
        )
    )
    packs = list_automation_packs_with_health()
    assert packs
    for p in packs:
        assert "health" in p
        assert "enabled" in p
