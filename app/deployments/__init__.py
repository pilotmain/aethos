# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deployment runtime (OpenClaw parity — persistent deployment lifecycle in ``aethos.json``)."""

from __future__ import annotations

from app.deployments.deployment_registry import deployment_records, get_deployment, list_deployments_for_user
from app.deployments.deployment_runtime import (
    deployment_id_for_plan,
    note_deploy_step_started,
    on_operator_plan_created_if_deploy,
    sync_deployment_terminal,
)

__all__ = [
    "deployment_records",
    "deployment_id_for_plan",
    "get_deployment",
    "list_deployments_for_user",
    "note_deploy_step_started",
    "on_operator_plan_created_if_deploy",
    "sync_deployment_terminal",
]
