# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Shared helpers for ``product_e2e`` tests (host executor settings patches)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def host_executor_settings_bundle(root: Path) -> SimpleNamespace:
    """Minimal settings bundle for gateway host-action tests under ``root``."""
    return SimpleNamespace(
        host_executor_work_root=str(root.resolve()),
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
        # Used by gateway fall-through paths that import get_settings from app.core.config.
        nexa_orchestration_enabled=False,
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


def patch_host_executor_for_e2e(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    include_enforcement_pipeline: bool,
) -> Path:
    """Return workspace directory under ``tmp_path`` used for relative file paths."""
    workspace = tmp_path / "e2e_workspace"
    workspace.mkdir()
    settings = host_executor_settings_bundle(tmp_path)
    targets = [
        "app.core.config.get_settings",
        "app.services.host_executor.get_settings",
        "app.services.host_executor_chat.get_settings",
        "app.services.host_executor_intent.get_settings",
        "app.services.permission_request_flow.get_settings",
        "app.services.runtime_capabilities.get_settings",
    ]
    if include_enforcement_pipeline:
        targets.insert(1, "app.services.enforcement_pipeline.get_settings")
    for target in targets:
        monkeypatch.setattr(target, lambda s=settings: s)
    return workspace


__all__ = ["host_executor_settings_bundle", "patch_host_executor_for_e2e"]
