# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from enum import Enum
from typing import Any


class PrivacyEventType(str, Enum):
    PII_DETECTED = "pii_detected"
    PII_REDACTED = "pii_redacted"
    EGRESS_ALLOWED = "egress_allowed"
    EGRESS_BLOCKED = "egress_blocked"
    LOCAL_ROUTE_SELECTED = "local_route_selected"
    SENSITIVE_ARTIFACT_CREATED = "sensitive_artifact_created"
    PRIVACY_POLICY_CHANGED = "privacy_policy_changed"


def emit_privacy_event(
    event: PrivacyEventType,
    *,
    channel: str = "privacy",
    details: dict[str, Any] | None = None,
) -> None:
    """Persist a privacy audit row (sanitized ``details`` only)."""
    from app.privacy.privacy_audit import append_privacy_line

    safe = dict(details or {})
    for k in list(safe.keys()):
        lk = str(k).lower()
        if any(x in lk for x in ("secret", "password", "token", "authorization", "raw", "payload")):
            safe.pop(k, None)
    append_privacy_line(
        "privacy.log",
        {"event": event.value, "channel": channel, "details": safe},
    )
    if event == PrivacyEventType.PII_DETECTED:
        append_privacy_line(
            "pii.log",
            {
                "event": event.value,
                "categories": list(safe.get("categories") or []),
                "count": int(safe.get("count") or 0),
            },
        )
    if event in (PrivacyEventType.EGRESS_ALLOWED, PrivacyEventType.EGRESS_BLOCKED):
        append_privacy_line(
            "egress.log",
            {"event": event.value, "boundary": str(safe.get("boundary") or ""), "allowed": event == PrivacyEventType.EGRESS_ALLOWED},
        )
