# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_operator_surface import sanitize_operator_log_line


def test_sanitize_nexa_settings_logger() -> None:
    line = "INFO [nexa.settings] nexa_llm_provider=auto"
    out = sanitize_operator_log_line(line)
    assert "nexa" not in out.lower()
    assert "active_provider" in out
    assert "aethos.settings" in out


def test_sanitize_nexa_config_banner() -> None:
    assert "AethOS" in sanitize_operator_log_line("=== Nexa config (api) ===")
