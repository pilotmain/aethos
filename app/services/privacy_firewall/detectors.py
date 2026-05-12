# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Heuristic detectors for secrets, PII, and policy triggers (expand over time)."""

# DO NOT MODIFY WITHOUT SECURITY REVIEW — detector heuristics affect outbound safety.

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

ConfidenceLevel = Literal["high", "medium", "low"]

_RE_OPENAI_SK = re.compile(r"\bsk-[A-Za-z0-9]{10,}\b")
_RE_EMAIL = re.compile(r"[\w.-]+@[\w.-]+")
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_RE_CARD_DASHED = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b")
_RE_PHONE_LOOSE = re.compile(r"\b\+?\d{10,15}\b")

_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_RE_SK_AWS = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
_RE_GITHUB_PAT = re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")
_RE_GITHUB_PAT_FINE = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")
_RE_NPM_TOKEN = re.compile(r"\bnpm_[A-Za-z0-9]{36,}\b")
_RE_PEM_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
# Assignment-shaped secrets (`.env` lines or embedded in repr/logs).
_RE_DOTENV_ASSIGNMENT = re.compile(
    r"\b[A-Z][A-Z0-9_]{3,}=[^\s\r\n,\"']{12,}\b"
)
_RE_SLACK_BOT = re.compile(r"\bxoxb-[0-9]{8,}-[0-9]{8,}-[A-Za-z0-9]{10,}\b")
_RE_API_KEY_SYM = re.compile(r"\bapi_key_[A-Za-z0-9_]{8,}\b")

# Egress — phone only when visibly formatted like +CC-xxx-xxx-xxxx
_RE_PHONE_EGRESS = re.compile(r"\+\d{1,3}[-.\s]\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")

# Candidate chunks that might be API-like secrets (egress high-entropy path)
_RE_LONG_TOKEN = re.compile(r"[A-Za-z0-9+/=_-]{24,}")


@dataclass
class DetectionHit:
    kind: str
    span_label: str


def _luhn_ok(digits: str) -> bool:
    n = [int(c) for c in digits if c.isdigit()]
    if len(n) < 13 or len(n) > 19:
        return False
    checksum = 0
    parity = len(n) % 2
    for i, d in enumerate(n):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _high_entropy_secret(tok: str) -> bool:
    """Long token with mixed classes — excludes pure hex (hashes) and digit-only strings."""
    if len(tok) < 33:
        return False
    if tok.isdigit():
        return False
    has_upper = any(c.isupper() for c in tok)
    has_lower = any(c.islower() for c in tok)
    has_digit = any(c.isdigit() for c in tok)
    if not (has_upper and has_lower and has_digit):
        return False
    # Drop likely hex digests (64-char SHA-256 etc.)
    hex_chars = set("0123456789abcdefABCDEF")
    if len(tok) >= 32 and all(c in hex_chars for c in tok):
        return False
    return True


def _ingress_credit_card_hit(raw: str) -> bool:
    return bool(_RE_CARD_DASHED.search(raw))


def _egress_credit_card_hit(raw: str) -> bool:
    """Credit-card-shaped runs only when Luhn validates."""
    for m in _RE_CARD_DASHED.finditer(raw):
        digits = "".join(c for c in m.group(0) if c.isdigit())
        if len(digits) == 16 and _luhn_ok(digits):
            return True
    for m in re.finditer(r"\b\d{13,19}\b", raw):
        digits = m.group(0)
        if _luhn_ok(digits):
            return True
    return False


def _any_high_entropy_token(raw: str) -> bool:
    skip_if_present = []
    j = _RE_JWT.search(raw)
    if j:
        skip_if_present.append(j.group(0))
    for m in _RE_LONG_TOKEN.finditer(raw):
        tok = m.group(0)
        if len(tok) < 33:
            continue
        if any(tok in s or s in tok for s in skip_if_present):
            continue
        if _RE_OPENAI_SK.search(tok) or _RE_SK_AWS.search(tok):
            continue
        if _high_entropy_secret(tok):
            return True
    return False


def _aggregate_confidence(
    *,
    high_secret: bool,
    medium_secret: bool,
    pii: bool,
) -> ConfidenceLevel:
    if high_secret:
        return "high"
    if medium_secret:
        return "medium"
    if pii:
        return "low"
    return "low"


def _detect_ingress(raw: str) -> dict[str, Any]:
    """Strict inbound / serialization scan — broad secret + PII coverage."""
    secrets_h = False
    secrets_m = False

    if _RE_OPENAI_SK.search(raw):
        secrets_h = True
    if _RE_JWT.search(raw):
        secrets_h = True
    if _RE_SK_AWS.search(raw):
        secrets_h = True
    if _RE_GITHUB_PAT.search(raw):
        secrets_h = True
    if _RE_GITHUB_PAT_FINE.search(raw):
        secrets_h = True
    if _RE_NPM_TOKEN.search(raw):
        secrets_h = True
    if _RE_PEM_PRIVATE_KEY.search(raw):
        secrets_h = True
    if _RE_DOTENV_ASSIGNMENT.search(raw):
        secrets_h = True
    if _RE_SLACK_BOT.search(raw):
        secrets_h = True
    if _RE_API_KEY_SYM.search(raw):
        secrets_h = True

    kinds: list[str] = []
    if secrets_h:
        if _RE_OPENAI_SK.search(raw):
            kinds.append("openai_key")
        if _RE_JWT.search(raw):
            kinds.append("jwt")
        if _RE_SK_AWS.search(raw):
            kinds.append("aws_access_key")
        if _RE_GITHUB_PAT.search(raw):
            kinds.append("github_pat")
        if _RE_GITHUB_PAT_FINE.search(raw):
            kinds.append("github_fine_grained_pat")
        if _RE_NPM_TOKEN.search(raw):
            kinds.append("npm_token")
        if _RE_PEM_PRIVATE_KEY.search(raw):
            kinds.append("pem_private_key")
        if _RE_DOTENV_ASSIGNMENT.search(raw):
            kinds.append("dotenv_assignment")
        if _RE_SLACK_BOT.search(raw):
            kinds.append("slack_bot_token")
        if _RE_API_KEY_SYM.search(raw):
            kinds.append("api_key_symbol")

    pii: list[str] = []
    if _RE_EMAIL.search(raw):
        pii.append("email")
    if _RE_SSN.search(raw):
        pii.append("ssn")
    if _ingress_credit_card_hit(raw):
        pii.append("credit_card")
    if _RE_PHONE_LOOSE.search(raw):
        pii.append("phone")

    # Ingress does not use generic high-entropy (avoid blocking benign payloads).

    conf = _aggregate_confidence(high_secret=secrets_h, medium_secret=secrets_m, pii=bool(pii))

    out_secrets = sorted(set(kinds))
    return {
        "secrets": out_secrets,
        "pii": sorted(set(pii)),
        "confidence": conf,
    }


def _detect_egress(raw: str) -> dict[str, Any]:
    """Post-provider scan — high-precision; fewer false positives."""
    kinds_h: list[str] = []
    kinds_m: list[str] = []

    if _RE_OPENAI_SK.search(raw):
        kinds_h.append("openai_key")
    if _RE_GITHUB_PAT.search(raw):
        kinds_h.append("github_pat")
    if _RE_GITHUB_PAT_FINE.search(raw):
        kinds_h.append("github_fine_grained_pat")
    if _RE_NPM_TOKEN.search(raw):
        kinds_h.append("npm_token")
    if _RE_PEM_PRIVATE_KEY.search(raw):
        kinds_h.append("pem_private_key")
    if _RE_DOTENV_ASSIGNMENT.search(raw):
        kinds_h.append("dotenv_assignment")
    if _RE_SLACK_BOT.search(raw):
        kinds_h.append("slack_bot_token")
    if _RE_API_KEY_SYM.search(raw):
        kinds_h.append("api_key_symbol")
    if _RE_SK_AWS.search(raw):
        kinds_h.append("aws_access_key")

    if _RE_JWT.search(raw):
        kinds_m.append("jwt")

    if _any_high_entropy_token(raw):
        kinds_m.append("high_entropy_token")

    secrets_h = bool(kinds_h)
    secrets_m = bool(kinds_m)

    pii: list[str] = []
    if _RE_EMAIL.search(raw):
        pii.append("email")
    if _RE_SSN.search(raw):
        pii.append("ssn")
    if _egress_credit_card_hit(raw):
        pii.append("credit_card")
    if _RE_PHONE_EGRESS.search(raw):
        pii.append("phone")

    conf = _aggregate_confidence(high_secret=secrets_h, medium_secret=secrets_m, pii=bool(pii))

    merged = sorted(set(kinds_h + kinds_m))
    return {
        "secrets": merged,
        "pii": sorted(set(pii)),
        "confidence": conf,
    }


def detect_sensitive_data(text: str, mode: str = "ingress") -> dict[str, Any]:
    """
    Return coarse secret / PII markers plus an aggregate confidence tier.

    - ``ingress`` — strict (outbound payload gate): classic patterns, no generic entropy.
    - ``egress`` — relaxed (post-provider output): prefix secrets + entropy tiering;
      PII rules tightened (phone / card).
    """
    raw = text or ""
    m = (mode or "ingress").strip().lower()
    if m == "egress":
        return _detect_egress(raw)
    return _detect_ingress(raw)


def detect_sensitive_segments(text: str) -> list[DetectionHit]:
    """Return coarse hits for auditing — not a complete DLP suite."""
    raw = text or ""
    hits: list[DetectionHit] = []
    if _RE_JWT.search(raw):
        hits.append(DetectionHit(kind="token_like", span_label="jwt_shape"))
    if _RE_SK_AWS.search(raw):
        hits.append(DetectionHit(kind="aws_access_key_shape", span_label="aws_key"))
    return hits
