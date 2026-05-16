# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.deploy_context.context_history import persist_deployment_identity
from app.providers.actions import vercel_actions


def test_persist_deployment_identity_roundtrip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        rec = persist_deployment_identity(
            linked_project_id="acme",
            provider="vercel",
            provider_project="acme",
            deployment_id="d1",
            environment="production",
            repo_path=str(tmp_path / "r"),
            url="https://example.vercel.app",
        )
        assert rec.get("deployment_id") == "d1"
        from app.runtime.runtime_state import load_runtime_state

        st = load_runtime_state()
        identities = st.get("deployment_identities") or {}
        assert identities.get("acme", {}).get("url") == "https://example.vercel.app"
    finally:
        get_settings.cache_clear()


def test_vercel_list_deployments_uses_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx: dict[str, Any] = {
        "project_id": "p",
        "repo_path": str(Path.cwd()),
    }

    def _fake_fetch(_ctx: dict[str, Any], *, environment: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return [{"uid": "dep-1", "state": "READY", "url": "https://x.vercel.app"}], {
            "returncode": 0,
            "failure_category": "ok",
            "summary_lines": [],
            "preview": "",
        }

    monkeypatch.setattr(vercel_actions, "_fetch_deployment_rows", _fake_fetch)
    monkeypatch.setattr(vercel_actions, "record_operator_provider_action", lambda *_a, **_k: None)
    out = vercel_actions.list_deployments(ctx, environment="production")
    assert out.get("success") is True
    extra = out.get("extra") or {}
    assert len(extra.get("deployments") or []) == 1
