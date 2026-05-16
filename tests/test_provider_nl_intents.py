# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.gateway.provider_intents import parse_provider_operation_intent


def test_parse_restart_invoicepilot() -> None:
    p = parse_provider_operation_intent("restart invoicepilot")
    assert p is not None
    assert p["intent"] == "provider_restart"
    assert p.get("project_phrase") == "invoicepilot"


def test_parse_redeploy_with_fix() -> None:
    p = parse_provider_operation_intent("fix and redeploy invoicepilot")
    assert p is not None
    assert p["intent"] == "provider_redeploy"


def test_parse_check_production() -> None:
    p = parse_provider_operation_intent("check invoicepilot production")
    assert p is not None
    assert p["intent"] == "provider_status"
    assert p.get("environment") == "production"


def test_parse_show_logs() -> None:
    p = parse_provider_operation_intent("show invoicepilot logs")
    assert p is not None
    assert p["intent"] == "provider_logs"


def test_parse_scan_providers() -> None:
    p = parse_provider_operation_intent("scan providers")
    assert p is not None
    assert p["intent"] == "provider_scan_providers"


def test_parse_unrelated_returns_none() -> None:
    assert parse_provider_operation_intent("hello there") is None
