# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve effective sandbox policy for tools/skills."""

from __future__ import annotations

import shutil
from typing import Any

from app.core.config import get_settings

from app.services.sandbox.types import SandboxMode, SandboxPolicy


def docker_cli_available() -> bool:
    return shutil.which("docker") is not None


def resolve_effective_mode(requested: SandboxMode) -> tuple[SandboxMode, bool, str | None]:
    """
    Returns ``(effective_mode, enforced, unsupported_reason)``.

    ``gvisor`` / ``firecracker`` are never activated implicitly — callers must supply
    explicit infra; otherwise we downgrade with a reason.
    """
    if requested in (SandboxMode.gvisor, SandboxMode.firecracker):
        return SandboxMode.process, False, f"{requested.value} requires explicit runtime integration"
    if requested == SandboxMode.docker:
        if docker_cli_available():
            return SandboxMode.docker, True, None
        return SandboxMode.process, True, "docker CLI not available; using process isolation"
    if requested == SandboxMode.disabled:
        return SandboxMode.disabled, True, None
    # process
    return SandboxMode.process, True, None


def resolve_sandbox_policy(
    tool_or_skill: str,
    requested_permissions: frozenset[str] | set[str] | None,
) -> SandboxPolicy:
    s = get_settings()
    raw = (getattr(s, "nexa_sandbox_mode", None) or "process").strip().lower()
    try:
        mode = SandboxMode(raw)
    except ValueError:
        mode = SandboxMode.process

    eff, enforced, reason = resolve_effective_mode(mode)
    perms = frozenset(requested_permissions or ())
    _ = tool_or_skill  # reserved for future per-tool routing
    return SandboxPolicy(
        mode=eff,
        enforced=enforced,
        unsupported_reason=reason,
        allowed_permissions=perms,
    )


__all__ = ["docker_cli_available", "resolve_effective_mode", "resolve_sandbox_policy"]
