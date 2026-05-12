# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""operator_execution_actions — gates and helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.operator_execution_actions import (
    operator_action_gates,
    operator_diag_gate,
    retry_with_backoff,
)


def test_operator_action_gates_require_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_actions.get_settings",
        lambda: SimpleNamespace(
            nexa_operator_mode=True,
            nexa_host_executor_enabled=False,
            nexa_operator_allow_write=True,
            nexa_operator_allow_deploy=False,
        ),
    )
    ok, reason = operator_action_gates(require_write=True, require_deploy=False)
    assert ok is False
    assert reason == "host_executor_disabled"


def test_operator_diag_gate_only_operator_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_actions.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True),
    )
    assert operator_diag_gate() == (True, "")


def test_retry_with_backoff_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.operator_execution_actions.time.sleep", lambda _s: None)
    n = {"i": 0}

    def fn():
        n["i"] += 1
        return {"ok": n["i"] >= 2}

    last, log = retry_with_backoff(fn, max_attempts=3, delays_sec=(0, 0, 0))
    assert last == {"ok": True}
    assert "Succeeded" in "\n".join(log)
