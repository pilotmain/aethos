# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Observability NL must not be mistaken for host read-file intents."""

from __future__ import annotations

from app.services.host_executor_intent import parse_read_intent
from app.services.observability.runtime_store import parse_observability_intent


def test_show_me_system_status_is_observability_not_read() -> None:
    assert parse_observability_intent("show me system status") == "full"
    assert parse_read_intent("show me system status") is None


def test_show_alerts_and_metrics_kinds() -> None:
    assert parse_observability_intent("show me alerts") == "alerts"
    assert parse_observability_intent("display metrics") == "metrics"


def test_health_check_phrases() -> None:
    assert parse_observability_intent("health check") == "full"
    assert parse_observability_intent("is everything ok?") == "full"


def test_show_readme_still_reads_file() -> None:
    assert parse_observability_intent("show README.md") is None
    r = parse_read_intent("show README.md")
    assert r is not None
    assert r.get("intent") == "read_file"
