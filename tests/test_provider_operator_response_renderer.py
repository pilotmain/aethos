# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deploy_context.errors import ProviderAuthenticationError
from app.rendering.operator_responses import render_operator_deploy_error, render_provider_action_success


def test_render_auth_missing_ux() -> None:
    text = render_operator_deploy_error(
        ProviderAuthenticationError("x", details={"provider": "vercel"})
    )
    assert "vercel login" in text.lower()
    assert "aethos providers scan" in text.lower()


def test_render_action_success() -> None:
    text = render_provider_action_success(
        intent="provider_redeploy",
        project_id="acme",
        provider="vercel",
        repo_path="/tmp/acme",
        result={"success": True, "action": "redeploy_latest", "url": "https://x.vercel.app"},
    )
    assert "acme" in text
    assert "https://x.vercel.app" in text
