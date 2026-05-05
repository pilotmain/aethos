"""Lightweight retrieval helpers for agent prompts (recent memory text)."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.memory.embedding import cosine_similarity, embed_text_primary
from app.services.memory.memory_store import MemoryStore
from app.services.memory.pro_intel import apply_pro_memory_ranking


class MemoryIndex:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    def recent_for_prompt(self, user_id: str, *, max_chars: int = 3500) -> str:
        """Plain-text blob safe to prepend to model payloads (truncated)."""
        entries = self.store.list_entries(user_id, limit=80)
        if not entries:
            return ""
        chunks: list[str] = []
        n = 0
        for e in reversed(entries):
            tid = str(e.get("id") or "")
            title = str(e.get("title") or "")
            preview = str(e.get("preview") or "")
            blob = f"- [{e.get('type', 'note')}] {title}\n{preview}".strip()
            if n + len(blob) > max_chars:
                break
            chunks.append(blob)
            n += len(blob) + 1
        return "\n\n".join(reversed(chunks))

    def search_keywords(self, user_id: str, *words: str) -> list[dict[str, Any]]:
        w = [re.escape(x.lower()) for x in words if (x or "").strip()]
        if not w:
            return []
        pat = re.compile("|".join(f"({x})" for x in w))
        hits: list[dict[str, Any]] = []
        for e in self.store.list_entries(user_id, limit=500):
            blob = json.dumps(e, default=str)
            if pat.search(blob.lower()):
                hits.append(e)
        return hits

    def semantic_search(self, user_id: str, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        """
        Rank entries by cosine similarity of deterministic pseudo-embeddings (Phase 39).

        Replace ``embed_text`` with Ollama embeddings for full semantic recall.
        """
        q = (query or "").strip()
        if not q:
            return []
        qv = embed_text_primary(q)
        scored: list[tuple[float, dict[str, Any]]] = []
        for e in self.store.list_entries(user_id, limit=500):
            blob = f"{e.get('title', '')}\n{e.get('preview', '')}"
            sv = embed_text_primary(blob[:8000])
            score = cosine_similarity(qv, sv)
            scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        trimmed = scored[:limit]
        enriched: list[dict[str, Any]] = []
        for sc, e in trimmed:
            row = dict(e)
            row["_similarity"] = float(sc)
            enriched.append(row)
        return apply_pro_memory_ranking(user_id, q, enriched)

    def active_recall(self, user_id: str, query: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Chunked recall (Phase 15); respects ``nexa_active_memory_enabled`` inside the service."""
        from app.services.memory.active_memory import ActiveMemoryService

        return ActiveMemoryService(self.store).recall(user_id, query, limit=limit)


__all__ = ["MemoryIndex"]
