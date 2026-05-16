# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import TYPE_CHECKING

from app.privacy.privacy_modes import PrivacyMode

if TYPE_CHECKING:
    from app.core.config import Settings


def should_redact_for_external_model(settings: Settings) -> bool:
    """True when outbound model payloads should be redacted before provider calls."""
    if not getattr(settings, "aethos_pii_redaction_enabled", False):
        return False
    mode = (getattr(settings, "aethos_privacy_mode", "observe") or "observe").strip().lower()
    return mode in (PrivacyMode.REDACT.value, PrivacyMode.BLOCK.value, PrivacyMode.LOCAL_ONLY.value)


def should_redact_for_telemetry(settings: Settings) -> bool:
    """Telemetry / structured logs: redact when global redaction flag is on."""
    return bool(getattr(settings, "aethos_pii_redaction_enabled", False))
