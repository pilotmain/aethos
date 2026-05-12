# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator mode — CLI locally does not require duplicate prefs (session-level)."""

from __future__ import annotations

from app.services.external_execution_session import parse_followup_preferences


def test_cli_locally_sets_auth_and_probe_once() -> None:
    out = parse_followup_preferences("CLI locally", {})
    assert out.get("auth_method") == "local_cli"
    assert out.get("permission_to_probe") is True
