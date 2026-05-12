# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 16 — channel adapters funnel inbound work through ``route_inbound`` / gateway only."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_DIR = ROOT / "app" / "services" / "channels"


def test_channel_adapters_use_route_inbound_not_gateway_import() -> None:
    """Concrete channels must call ``route_inbound``; only ``router.py`` may reference ``NexaGateway``."""
    for path in sorted(CHANNEL_DIR.glob("*.py")):
        if path.name in ("__init__.py", "base.py", "router.py"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "route_inbound" in text, f"{path.name} must import route_inbound"
        assert "NexaGateway" not in text, f"{path.name} must not import NexaGateway directly"


def test_router_imports_gateway() -> None:
    router = CHANNEL_DIR / "router.py"
    assert "NexaGateway" in router.read_text(encoding="utf-8")
