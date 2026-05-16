# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text


def test_redact_text_replaces_spans() -> None:
    text = "mail user@example.com done"
    m = detect_pii(text)
    out = redact_text(text, m)
    assert "user@example.com" not in out
    assert "[REDACTED:email]" in out
