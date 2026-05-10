"""Gateway routing for natural-language file writes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.agent_job import AgentJob
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


def _host_settings(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        host_executor_work_root=str(root.resolve()),
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
        nexa_access_permissions_enforced=False,
        nexa_approval_bypass_reason="tests",
        nexa_approvals_enabled=True,
        nexa_audit_enforcement_paths=False,
        nexa_host_executor_enabled=True,
        nexa_sensitive_external_confirmation_required=False,
        nexa_workspace_mode="regulated",
    )


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_file_write_phrase_queues_host_executor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    nexa_runtime_clean,
) -> None:
    workspace = tmp_path / "aethos_workspace"
    workspace.mkdir()
    settings = _host_settings(tmp_path)

    for target in (
        "app.core.config.get_settings",
        "app.services.enforcement_pipeline.get_settings",
        "app.services.host_executor.get_settings",
        "app.services.host_executor_chat.get_settings",
        "app.services.host_executor_intent.get_settings",
        "app.services.permission_request_flow.get_settings",
        "app.services.runtime_capabilities.get_settings",
    ):
        monkeypatch.setattr(target, lambda settings=settings: settings)

    ctx = GatewayContext.from_channel(
        "hx_gateway_file",
        "web",
        {"web_session_id": "sess-file"},
    )
    out = NexaGateway().handle_message(
        ctx,
        f"Create a file called test.txt with content 'Hello AethOS' in {workspace}",
        db=nexa_runtime_clean,
    )

    assert out.get("host_executor") is True
    assert out.get("intent") == "file_write"
    assert "Approval: required" in (out.get("text") or "")

    out_yes = NexaGateway().handle_message(ctx, "yes", db=nexa_runtime_clean)
    assert out_yes.get("host_executor") is True
    assert out_yes.get("intent") == "file_write"
    assert out_yes.get("related_job_ids")

    job = nexa_runtime_clean.get(AgentJob, out_yes["related_job_ids"][0])
    assert job is not None
    assert job.status == "needs_approval"
    assert (job.payload_json or {}).get("host_action") == "file_write"
    assert (job.payload_json or {}).get("relative_path") == "aethos_workspace/test.txt"

    from app.services.host_executor import execute_payload

    result = execute_payload(dict(job.payload_json or {}))
    assert "Wrote" in result
    assert (workspace / "test.txt").read_text(encoding="utf-8") == "Hello AethOS"
