# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.privacy.pii_patterns import find_pii_matches
from app.privacy.pii_result import PIIMatch


def detect_pii(text: str) -> list[PIIMatch]:
    """Return deterministic, non-overlapping PII spans for ``text``."""
    return find_pii_matches(text)
