# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_includes_plugin_health_and_traces() -> None:
    t = build_runtime_truth(user_id=None)
    plugins = t.get("plugins") or {}
    assert "healthy_count" in plugins
    traces = t.get("operator_traces") or {}
    assert "provider" in traces
