# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pro memory ranking — rerank semantic hits using query overlap + recency hints."""

from __future__ import annotations

import re
from typing import Any


def _score(entry: dict[str, Any], query: str) -> float:
    base = float(entry.get("_similarity") or 0.0)
    q_tokens = set(re.findall(r"[a-z0-9]{3,}", query.lower()))
    blob = f"{entry.get('title', '')} {entry.get('preview', '')}".lower()
    overlap = sum(1 for t in q_tokens if t in blob)
    return base + overlap * 0.03


def rank_memory(entries: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Re-order ``entries`` for prompts. ``context`` may include ``query`` (user / retrieval query).

    Attach ``_similarity`` on entries beforehand when cosine scores are available for smoother blending.
    """
    q = str((context or {}).get("query") or "")
    if not entries:
        return []
    return sorted(entries, key=lambda e: _score(e, q), reverse=True)


__all__ = ["rank_memory"]
