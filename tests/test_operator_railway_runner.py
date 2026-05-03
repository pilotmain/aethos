"""Operator Railway runner delegates to bounded investigation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.external_execution_runner import BoundedRailwayInvestigation


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_railway_operator_readonly_delegates(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    from app.services.operator_runners import railway as rw

    inv = BoundedRailwayInvestigation(skipped_reason=None, progress_lines=["→ ok"])
    monkeypatch.setattr(
        "app.services.operator_runners.railway.run_bounded_railway_repo_investigation",
        lambda db, uid, coll: inv,
    )
    monkeypatch.setattr(
        "app.services.operator_runners.railway.format_investigation_for_chat",
        lambda i: "railway body",
    )
    monkeypatch.setattr(
        "app.services.operator_runners.railway.assess_external_execution_access",
        lambda db, uid: MagicMock(
            railway_token_present=False,
            railway_cli_on_path=True,
            dev_workspace_registered=True,
            host_executor_enabled=True,
        ),
    )

    body, ev, prog, ok = rw.run_railway_operator_readonly(db_session, "u1")
    assert "railway" in body.lower()
    assert ev.get("provider") == "railway"
