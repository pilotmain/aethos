# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — retry external execution requires Railway CLI or env token on worker."""

from __future__ import annotations

import json

from app.services.conversation_context_service import get_or_create_context
from app.services.external_execution_access import ExternalExecutionAccess
from app.services.external_execution_session import try_retry_external_execution_turn


def test_retry_blocked_when_no_railway_access(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.assess_external_execution_access",
        lambda db, uid: ExternalExecutionAccess(
            dev_workspace_registered=True,
            host_executor_enabled=True,
            railway_token_present=False,
            railway_cli_on_path=False,
            github_token_configured=False,
        ),
    )

    uid = "u-retry-block"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json.dumps(
        {
            "external_execution": {
                "status": "completed",
                "collected": {},
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }
    )
    db_session.add(cctx)
    db_session.commit()

    out = try_retry_external_execution_turn(db_session, uid, "retry external execution", cctx)
    assert out is not None
    text = (out.get("text") or "").lower()
    assert "railway_token" in text.replace(" ", "").replace("`", "")
    assert "not loaded in this worker" in text
    assert "can't log in" not in text
    assert "cannot log in" not in text


def test_retry_proceeds_when_token_present(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.external_execution_access.assess_external_execution_access",
        lambda db, uid: ExternalExecutionAccess(
            dev_workspace_registered=True,
            host_executor_enabled=True,
            railway_token_present=True,
            railway_cli_on_path=False,
            github_token_configured=False,
        ),
    )
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: __import__(
            "app.services.external_execution_runner", fromlist=["BoundedRailwayInvestigation"]
        ).BoundedRailwayInvestigation(skipped_reason="host_executor_disabled"),
    )

    uid = "u-retry-ok"
    cctx = get_or_create_context(db_session, uid)
    cctx.current_flow_state_json = json.dumps(
        {
            "external_execution": {
                "status": "completed",
                "collected": {},
                "updated_at": "2099-01-01T00:00:00+00:00",
            }
        }
    )
    db_session.add(cctx)
    db_session.commit()

    out = try_retry_external_execution_turn(db_session, uid, "retry external execution", cctx)
    assert out is not None
    assert "retrying railway investigation" in (out.get("text") or "").lower()
