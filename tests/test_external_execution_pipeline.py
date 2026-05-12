# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic external execution pipeline — composes access + runner + summary."""

from __future__ import annotations

from unittest.mock import patch

from app.services.external_execution_pipeline import PipelineContext, run_pipeline
from app.services.external_execution_runner import BoundedRailwayInvestigation


@patch("app.services.external_execution_pipeline.run_bounded_railway_repo_investigation")
@patch("app.services.external_execution_pipeline.assess_external_execution_access")
def test_run_pipeline_returns_access_investigation_summary(
    m_acc, m_run, db_session
) -> None:
    from app.services.external_execution_access import ExternalExecutionAccess

    m_acc.return_value = ExternalExecutionAccess(
        dev_workspace_registered=True,
        host_executor_enabled=True,
        railway_token_present=False,
        railway_cli_on_path=True,
        github_token_configured=False,
    )
    inv = BoundedRailwayInvestigation(skipped_reason="no_workspace")
    inv.progress_lines = ["Starting investigation", "Stopped: no dev workspace"]
    m_run.return_value = inv

    out = run_pipeline(
        PipelineContext(db_session, "u-pipe", {"deploy_mode": "report_then_approve"})
    )
    assert out["access"]["railway_access_available"] is True
    assert out["investigation"].skipped_reason == "no_workspace"
    assert "### Summary" in out["summary_markdown"]
    assert "✖" in out["summary_markdown"] or "blocked" in out["summary_markdown"].lower()
