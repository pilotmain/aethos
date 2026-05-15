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


def test_workflow_builder_run_project_verification(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    steps = build_steps_from_operator_text("run project verification")
    assert len(steps) == 1
    cmd = str(steps[0].get("tool", {}).get("input", {}).get("command") or "")
    assert "compileall" in cmd and " -q ." in cmd


def test_workflow_builder_create_file_and_summarize(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    steps = build_steps_from_operator_text("create a file in workspace and summarize it")
    assert len(steps) == 2
    assert steps[0].get("tool", {}).get("name") == "file_write"
    assert steps[1].get("tool", {}).get("name") == "file_read"
    assert steps[0].get("step_id") in (steps[1].get("depends_on") or [])


def test_workflow_builder_delegate_verification_and_deploy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    steps = build_steps_from_operator_text(
        "delegate verification and deployment to separate agents",
    )
    assert len(steps) == 2
    assert steps[0].get("tool", {}).get("name") == "shell"
    assert steps[1].get("tool", {}).get("name") == "deploy"
    assert steps[0].get("step_id") in (steps[1].get("depends_on") or [])
