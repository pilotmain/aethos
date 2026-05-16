# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bridge deploy context → provider actions (Phase 2 Step 4)."""

from __future__ import annotations

from typing import Any

from app.deploy_context.context_resolution import build_deploy_context
from app.providers.actions import vercel_actions


def execute_vercel_redeploy(project_slug: str, *, environment: str = "production") -> dict[str, Any]:
    ctx = build_deploy_context(project_slug, provider="vercel", environment=environment)
    return vercel_actions.redeploy_latest(ctx, environment=environment)


def execute_vercel_restart(project_slug: str, *, environment: str = "production") -> dict[str, Any]:
    """For Vercel serverless, restart maps to redeploy of latest production deployment."""
    ctx = build_deploy_context(project_slug, provider="vercel", environment=environment)
    return vercel_actions.restart_project(ctx, environment=environment)


def execute_vercel_status(project_slug: str, *, environment: str = "production") -> dict[str, Any]:
    ctx = build_deploy_context(project_slug, provider="vercel", environment=environment)
    return vercel_actions.deployment_status(ctx, environment=environment)


def execute_vercel_logs(project_slug: str, *, environment: str = "production", limit: int = 80) -> dict[str, Any]:
    ctx = build_deploy_context(project_slug, provider="vercel", environment=environment)
    return vercel_actions.deployment_logs(ctx, environment=environment, limit=limit)
