# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

# Mirror web formatOperationalError logic for unit tests without TS runner.


def format_operational_error(message: str) -> str:
    m = message.strip()
    if m.startswith("500") or m.startswith("503"):
        return "AethOS runtime hit an internal error while loading this panel. Other panels may still be available."
    if "Cannot reach API" in m:
        return "AethOS runtime connection is not available yet. The API may still be starting, or connection settings may need repair."
    if "unknown provider" in m.lower():
        return "This provider is not available in the current AethOS runtime configuration."
    return m


def test_operator_error_copy() -> None:
    assert "internal error" in format_operational_error("500: boom")
    assert "not available yet" in format_operational_error("Cannot reach API")
    assert "provider" in format_operational_error("unknown provider x").lower()
