"""Phase 58 — bounded Railway/repo runner (truth-first, never auto-deploy)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.external_execution_runner import (
    BoundedRailwayInvestigation,
    format_investigation_for_chat,
    run_bounded_railway_repo_investigation,
)
from app.services.integrations.railway.cli import run_railway_cli


def test_run_railway_cli_rejects_disallowed_subcommand() -> None:
    r = run_railway_cli("up", [], cwd=None, timeout=5.0)
    assert r.get("ok") is False
    assert r.get("error") == "railway_subcommand_not_allowed"


def test_run_railway_cli_rejects_extra_args_for_whoami() -> None:
    r = run_railway_cli("whoami", ["--json"], cwd=None, timeout=5.0)
    assert r.get("ok") is False
    assert r.get("error") == "extra_args_not_allowed_for_subcommand"


def test_format_report_first_policy_note() -> None:
    inv = BoundedRailwayInvestigation(skipped_reason="runner_disabled")
    inv.deploy_blocked_by_policy = True
    inv.policy_note = "_Deploy remains **blocked** until you approve — findings below are diagnostic only._"
    txt = format_investigation_for_chat(inv)
    assert "runner is disabled" in txt.lower() or "disabled" in txt.lower()
    assert "deploy" in txt.lower()


def test_format_respects_deploy_when_ready_policy_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner._operator_zero_nag",
        lambda: False,
    )
    inv = BoundedRailwayInvestigation(skipped_reason="no_workspace")
    inv.deploy_blocked_by_policy = False
    inv.policy_note = "_Deploy is **not** triggered automatically._"
    txt = format_investigation_for_chat(inv)
    assert "not** triggered automatically" in txt or "not triggered" in txt.lower()


def test_truth_footer_when_commands_ran() -> None:
    inv = BoundedRailwayInvestigation(
        skipped_reason=None,
        workspace_paths=["/tmp/ws"],
    )
    inv.railway_whoami = {"ok": True, "stdout": "user@x", "stderr": ""}
    inv.git_status = {"ok": True, "stdout": "On branch main", "stderr": ""}
    out = format_investigation_for_chat(inv)
    assert "user@x" in out
    assert "On branch main" in out
    assert "no deploy" in out.lower() or "deploy" in out.lower()


@patch("app.services.external_execution_runner.run_railway_cli")
@patch("app.services.external_execution_runner.list_workspaces")
@patch("app.services.external_execution_runner.get_settings")
def test_runner_skips_when_host_executor_off(
    m_settings, m_lsw, m_rail, db_session, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.external_execution_runner.Path.is_dir", lambda self: True)
    m_lsw.return_value = []
    s = m_settings.return_value
    s.nexa_external_execution_runner_enabled = True
    s.nexa_host_executor_enabled = False

    r = run_bounded_railway_repo_investigation(db_session, "u1", {"deploy_mode": "report_then_approve"})
    assert r.skipped_reason == "host_executor_disabled"
    m_rail.assert_not_called()
