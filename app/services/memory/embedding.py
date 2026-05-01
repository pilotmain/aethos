"""Lightweight pseudo-embeddings for ranking — swap for Ollama ``/api/embeddings`` when desired."""

from __future__ import annotations

import hashlib
import math
from typing import Sequence


def embed_text(text: str, *, dim: int = 64) -> list[float]:
    """
    Deterministic embedding (no network). Replace with real embeddings for semantic recall.

    Uses SHA-256 chunks mapped to ``dim`` dimensions (L2-normalized).
    """
    if dim < 8:
        dim = 8
    vec = [0.0] * dim
    raw = (text or "").encode("utf-8", errors="replace")
    for i in range(0, len(raw), 32):
        h = hashlib.sha256(raw[i : i + 64]).digest()
        for j in range(dim):
            vec[j] += float(h[j % len(h)]) / 255.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return min(1.0, max(-1.0, dot / (na * nb)))


__all__ = ["cosine_similarity", "embed_text"]
