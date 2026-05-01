"""Phase 22 — NEXA_LOCAL_FIRST prefers local_stub when tool maps to remote."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.tools.registry import TOOLS, ToolDescriptor, get_provider_for_tool, register_tool


def test_local_first_forces_stub(monkeypatch) -> None:
    register_tool(
        ToolDescriptor(
            name="phase22_remote_probe",
            description="test",
            risk_level="model",
            provider="openai",
            pii_policy="firewall_required",
        )
    )
    monkeypatch.setenv("NEXA_LOCAL_FIRST", "true")
    get_settings.cache_clear()
    try:
        assert get_provider_for_tool("phase22_remote_probe") == "local_stub"
    finally:
        monkeypatch.delenv("NEXA_LOCAL_FIRST", raising=False)
        get_settings.cache_clear()
        TOOLS.pop("phase22_remote_probe", None)
