# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conservative token estimation (Phase 38)."""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def estimate_payload_tokens(payload: dict[str, Any]) -> int:
    try:
        s = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(payload)
    return estimate_tokens(s)
