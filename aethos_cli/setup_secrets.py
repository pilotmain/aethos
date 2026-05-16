# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Secret redaction and safe display for setup flows (Phase 4 Step 4)."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|api_key|bearer|authorization)",
    re.IGNORECASE,
)


def mask_secret(value: str | None, *, visible: int = 4) -> str:
    """Redact a secret for display — never echo full tokens after entry."""
    if not value:
        return "(not set)"
    v = str(value).strip()
    if len(v) <= visible * 2:
        return "•" * len(v)
    return f"{v[:visible]}…{v[-visible:]}"


def redact_env_for_display(env: dict[str, Any]) -> dict[str, str]:
    """Return env dict safe for logs/summaries."""
    out: dict[str, str] = {}
    for k, v in env.items():
        if not isinstance(k, str):
            continue
        sv = str(v) if v is not None else ""
        if _SECRET_KEY_RE.search(k):
            out[k] = mask_secret(sv)
        else:
            out[k] = sv
    return out


def safe_token_confirm_display(token: str) -> str:
    """One-line masked confirmation after token entry."""
    return f"Token saved ({mask_secret(token, visible=6)}) — full value not shown again."
