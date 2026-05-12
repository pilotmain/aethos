# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Commit + push path is gated."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.operator_execution_actions import commit_and_push


def test_commit_push_blocked_without_write_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_execution_actions.get_settings",
        lambda: SimpleNamespace(
            nexa_operator_mode=True,
            nexa_host_executor_enabled=True,
            nexa_operator_allow_write=False,
            nexa_operator_allow_deploy=False,
        ),
    )
    r = commit_and_push("/tmp", "msg")
    assert r.get("ok") is False
    assert r.get("error") == "operator_write_disabled"
