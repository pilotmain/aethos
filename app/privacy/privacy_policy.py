# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import TYPE_CHECKING

from app.privacy.privacy_modes import PrivacyMode

if TYPE_CHECKING:
    from app.core.config import Settings


def current_privacy_mode(settings: Settings) -> PrivacyMode:
    raw = (getattr(settings, "aethos_privacy_mode", "observe") or "observe").strip().lower()
    try:
        return PrivacyMode(raw)
    except ValueError:
        return PrivacyMode.OBSERVE


def observe_only(settings: Settings) -> bool:
    return current_privacy_mode(settings) == PrivacyMode.OBSERVE


def mutations_allowed(settings: Settings) -> bool:
    return current_privacy_mode(settings) in (
        PrivacyMode.REDACT,
        PrivacyMode.BLOCK,
        PrivacyMode.LOCAL_ONLY,
    )


def block_egress_on_pii(settings: Settings) -> bool:
    return (
        current_privacy_mode(settings) == PrivacyMode.BLOCK
        and bool(getattr(settings, "aethos_external_egress_guard_enabled", False))
    )
