# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_operator_surface import (
    build_operator_startup_lines,
    sanitize_operator_log_line,
    should_show_advanced_endpoints,
)


def test_runtime_branding_no_nexa_in_startup_lines() -> None:
    text = "\n".join(build_operator_startup_lines())
    for legacy in ("Nexa", "Dashboard", "OpenClaw", "ClawHub", "OpenHub"):
        assert legacy not in text


def test_sanitize_operator_log_line() -> None:
    assert "AethOS" in sanitize_operator_log_line("Nexa: starting")
    assert "Nexa" not in sanitize_operator_log_line("Nexa: starting")


def test_advanced_endpoints_hidden_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AETHOS_SHOW_ADVANCED_ENDPOINTS", raising=False)
    assert should_show_advanced_endpoints() is False
