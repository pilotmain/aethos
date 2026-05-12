# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator Vercel runner — bounded CLI behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_vercel_runner_reports_cli_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_runners.vercel.profile_shell_enabled", lambda: False)
    monkeypatch.setattr("app.services.operator_runners.vercel.operator_cli_argv_resolves", lambda _: False)
    from app.services.operator_runners.vercel import run_vercel_operator_readonly

    body, ev, _prog, verified = run_vercel_operator_readonly(cwd=None)
    low = body.lower()
    assert "`vercel` not found in path" in low
    assert verified is False
    assert ev.get("provider") == "vercel"


@patch("app.services.operator_runners.vercel.subprocess.run")
def test_vercel_runner_whoami_ok(mock_run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_runners.vercel.profile_shell_enabled", lambda: False)
    monkeypatch.setattr("app.services.operator_runners.vercel.operator_cli_argv_resolves", lambda _: True)

    class Proc:
        returncode = 0
        stdout = "user@example.com"
        stderr = ""

    mock_run.return_value = Proc()

    from app.services.operator_runners.vercel import _run_vercel_allowlisted

    out = _run_vercel_allowlisted(["vercel", "whoami"], cwd=None)
    assert out.get("ok") is True
    assert "user@" in (out.get("stdout") or "")
