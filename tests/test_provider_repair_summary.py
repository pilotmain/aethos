# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.rendering.repair_summary import render_fix_and_redeploy_blocked, render_fix_and_redeploy_success


def test_success_summary() -> None:
    text = render_fix_and_redeploy_success(
        project_id="invoicepilot",
        repo_path="/tmp/ip",
        diagnosis={"diagnosis": "Build failed"},
        actions_taken=["Ran npm install", "Redeployed"],
        deploy_result={"url": "https://x.vercel.app"},
    )
    assert "Invoicepilot" in text
    assert "https://x.vercel.app" in text


def test_blocked_summary() -> None:
    text = render_fix_and_redeploy_blocked(
        project_id="invoicepilot",
        repo_path="/tmp/ip",
        reason="verification failed",
    )
    assert "did **not** redeploy" in text
