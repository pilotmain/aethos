# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.gateway.provider_intents import parse_provider_operation_intent


def test_nl_logs_parses() -> None:
    p = parse_provider_operation_intent("show logs for invoicepilot")
    assert p and p["intent"] == "provider_logs"
