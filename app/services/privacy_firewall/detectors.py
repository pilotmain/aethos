"""Heuristic detectors for secrets, PII, and policy triggers (expand over time)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DetectionHit:
    kind: str
    span_label: str


_RE_OPENAI_SK = re.compile(r"sk-[A-Za-z0-9]{20,}")
_RE_EMAIL = re.compile(r"[\w.-]+@[\w.-]+")
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_RE_SK_AWS = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")


def detect_sensitive_data(text: str) -> dict[str, list[str]]:
    """Coarse secret / PII markers for worker outbound gate."""
    raw = text or ""
    secrets: list[str] = []
    pii: list[str] = []

    if _RE_OPENAI_SK.search(raw):
        secrets.append("openai_key")

    if _RE_EMAIL.search(raw):
        pii.append("email")

    if _RE_SSN.search(raw):
        pii.append("ssn")

    return {
        "secrets": secrets,
        "pii": pii,
    }


def detect_sensitive_segments(text: str) -> list[DetectionHit]:
    """Return coarse hits for auditing — not a complete DLP suite."""
    raw = text or ""
    hits: list[DetectionHit] = []
    if _RE_JWT.search(raw):
        hits.append(DetectionHit(kind="token_like", span_label="jwt_shape"))
    if _RE_SK_AWS.search(raw):
        hits.append(DetectionHit(kind="aws_access_key_shape", span_label="aws_key"))
    return hits
