"""Optional Pro memory reranking (``nexa_ext.memory_intel`` + license)."""

from __future__ import annotations

from typing import Any

from app.services.extensions import get_extension
from app.services.licensing.features import FEATURE_MEMORY_INTEL, has_pro_feature


def apply_pro_memory_ranking(user_id: str, query: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not entries:
        return entries
    mod = get_extension("memory_intel")
    if mod is None or not has_pro_feature(FEATURE_MEMORY_INTEL):
        return entries
    rank = getattr(mod, "rank_memory", None)
    if not callable(rank):
        return entries
    try:
        out = rank(list(entries), {"query": query, "user_id": user_id})
        return list(out) if out else entries
    except Exception:
        return entries


__all__ = ["apply_pro_memory_ranking"]
