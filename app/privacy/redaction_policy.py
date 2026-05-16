# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.config import Settings
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode


def should_redact_for_external_model(settings: Settings) -> bool:
    """True when outbound model payloads should be redacted before cloud provider calls."""
    mode = current_privacy_mode(settings)
    if mode == PrivacyMode.REDACT:
        return True
    if bool(getattr(settings, "aethos_pii_redaction_enabled", False)):
        return mode in (PrivacyMode.BLOCK, PrivacyMode.LOCAL_ONLY)
    return False


def should_redact_for_telemetry(settings: Settings) -> bool:
    """Telemetry / structured logs: redact when global redaction flag is on."""
    return bool(getattr(settings, "aethos_pii_redaction_enabled", False))
