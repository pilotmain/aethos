"""Lightweight pseudo-embeddings for ranking — optional Ollama ``/api/embeddings`` (Phase 42)."""

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


def _embed_ollama_http(text: str, *, dim: int) -> list[float] | None:
    from app.core.config import get_settings

    s = get_settings()
    base = (s.nexa_ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
    model = (s.nexa_ollama_default_model or "llama3").strip()
    try:
        import httpx  # noqa: PLC0415

        r = httpx.post(
            f"{base}/api/embeddings",
            json={"model": model, "prompt": (text or "")[:8000]},
            timeout=45.0,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        emb = data.get("embedding")
        if not isinstance(emb, list) or not emb:
            return None
        vec = [float(x) for x in emb]
        if dim > 0 and len(vec) > dim:
            vec = vec[:dim]
        elif dim > 0 and len(vec) < dim:
            vec.extend([0.0] * (dim - len(vec)))
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
    except Exception:
        return None


def embed_text_primary(text: str, *, dim: int = 64) -> list[float]:
    """
    Prefer Ollama embeddings when ``NEXA_OLLAMA_EMBEDDINGS_ENABLED`` and Ollama are on;
    fall back to deterministic pseudo-vectors.
    """
    from app.core.config import get_settings

    s = get_settings()
    if getattr(s, "nexa_ollama_embeddings_enabled", False) and getattr(s, "nexa_ollama_enabled", False):
        v = _embed_ollama_http(text, dim=dim)
        if v:
            return v
    return embed_text(text, dim=dim)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return min(1.0, max(-1.0, dot / (na * nb)))


__all__ = ["cosine_similarity", "embed_text", "embed_text_primary"]
