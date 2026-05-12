# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Route authority: classify inbound turns → gateway intents (missions, tools, chat).

Concrete routing logic will delegate to mission parser, onboarding, and channel adapters."""

from __future__ import annotations

from typing import Any


def classify_turn(text: str, *, channel: str) -> dict[str, Any]:
    """
    Deterministic first-pass classification for gateway admission.

    Returns a small descriptor; full routing happens in ``NexaGateway``.
    """
    raw = (text or "").strip()
    return {
        "channel": (channel or "web").strip().lower()[:32],
        "empty": len(raw) == 0,
        "length": len(raw),
    }
