# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Local CLI PATH enrichment + operator reply formatting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.intent_focus_filter import clean_operator_reply_format
from app.services.operator_cli_path import cli_environ_for_operator, which_operator_cli
from app.services.gateway.runtime import gateway_finalize_operator_or_execution_reply


def test_cli_environ_prepends_standard_locations() -> None:
    env = cli_environ_for_operator()
    path = env.get("PATH", "")
    assert "/usr/local/bin" in path
    assert "/opt/homebrew/bin" in path
    assert "/usr/bin" in path


def test_clean_operator_reply_format_strips_horizontal_rules() -> None:
    raw = "### Progress\n\n→ x\n\n---\n\n### Output\n\nhello"
    assert "---" not in clean_operator_reply_format(raw)


def test_gateway_finalize_operator_strips_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    _s = SimpleNamespace(
        nexa_operator_mode=True,
        nexa_operator_precise_short_responses=False,
        nexa_operator_proactive_intro=False,
        nexa_operator_zero_nag=False,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.gateway.runtime.get_settings", lambda: _s)
    monkeypatch.setattr("app.services.operator_orchestration_intro.get_settings", lambda: _s)
    body = "### Progress\n\n→ step\n\n---\n\nDone."
    out = gateway_finalize_operator_or_execution_reply(body, user_text="check vercel", layer="operator_execution")
    assert "---" not in out
    assert "Done." in out


@patch("app.services.operator_runners.vercel.subprocess.run")
def test_vercel_subprocess_receives_enriched_env(mock_run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_runners.vercel.profile_shell_enabled", lambda: False)
    monkeypatch.setattr("app.services.operator_runners.vercel.operator_cli_argv_resolves", lambda _: True)

    class Proc:
        returncode = 0
        stdout = "user@test.dev"
        stderr = ""

    mock_run.return_value = Proc()

    from app.services.operator_runners.vercel import run_vercel_operator_readonly

    run_vercel_operator_readonly(cwd=None)
    assert mock_run.called
    env = mock_run.call_args.kwargs.get("env")
    assert env is not None
    path = env.get("PATH", "")
    assert "/opt/homebrew/bin" in path or "/usr/local/bin" in path


def test_which_operator_cli_matches_subprocess_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_which(name: str, mode: int | None = None, path: str | None = None) -> str | None:
        captured["path"] = path
        if path and "/usr/bin" in path:
            return "/usr/bin/gh"
        return None

    monkeypatch.setattr("app.services.operator_cli_path.shutil.which", fake_which)
    assert which_operator_cli("gh") == "/usr/bin/gh"
    assert captured.get("path") is not None
