"""Operator GitHub runner — gh auth status."""

from __future__ import annotations

import pytest


def test_github_runner_reports_missing_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_runners.github.profile_shell_enabled", lambda: False)
    monkeypatch.setattr("app.services.operator_runners.github.operator_cli_argv_resolves", lambda _: False)
    from app.services.operator_runners.github import run_github_operator_readonly

    body, ev, _p, verified = run_github_operator_readonly(cwd=None)
    assert "gh" in body.lower() or "github cli" in body.lower()
    assert verified is False
    assert ev.get("provider") == "github"
