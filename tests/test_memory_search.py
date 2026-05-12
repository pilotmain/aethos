# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 39 — memory pseudo-semantic search."""

from __future__ import annotations

from app.services.memory.embedding import cosine_similarity, embed_text
from app.services.memory.memory_index import MemoryIndex
from app.services.memory.memory_store import MemoryStore


def test_embed_text_deterministic() -> None:
    a = embed_text("hello")
    b = embed_text("hello")
    assert len(a) == len(b) == 64
    assert all(isinstance(x, float) for x in a)
    assert max(abs(a[i] - b[i]) for i in range(64)) < 1e-9


def test_cosine_similarity_range() -> None:
    a = embed_text("cat")
    b = embed_text("cat")
    sim = cosine_similarity(a, b)
    assert 0.99 < sim <= 1.0


def test_semantic_search_returns_list() -> None:
    store = MemoryStore()
    # avoid fs if store needs user dir - use real store with temp if needed
    idx = MemoryIndex(store=store)
    out = idx.semantic_search("u_test", "query", limit=3)
    assert isinstance(out, list)
