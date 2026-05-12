# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class OpsAction:
    """Whitelisted ops action. Execution is implemented in ops_executor (no arbitrary user shell)."""

    name: str
    requires_approval: bool
    description: str = ""
    # Optional: used for documentation; handlers live in ops_executor
    _handler: Callable[..., Any] | None = field(default=None, repr=False, compare=False)


OPS_ACTIONS: dict[str, OpsAction] = {}


def register_action(action: OpsAction) -> None:
    OPS_ACTIONS[action.name] = action


def get_action(name: str) -> OpsAction | None:
    return OPS_ACTIONS.get(name)


def _register_default_ops_actions() -> None:
    specs: list[tuple[str, bool, str]] = [
        ("health", False, "Local worker and host health (read-only)"),
        ("status", False, "Project / provider process status (read-only)"),
        ("logs", False, "Tail logs for a whitelisted service (bounded)"),
        ("queue", False, "Dev executor queue snapshot"),
        ("jobs", False, "Recent jobs list"),
        ("deploy_staging", True, "Deploy to staging (requires explicit approval)"),
        ("deploy_production", True, "Deploy to production (requires explicit approval)"),
        ("restart_service", True, "Restart a whitelisted process (requires approval)"),
        (
            "set_env_var",
            True,
            "Propose an env var change (never stores secrets; requires approval)",
        ),
        ("rollback", True, "Rollback / redeploy previous revision (requires approval)"),
    ]
    for name, needs_app, blurb in specs:
        if name not in OPS_ACTIONS:
            register_action(OpsAction(name=name, requires_approval=needs_app, description=blurb))


_register_default_ops_actions()
