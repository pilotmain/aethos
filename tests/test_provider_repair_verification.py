# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.providers.repair.repair_verification import run_verification_suite


def test_verification_rejects_disallowed_command(tmp_path: Path) -> None:
    from app.providers.repair.repair_verification import _run_shell

    row = _run_shell("rm -rf /", tmp_path)
    assert row.get("ok") is False


def test_verification_compileall_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "py"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo / "main.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.providers.repair.repair_verification._run_shell",
        lambda cmd, cwd, **kw: {"ok": True, "command": cmd, "returncode": 0, "cli": {"preview": ""}},
    )
    out = run_verification_suite(repo)
    assert out.get("ok") is True
