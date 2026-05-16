# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PIIMatch:
    """Structured PII span (indices are Python slice bounds on the original string)."""

    category: str
    severity: str
    start: int
    end: int
    redacted_preview: str
    confidence: float

    def as_public_dict(self) -> dict[str, str | int | float]:
        return {
            "category": self.category,
            "severity": self.severity,
            "start": self.start,
            "end": self.end,
            "redacted_preview": self.redacted_preview,
            "confidence": self.confidence,
        }
