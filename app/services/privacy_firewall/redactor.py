# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Redact known patterns from text prior to external transmission."""

# DO NOT MODIFY WITHOUT SECURITY REVIEW — redaction behavior.

from __future__ import annotations

import re
from typing import Any

_RE_BEARER = re.compile(r"(?i)\b(bearer\s+)([a-z0-9._~-]{20,})\b")
_RE_EMAIL = re.compile(r"[\w.-]+@[\w.-]+")
_RE_SK_OPENAI = re.compile(r"sk-[A-Za-z0-9]+")


def redact_sensitive_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Serialize payload to string, redact PII/key-shaped segments, return single redacted blob."""
    text = str(payload)
    text = _RE_EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _RE_SK_OPENAI.sub("[REDACTED_KEY]", text)
    return {"redacted": text}


def redact_common_secrets(text: str) -> tuple[str, int]:
    """
    Return redacted text and count of substitutions (best-effort).
    """
    raw = text or ""
    n = 0

    def _sub_bearer(m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return f"{m.group(1)}[REDACTED]"

    out = _RE_BEARER.sub(_sub_bearer, raw)
    return out, n
