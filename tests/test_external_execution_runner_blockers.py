# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — runner surfaces exact blockers; never runs deploy/push commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.external_execution_runner import (
    BoundedRailwayInvestigation,
    format_investigation_for_chat,
    investigation_to_public_payload,
    run_bounded_railway_repo_investigation,
)
from app.services.integrations.railway.cli import run_railway_cli


def test_investigation_to_public_payload_skipped() -> None:
    inv = BoundedRailwayInvestigation(skipped_reason="host_executor_disabled")
    assert investigation_to_public_payload(inv) == {"ran": False, "reason": "host_executor_disabled"}


def test_investigation_to_public_payload_ran() -> None:
    inv = BoundedRailwayInvestigation(skipped_reason=None, workspace_paths=["/tmp/w"])
    assert investigation_to_public_payload(inv) == {"ran": True, "reason": None}


def test_format_host_executor_disabled_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_runner._operator_zero_nag",
        lambda: False,
    )
    inv = BoundedRailwayInvestigation(skipped_reason="host_executor_disabled")
    inv.policy_note = "_p_"
    txt = format_investigation_for_chat(inv)
    assert "tried to start read-only checks" in txt.lower()
    assert "nexa_host_executor_enabled" in txt.lower()


def test_format_railway_cli_missing_banner_when_no_binary() -> None:
    inv = BoundedRailwayInvestigation(workspace_paths=["/tmp/w"])
    inv.railway_cli_present = False
    inv.railway_env_token_present = False
    inv.railway_whoami = {"ok": False, "error": "railway_cli_missing", "stdout": "", "stderr": ""}
    txt = format_investigation_for_chat(inv)
    assert "`railway` not found in path" in txt.lower()
    assert "no credentials available" in txt.lower()


def test_format_no_extra_credentials_line_when_token_env_set() -> None:
    inv = BoundedRailwayInvestigation(workspace_paths=["/tmp/w"])
    inv.railway_cli_present = False
    inv.railway_env_token_present = True
    inv.railway_whoami = {"ok": False, "error": "railway_cli_missing", "stdout": "", "stderr": ""}
    txt = format_investigation_for_chat(inv)
    assert "no credentials available" not in txt.lower()


@patch("app.services.external_execution_runner.run_railway_cli")
@patch("app.services.external_execution_runner.list_workspaces")
@patch("app.services.external_execution_runner.get_settings")
def test_runner_never_calls_deploy_or_push(
    m_settings, m_lsw, m_rail, db_session, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr("app.services.external_execution_runner.Path.is_dir", lambda self: True)
    m_lsw.return_value = []
    # Pretend one workspace row:
    class Row:
        repo_path = str(tmp_path)

    m_lsw.return_value = [Row()]
    s = m_settings.return_value
    s.nexa_external_execution_runner_enabled = True
    s.nexa_host_executor_enabled = True

    run_bounded_railway_repo_investigation(db_session, "u1", {"auth_method": "local_cli"})
    argv_hist = [tuple(call.args[0]) for call in m_rail.call_args_list]
    flat = " ".join(" ".join(a) for a in argv_hist).lower()
    assert "railway up" not in flat
    assert "railway deploy" not in flat
    assert "git push" not in flat


def test_cli_module_rejects_deploy_subcommands() -> None:
    assert run_railway_cli("deploy", [], cwd=None).get("error") == "railway_subcommand_not_allowed"
    assert run_railway_cli("up", [], cwd=None).get("error") == "railway_subcommand_not_allowed"
