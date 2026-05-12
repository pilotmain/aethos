# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — Railway-shaped asks route through execution loop with investigation framing."""

from __future__ import annotations

import uuid

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_railway_check_request_receives_progress_not_generic_guidance(monkeypatch, db_session) -> None:
    """Bounded runner path should surface progress-style copy, not generic coaching."""
    from app.services.external_execution_access import ExternalExecutionAccess
    from app.services.external_execution_runner import BoundedRailwayInvestigation

    monkeypatch.setattr(
        "app.services.external_execution_access.assess_external_execution_access",
        lambda db, uid: ExternalExecutionAccess(
            dev_workspace_registered=True,
            host_executor_enabled=True,
            railway_token_present=True,
            railway_cli_on_path=True,
            github_token_configured=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "app.services.external_execution_runner.run_bounded_railway_repo_investigation",
        lambda *_a, **_k: BoundedRailwayInvestigation(
            skipped_reason=None,
            progress_lines=["Starting investigation", "railway whoami ok"],
        ),
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(
        gctx,
        "Can you check Railway and fix my service?",
        db=db_session,
    )
    body = (out.get("text") or "").lower()
    assert out.get("execution_loop") is True
    assert "starting investigation" in body or "progress" in body
    assert "i can guide you" not in body
    assert "paste logs" not in body
