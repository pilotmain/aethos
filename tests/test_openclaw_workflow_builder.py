# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.execution.workflow_builder import build_steps_from_operator_text


def test_workflow_builder_maps_compileall(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    steps = build_steps_from_operator_text("run compileall now")
    assert len(steps) == 1
    assert steps[0].get("tool", {}).get("name") == "shell"
    assert "compileall" in str(steps[0].get("tool", {}).get("input", {}).get("command") or "")


def test_workflow_builder_list_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    steps = build_steps_from_operator_text("list workspace")
    assert steps[0].get("tool", {}).get("name") == "workspace_list"
