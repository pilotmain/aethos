"""P0 — executable infra asks must not fall through to generic coaching phrases."""

from __future__ import annotations

import uuid

import pytest

from app.services.external_execution_access import ExternalExecutionAccess
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_heavy_railway_ask_skips_compose_llm_generic(monkeypatch, db_session) -> None:
    """When runner handles the turn, compose_llm_reply must not run."""
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
            progress_lines=["→ Starting investigation"],
        ),
    )

    called: list[str] = []

    def boom(*_a, **_k):
        called.append("compose")
        return "I can guide you through Railway setup step by step."

    monkeypatch.setattr(NexaGateway, "compose_llm_reply", boom)

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(
        gctx,
        "Can you check Railway, inspect my local repo, fix the issue, and redeploy?",
        db=db_session,
    )
    assert called == []
    low = (out.get("text") or "").lower()
    assert "i can guide you" not in low
