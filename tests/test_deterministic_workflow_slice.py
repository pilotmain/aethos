# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Light deterministic multi-step runner (NexaForge slice)."""

from __future__ import annotations

from app.services.execution_loop import run_deterministic_steps


def test_run_deterministic_steps_noop_chain() -> None:
    out = run_deterministic_steps(
        [
            {"id": "a", "tool": "noop"},
            {"id": "b", "tool": "echo", "args": {"message": "hi"}},
        ],
        context={},
    )
    assert out["status"] == "complete"
    assert out["results"]["a"]["ok"] is True
    assert out["results"]["b"]["message"] == "hi"


def test_run_deterministic_steps_deploy_needs_approval() -> None:
    out = run_deterministic_steps(
        [
            {"id": "prep", "tool": "noop"},
            {"id": "d1", "tool": "vercel_deploy", "args": {}},
        ],
        context={},
    )
    assert out["status"] == "approval_needed"
    assert out["token"] == "d1"
    assert out["results"]["prep"]["ok"] is True


def test_run_deterministic_steps_deploy_when_allowed() -> None:
    out = run_deterministic_steps(
        [{"id": "d1", "tool": "railway_deploy"}],
        context={"operator_deploy_allowed": True},
    )
    assert out["status"] == "complete"
    assert out["results"]["d1"]["ok"] is True


def test_run_deterministic_steps_unknown_tool() -> None:
    out = run_deterministic_steps([{"id": "u", "tool": "not_a_real_tool"}], context={})
    assert out["status"] == "complete"
    assert out["results"]["u"]["ok"] is False
