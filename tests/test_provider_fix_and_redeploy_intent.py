# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.gateway.provider_intents import parse_provider_operation_intent


def test_fix_and_redeploy_intent_payload() -> None:
    p = parse_provider_operation_intent("fix and redeploy invoicepilot")
    assert p is not None
    assert p["intent"] == "fix_and_redeploy"
    assert p.get("requires_workspace") is True
    assert p.get("requires_verification") is True


def test_fix_project_and_deploy() -> None:
    p = parse_provider_operation_intent("fix invoicepilot and deploy")
    assert p and p["intent"] == "fix_and_redeploy"


def test_plain_redeploy_not_fix_intent() -> None:
    p = parse_provider_operation_intent("redeploy invoicepilot")
    assert p and p["intent"] == "provider_redeploy"
