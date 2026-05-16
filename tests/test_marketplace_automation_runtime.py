# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.plugins.plugin_manifest import PluginManifest
from app.plugins.plugin_registry import register_manifest
from app.runtime.automation_pack_runtime import build_automation_pack_runtime_truth, run_automation_pack


def test_run_pack_records_execution() -> None:
    register_manifest(
        PluginManifest(
            plugin_id="step10-test-pack",
            name="Step10 Pack",
            capabilities=["automation_pack"],
            automation_pack="deployment",
            verified=True,
        )
    )
    out = run_automation_pack("step10-test-pack")
    assert out.get("ok") is True
    truth = build_automation_pack_runtime_truth()
    assert truth.get("recent_executions")
