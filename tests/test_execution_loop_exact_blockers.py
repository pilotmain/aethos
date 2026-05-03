"""P0 — gated / blocked paths surface exact access blockers (no vague refusal)."""

from __future__ import annotations

import uuid

import pytest

from app.services.external_execution_access import ExternalExecutionAccess
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_no_railway_access_lists_token_env(monkeypatch, db_session) -> None:
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
    monkeypatch.setattr(
        "app.services.external_execution_access.should_gate_external_execution",
        lambda *_a, **_k: True,
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(
        gctx,
        "check Railway status for my project",
        db=db_session,
    )
    body = out.get("text") or ""
    lower = body.lower()
    assert "railway" in lower
    assert "railway_token" in lower or "RAILWAY_TOKEN" in body
