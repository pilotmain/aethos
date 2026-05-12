# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — access copy explains env not loaded; chat paste ≠ worker credentials."""

from __future__ import annotations

from app.services.external_execution_access import (
    ExternalExecutionAccess,
    assess_external_execution_access,
    format_external_execution_access_reply,
)


def test_access_reply_mentions_env_not_loaded_not_generic_login(db_session, monkeypatch) -> None:
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    monkeypatch.delenv("RAILWAY_API_TOKEN", raising=False)

    acc = ExternalExecutionAccess(
        dev_workspace_registered=True,
        host_executor_enabled=True,
        railway_token_present=False,
        railway_cli_on_path=False,
        github_token_configured=False,
    )
    txt = format_external_execution_access_reply(acc, user_text="check railway logs")
    low = txt.lower()
    assert "railway_token" in low or "railway_api_token" in low
    assert "not loaded in this worker" in low
    assert "chat" in low or ".env" in low


def test_assess_marks_token_present_when_env_set(db_session, monkeypatch) -> None:
    monkeypatch.setenv("RAILWAY_TOKEN", "test-token-placeholder")
    acc = assess_external_execution_access(db_session, "user-z")
    assert acc.railway_token_present is True
    assert acc.railway_access_available is True
