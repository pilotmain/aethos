# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.tools.runtime_shell import run_shell_command


def test_shell_runtime_allowlisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    r = run_shell_command("echo shell_rt")
    assert r.get("returncode") == 0
    assert r.get("ok") is True
    assert "shell_rt" in str(r.get("stdout") or "")


def test_shell_runtime_rejects_unsafe(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    r = run_shell_command("rm -rf /")
    assert r.get("returncode") == -1
