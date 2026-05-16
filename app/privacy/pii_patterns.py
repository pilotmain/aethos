# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Compiled regex patterns for deterministic PII detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.privacy.pii_result import PIIMatch


@dataclass(frozen=True, slots=True)
class _Pattern:
    category: str
    severity: str
    regex: re.Pattern[str]


def _preview(raw: str, *, category: str) -> str:
    s = raw.strip()
    if not s:
        return "[REDACTED]"
    if len(s) <= 6:
        tail = "…" if len(s) > 2 else ""
        return f"{s[0]}…{tail}"
    return f"{s[:4]}…redacted"


_SEVERITY: dict[str, int] = {"high": 3, "medium": 2, "low": 1}

# Order is not used for precedence; overlap resolution uses severity + span length.
_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        "private_key",
        "high",
        re.compile(
            r"-----BEGIN [A-Z0-9 -]*PRIVATE KEY-----[A-Za-z0-9+/=\s\r\n]+?-----END [A-Z0-9 -]*PRIVATE KEY-----",
            re.MULTILINE | re.DOTALL,
        ),
    ),
    _Pattern(
        "auth_header",
        "high",
        re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9._\-~+/]+=*"),
    ),
    _Pattern(
        "database_url_with_secret",
        "high",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql)://[^\s'\"]+:[^\s'\"]+@[^\s'\"]+",
        ),
    ),
    _Pattern("ssn", "high", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    _Pattern(
        "credit_card",
        "high",
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    ),
    _Pattern("api_key", "high", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    _Pattern("api_key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    _Pattern("api_key", "high", re.compile(r"\bgh[pous]_[A-Za-z0-9]{20,}\b")),
    _Pattern("api_key", "high", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    _Pattern(
        "secret_token",
        "high",
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    ),
    _Pattern(
        "email",
        "medium",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    _Pattern(
        "phone",
        "medium",
        re.compile(
            r"\b(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b",
        ),
    ),
    _Pattern(
        "address",
        "low",
        re.compile(
            r"\b\d{1,5}\s+[NSEW]?\s*[A-Za-z0-9.\s]{2,40}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b",
            re.IGNORECASE,
        ),
    ),
    _Pattern(
        "password_like",
        "low",
        re.compile(
            r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*"
            r"(?:\"[^\"\n]{3,200}\"|'[^'\n]{3,200}'|[^\s#;,\"']{3,200})",
        ),
    ),
)


def _select_non_overlapping(matches: list[PIIMatch]) -> list[PIIMatch]:
    ordered = sorted(
        matches,
        key=lambda m: (
            -_SEVERITY.get(m.severity, 0),
            m.start,
            -(m.end - m.start),
        ),
    )
    chosen: list[PIIMatch] = []
    for m in ordered:
        if any(not (m.end <= o.start or m.start >= o.end) for o in chosen):
            continue
        chosen.append(m)
    return sorted(chosen, key=lambda x: (x.start, x.end, x.category))


def find_pii_matches(text: str) -> list[PIIMatch]:
    if not text:
        return []
    raw: list[PIIMatch] = []
    for p in _PATTERNS:
        for m in p.regex.finditer(text):
            span = text[m.start() : m.end()]
            raw.append(
                PIIMatch(
                    category=p.category,
                    severity=p.severity,
                    start=m.start(),
                    end=m.end(),
                    redacted_preview=_preview(span, category=p.category),
                    confidence=1.0,
                )
            )
    return _select_non_overlapping(raw)
