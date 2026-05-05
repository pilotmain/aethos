"""Phase 21 — CLI settings helpers."""

from __future__ import annotations

from aethos_cli.__main__ import merge_settings_payload


def test_merge_settings_payload_updates_privacy_and_ui() -> None:
    base = {
        "privacy_mode": "standard",
        "ui_preferences": {"theme": "dark", "auto_refresh": True},
    }
    out = merge_settings_payload(base, ["privacy_mode=strict", "theme=light", "auto_refresh=false"])
    assert out["privacy_mode"] == "strict"
    assert out["ui_preferences"]["theme"] == "light"
    assert out["ui_preferences"]["auto_refresh"] is False
