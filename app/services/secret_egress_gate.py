# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Heuristic detection of secret-like material (never exhaustive — defense in depth).
"""

from __future__ import annotations

import re

# Short patterns — avoid noisy false positives on normal prose where practical.
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_GITHUB_PAT = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_OPENAI_SK = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_STRIPE_KEY = re.compile(r"\bsk_live_[0-9a-zA-Z]{20,}\b")
_PEM_BLOCK = re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----")
_ENV_SECRET = re.compile(
    r"(?i)\b(API_KEY|SECRET_KEY|ACCESS_KEY|AUTH_TOKEN|BEARER|PASSWORD)\s*=\s*[^\s][^\n]{4,}"
)


def looks_like_secret_material(text: str) -> bool:
    """Return True if text likely contains credentials or key material."""
    if not (text or "").strip():
        return False
    s = text[:500_000]
    if _PEM_BLOCK.search(s):
        return True
    if _AWS_KEY.search(s) or _GITHUB_PAT.search(s) or _SLACK_TOKEN.search(s):
        return True
    if _OPENAI_SK.search(s) or _STRIPE_KEY.search(s):
        return True
    if _ENV_SECRET.search(s):
        return True
    low = s.lower()
    if ".ssh/id_rsa" in low or ".ssh/id_ed25519" in low:
        return True
    if "session=" in low and "cookie" in low and len(s) < 50_000:
        # coarse: long random session cookies often appear with session=
        if re.search(r"session=[a-zA-Z0-9._-]{16,}", s, re.I):
            return True
    return False


def assert_safe_for_external_send(
    body: str,
    *,
    allow_when: bool,
    detail: str = "",
) -> None:
    """If body may contain secrets, require explicit allow (e.g. paired permissions)."""
    if allow_when:
        return
    if looks_like_secret_material(body):
        raise ValueError(
            (detail or "Outbound content may include secrets or credentials.") + " "
            "Explicit approval is required before sending off this machine."
        )
