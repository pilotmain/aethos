# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.deployments.deployment_artifacts import artifacts_from_plan


def test_artifacts_from_deploy_steps() -> None:
    plan = {
        "steps": [
            {
                "step_id": "s1",
                "type": "deploy",
                "status": "completed",
                "outputs": [{"ts": "t", "tool": "deploy"}],
                "result": {"tool": "deploy", "ok": True},
            }
        ]
    }
    arts = artifacts_from_plan(plan)
    assert any(a.get("kind") == "deploy" for a in arts)
