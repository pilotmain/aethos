# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.execution.tool_step import execute_tool_step, tool_result_ok


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    yield tmp_path


def test_noop_tool_step(isolated_home) -> None:
    step = {"step_id": "n1", "type": "noop", "tool": {"name": "noop", "input": {}}}
    r = execute_tool_step(step)
    assert tool_result_ok("noop", r)


def test_tool_step_echo_ok(isolated_home) -> None:
    step = {"step_id": "s1", "type": "shell", "tool": {"name": "shell", "input": {"command": "echo tool_step_ok"}}}
    r = execute_tool_step(step)
    assert r.get("returncode") == 0
    assert "tool_step_ok" in str(r.get("stdout") or "")
    assert tool_result_ok("shell", r)
