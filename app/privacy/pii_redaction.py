# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from collections.abc import Sequence

from app.privacy.pii_detection import detect_pii
from app.privacy.pii_result import PIIMatch


def redact_text(text: str, matches: Sequence[PIIMatch] | None = None) -> str:
    """Replace spans with ``[REDACTED:<category>]`` (end-to-start so indices stay valid)."""
    mlist = list(matches) if matches is not None else detect_pii(text)
    if not mlist:
        return text
    out = text
    for m in sorted(mlist, key=lambda x: -x.start):
        token = f"[REDACTED:{m.category}]"
        out = out[: m.start] + token + out[m.end :]
    return out
