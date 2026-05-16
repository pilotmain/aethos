# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.privacy.privacy_events import PrivacyEventType, emit_privacy_event
from app.privacy.privacy_policy import block_egress_on_pii, current_privacy_mode, observe_only
from app.privacy.privacy_modes import PrivacyMode

if TYPE_CHECKING:
    from app.core.config import Settings


class EgressBlocked(Exception):
    """Raised when ``block`` mode refuses an outbound boundary because PII is present."""

    def __init__(self, message: str, *, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.payload: dict[str, Any] = dict(payload or {})


def evaluate_egress(
    settings: Settings,
    boundary: str,
    *,
    pii_categories: Sequence[str] | None = None,
) -> tuple[bool, str]:
    """
    Decide whether an egress boundary may proceed.

    - ``off``: allow, no audit noise.
    - ``observe``: allow, emit audit.
    - ``redact``: allow (caller should redact separately).
    - ``block`` + guard + PII categories: deny.
    - ``local_only``: informational allow here; routing is handled elsewhere.
    """
    cats = [str(c).strip() for c in (pii_categories or []) if str(c).strip()]
    mode = current_privacy_mode(settings)
    if mode == PrivacyMode.OFF:
        return True, "off"
    if observe_only(settings):
        emit_privacy_event(
            PrivacyEventType.EGRESS_ALLOWED,
            details={"boundary": boundary, "mode": mode.value, "pii_categories": cats},
        )
        return True, "observe"
    if mode == PrivacyMode.REDACT:
        emit_privacy_event(
            PrivacyEventType.EGRESS_ALLOWED,
            details={"boundary": boundary, "mode": mode.value, "note": "caller_redacts"},
        )
        return True, "redact_mode"
    if block_egress_on_pii(settings) and cats:
        emit_privacy_event(
            PrivacyEventType.EGRESS_BLOCKED,
            details={"boundary": boundary, "pii_categories": cats},
        )
        return False, "blocked_pii_present"
    emit_privacy_event(
        PrivacyEventType.EGRESS_ALLOWED,
        details={"boundary": boundary, "mode": mode.value, "pii_categories": cats},
    )
    return True, "allowed"
