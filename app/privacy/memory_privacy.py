# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent memory write path — PII scan + optional redaction + privacy metadata."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode


def prepare_memory_write(
    body_md: str,
    title: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """
    Return ``(body_md, title, privacy_meta)`` for persistence.

    Redacts title/body when privacy mode is ``redact`` or ``AETHOS_PII_REDACTION_ENABLED`` is true
    and PII categories are detected.
    """
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    blob = f"{title}\n{body_md}"[:200_000]
    matches = detect_pii(blob)
    cats = sorted({m.category for m in matches})
    redacted = False
    out_b = body_md
    out_t = title
    if cats and (
        mode == PrivacyMode.REDACT or bool(getattr(s, "aethos_pii_redaction_enabled", False))
    ):
        out_b = redact_text(body_md)
        out_t = redact_text(title)
        redacted = out_b != body_md or out_t != title
    meta = {
        "scanned": True,
        "pii_categories": cats,
        "redacted": redacted,
        "local_only_required": mode == PrivacyMode.LOCAL_ONLY,
        "privacy_mode": mode.value,
    }
    return out_b, out_t, meta
