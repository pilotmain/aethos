# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Redact provider CLI output before logs / API surfaces (Phase 2 privacy)."""

from __future__ import annotations

from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text


def redact_cli_output(text: str, *, max_out: int = 4000) -> str:
    raw = (text or "")[:50_000]
    matches = detect_pii(raw)
    return redact_text(raw, matches)[:max_out]
