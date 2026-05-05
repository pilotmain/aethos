"""Chunked semantic recall over filesystem memory (Phase 15a)."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.config import get_settings
from app.services.memory.chunking import chunk_text
from app.services.memory.embedding import cosine_similarity, embed_text_primary
from app.services.memory.memory_store import MemoryStore
from app.services.memory.pro_intel import apply_pro_memory_ranking

logger = logging.getLogger(__name__)


def _read_entry_body(store: MemoryStore, user_id: str, entry_id: str) -> str:
    tid = (entry_id or "").strip()
    if not tid:
        return ""
    fp = store.user_dir(user_id) / f"{tid}.md"
    if not fp.is_file():
        return ""
    text = fp.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


class ActiveMemoryService:
    """Chunk documents, embed query + chunks, return top-K cosine matches."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    def _expand_to_chunks(self, user_id: str) -> list[dict[str, Any]]:
        s = get_settings()
        max_entries = min(max(int(getattr(s, "nexa_active_memory_max_entries_scan", 200) or 200), 1), 500)
        chunk_chars = min(max(int(getattr(s, "nexa_active_memory_chunk_chars", 800) or 800), 128), 12000)
        overlap = max(0, min(int(getattr(s, "nexa_active_memory_chunk_overlap", 100) or 100), chunk_chars // 2))

        entries = self.store.list_entries(user_id, limit=max_entries)
        chunks_out: list[dict[str, Any]] = []
        for e in entries:
            eid = str(e.get("id") or "")
            title = str(e.get("title") or "").strip()
            preview = str(e.get("preview") or "").strip()
            body = _read_entry_body(self.store, user_id, eid)
            blob = f"{title}\n{preview}\n{body}".strip()
            if not blob:
                continue
            parts = chunk_text(blob, max_chars=chunk_chars, overlap=overlap)
            if not parts:
                parts = [blob[:chunk_chars]]
            for idx, part in enumerate(parts):
                chunks_out.append(
                    {
                        "entry_id": eid,
                        "chunk_index": idx,
                        "title": title[:500],
                        "text": part,
                        "type": str(e.get("type") or "note"),
                        "ts": str(e.get("ts") or ""),
                    }
                )
        return chunks_out

    def recall(
        self,
        user_id: str,
        query: str,
        *,
        limit: int | None = None,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        uid = (user_id or "").strip()
        q = (query or "").strip()
        if not uid or not q:
            return []

        s = get_settings()
        if not bool(getattr(s, "nexa_active_memory_enabled", False)):
            return []

        limit = limit if limit is not None else int(getattr(s, "nexa_active_memory_top_k", 8) or 8)
        limit = min(max(limit, 1), 48)
        min_score = (
            float(getattr(s, "nexa_active_memory_min_score", 0.12))
            if min_score is None
            else float(min_score)
        )

        t0 = time.perf_counter()
        qv = embed_text_primary(q[:8000])
        chunks = self._expand_to_chunks(uid)
        scored: list[tuple[float, dict[str, Any]]] = []
        for ch in chunks:
            blob = f"{ch.get('title', '')}\n{ch.get('text', '')}"
            sv = embed_text_primary(blob[:8000])
            score = cosine_similarity(qv, sv)
            row = dict(ch)
            row["_similarity"] = float(score)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        filtered = [(sc, r) for sc, r in scored if sc >= min_score][:limit]
        enriched = [r for _, r in filtered]
        enriched = apply_pro_memory_ranking(uid, q, enriched)

        ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "active_memory recall user=%s chunks=%s hits=%s ms=%.1f",
            uid[:24],
            len(chunks),
            len(enriched),
            ms,
            extra={
                "nexa_event": "active_memory_recall",
                "hit_count": len(enriched),
                "latency_ms": round(ms, 2),
            },
        )
        return enriched


def format_active_memory_block(hits: list[dict[str, Any]], *, max_chars: int | None = None) -> str:
    """Human-readable block for prompt injection."""
    if not hits:
        return ""
    s = get_settings()
    cap = max_chars if max_chars is not None else int(getattr(s, "nexa_active_memory_max_chars", 4000) or 4000)
    lines: list[str] = ["Active memory (chunk recall):"]
    n = 0
    for h in hits:
        title = str(h.get("title") or "").strip()
        tid = str(h.get("entry_id") or "")
        score = float(h.get("_similarity") or 0.0)
        body = str(h.get("text") or "").strip()[:1200]
        line = f"- [{score:.3f}] {title or tid}\n  {body}".strip()
        if n + len(line) > cap:
            break
        lines.append(line)
        n += len(line) + 1
    blob = "\n".join(lines).strip()
    return blob[:cap]


__all__ = ["ActiveMemoryService", "format_active_memory_block"]
