# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for approval-gated command execution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.agent_job import AgentJob
from app.services import host_executor
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.host_executor_intent import infer_host_executor_action, parse_command_intent


def _settings(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        host_executor_work_root=str(root.resolve()),
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
        nexa_access_permissions_enforced=False,
        nexa_allowed_commands=(
            "npm,yarn,pnpm,pip,python,python3,node,npx,git,gh,ls,cat,echo,mkdir,touch,cp,mv,cd,pwd"
        ),
        nexa_approval_bypass_reason="tests",
        nexa_approvals_enabled=True,
        nexa_audit_enforcement_paths=False,
        nexa_command_execution_enabled=True,
        nexa_command_timeout_seconds=60,
        nexa_command_work_root=str(root.resolve()),
        nexa_host_executor_enabled=True,
        nexa_host_executor_dry_run_default=False,
        nexa_sensitive_external_confirmation_required=False,
        nexa_workspace_mode="regulated",
    )


class TestCommandExecution:
    def test_safe_command(self) -> None:
        assert host_executor.is_command_safe("ls -la") is True
        assert host_executor.is_command_safe("npm install express") is True

    def test_unsafe_command(self) -> None:
        assert host_executor.is_command_safe("rm -rf /") is False
        assert host_executor.is_command_safe("rm -rf ~") is False
        assert host_executor.is_command_safe("cat /etc/passwd") is False
        assert host_executor.is_command_safe("echo hi > out.txt") is False

    def test_parse_command_intent(self) -> None:
        run = parse_command_intent("run ls -la")
        assert run is not None
        assert run["command_type"] == "run_command"
        assert run["command"] == "ls -la"

        bare = parse_command_intent("ls -la")
        assert bare is not None
        assert bare["command_type"] == "run_command_bare_ls"
        assert bare["command"] == "ls -la"

        bare2 = parse_command_intent("ls")
        assert bare2 is not None
        assert bare2["command"] == "ls"

        install = parse_command_intent("install express")
        assert install is not None
        assert install["command_type"] == "install_package"
        assert install["command"] == "npm install express"

        mkdir = parse_command_intent("create directory src/components")
        assert mkdir is not None
        assert mkdir["command"] == "mkdir -p src/components"

    def test_infer_host_executor_bare_ls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        s = _settings(tmp_path)
        monkeypatch.setattr("app.services.host_executor_intent.get_settings", lambda: s)
        pl = infer_host_executor_action("ls -la")
        assert pl is not None
        assert pl.get("host_action") == "run_command"
        assert pl.get("command") == "ls -la"
        assert pl.get("command_type") == "run_command_bare_ls"

    def test_execute_payload_runs_safe_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings(tmp_path)
        monkeypatch.setattr(host_executor, "get_settings", lambda: settings)

        out = host_executor.execute_payload({"host_action": "run_command", "command": "echo Hello AethOS"})

        assert "Hello AethOS" in out

    @pytest.mark.usefixtures("nexa_runtime_clean")
    def test_gateway_run_ls_queues_command_job(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        nexa_runtime_clean,
    ) -> None:
        settings = _settings(tmp_path)
        for target in (
            "app.core.config.get_settings",
            "app.services.host_executor.get_settings",
            "app.services.host_executor_chat.get_settings",
            "app.services.host_executor_intent.get_settings",
            "app.services.permission_request_flow.get_settings",
            "app.services.runtime_capabilities.get_settings",
        ):
            monkeypatch.setattr(target, lambda settings=settings: settings)

        ctx = GatewayContext.from_channel(
            "hx_gateway_command",
            "web",
            {"web_session_id": "sess-command"},
        )
        out = NexaGateway().handle_message(ctx, "run ls -la", db=nexa_runtime_clean)
        assert out.get("host_executor") is True
        assert out.get("intent") == "command_approval"
        assert "Approval: required" in (out.get("text") or "")

        out_yes = NexaGateway().handle_message(ctx, "yes", db=nexa_runtime_clean)
        assert out_yes.get("related_job_ids")
        job = nexa_runtime_clean.get(AgentJob, out_yes["related_job_ids"][0])
        assert job is not None
        assert job.status == "needs_approval"
        assert (job.payload_json or {}).get("host_action") == "run_command"
        assert (job.payload_json or {}).get("command") == "ls -la"
