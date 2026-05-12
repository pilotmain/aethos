# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Deterministic external execution pipeline — access → CLI checks → analysis → summary.

Lightweight: no GPU, no extra network; reuses host executor + bounded Railway CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.services.external_execution_access import ExternalExecutionAccess, assess_external_execution_access
from app.services.external_execution_runner import (
    BoundedRailwayInvestigation,
    analyze_investigation_for_contract,
    format_execution_summary_contract,
    run_bounded_railway_repo_investigation,
)


@dataclass
class PipelineContext:
    """Inputs for :func:`run_pipeline`."""

    db: Session
    user_id: str
    collected: dict[str, Any]
    on_progress: Callable[[dict[str, Any]], None] | None = None


def check_access(ctx: PipelineContext) -> dict[str, Any]:
    """Non-secret signals only — whether this worker can attempt Railway/repo checks."""
    acc: ExternalExecutionAccess = assess_external_execution_access(ctx.db, ctx.user_id)
    return {
        "dev_workspace_registered": acc.dev_workspace_registered,
        "host_executor_enabled": acc.host_executor_enabled,
        "railway_access_available": acc.railway_access_available,
        "railway_token_present": acc.railway_token_present,
        "railway_cli_on_path": acc.railway_cli_on_path,
    }


def run_cli_checks(ctx: PipelineContext) -> BoundedRailwayInvestigation:
    """Bounded subprocess / CLI investigation (same as historical runner entrypoint)."""
    return run_bounded_railway_repo_investigation(
        ctx.db,
        ctx.user_id,
        ctx.collected,
        on_progress=ctx.on_progress,
        progress_user_id=ctx.user_id,
    )


def analyze_results(inv: BoundedRailwayInvestigation) -> dict[str, Any]:
    """Structured facts derived from captured CLI output (no LLM)."""
    return analyze_investigation_for_contract(inv)


def summarize(inv: BoundedRailwayInvestigation, analysis: dict[str, Any]) -> str:
    """User-visible summary block — checkmarks reflect real outcomes only."""
    _ = analysis
    return format_execution_summary_contract(inv)


def run_pipeline(ctx: PipelineContext) -> dict[str, Any]:
    """
    Ordered stages: access snapshot → CLI investigation → analysis → summary markdown.

    Returns dict suitable for merging into chat replies and Mission Control–oriented UIs.
    """
    access = check_access(ctx)
    investigation = run_cli_checks(ctx)
    analysis = analyze_results(investigation)
    summary_md = summarize(investigation, analysis)
    return {
        "access": access,
        "investigation": investigation,
        "analysis": analysis,
        "summary_markdown": summary_md,
    }


__all__ = [
    "PipelineContext",
    "analyze_results",
    "check_access",
    "run_cli_checks",
    "run_pipeline",
    "summarize",
]
