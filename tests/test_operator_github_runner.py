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
    assert "What this step did" not in body


def test_github_runner_success_includes_verify_vs_mutate_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_runners.github.profile_shell_enabled", lambda: False)

    def _fake_run(argv, *, cwd):
        return {"ok": True, "exit_code": 0, "stdout": "logged in", "stderr": ""}

    monkeypatch.setattr("app.services.operator_runners.github._run_allowlisted", _fake_run)
    monkeypatch.setattr("app.services.operator_runners.github.operator_cli_argv_resolves", lambda _: True)
    from app.services.operator_runners.github import run_github_operator_readonly

    body, _ev, _p, verified = run_github_operator_readonly(cwd=None)
    assert verified is True
    assert "What this step did" in body
    assert "host executor" in body.lower()
    assert "RUNBOOK" in body or "runbook" in body.lower()
