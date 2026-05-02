"""Per-turn memory bundle for gateway / compose paths (Phase 52)."""

from __future__ import annotations

import re
from typing import Any

from app.services.memory.memory_index import MemoryIndex

_FOLLOWUP_CUES = re.compile(
    r"(?i)\b("
    r"given my project|based on what you remember|from memory|my project setup|"
    r"my stack|what you (?:know|stored)|remember (?:that|we)|as (?:you )?mentioned"
    r")\b"
)

# Words likely to improve recall when matching stored notes (short queries).
_TECH_PULL = re.compile(
    r"(?i)\b(eks|k8s|kubernetes|mongo(db)?|postgres|mysql|redis|oidc|oauth|jwt|spring|docker|"
    r"terraform|helm|aws|gcp|azure|istio|vault|kafka|nginx)\b"
)


def _looks_like_memory_followup(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if _FOLLOWUP_CUES.search(t):
        return True
    if len(t) < 400 and _TECH_PULL.search(t):
        return True
    return False


def _keyword_tokens(text: str) -> list[str]:
    out: list[str] = []
    for m in _TECH_PULL.finditer(text or ""):
        w = (m.group(0) or "").strip().lower()
        if len(w) >= 3 and w not in out:
            out.append(w)
    return out[:12]


def build_memory_context_for_turn(user_id: str, text: str, *, max_items: int = 5) -> dict[str, Any]:
    """
    Build structured memory for one user turn.

    Returns a dict suitable for merging into :attr:`~app.services.gateway.context.GatewayContext.memory`
    and for setting ``memory_context`` on behavior Context.
    """
    uid = (user_id or "").strip()
    raw = (text or "").strip()
    idx = MemoryIndex()
    recent = idx.recent_for_prompt(uid, max_chars=2800)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    follow = _looks_like_memory_followup(raw)
    semantic_blob = ""

    if follow and raw:
        sem = idx.semantic_search(uid, raw[:2000], limit=max_items)
        for e in sem:
            eid = str(e.get("id") or "")
            if eid and eid not in seen:
                seen.add(eid)
                items.append(e)
        if sem:
            lines = []
            for e in sem[:max_items]:
                title = str(e.get("title") or "").strip()
                pv = str(e.get("preview") or "").strip()[:360]
                lines.append(f"- {title}\n  {pv}".strip())
            semantic_blob = "Most relevant notes for this question:\n" + "\n".join(lines)

    if not items:
        for kw in _keyword_tokens(raw):
            for e in idx.search_keywords(uid, kw):
                eid = str(e.get("id") or "")
                if eid and eid not in seen:
                    seen.add(eid)
                    items.append(e)
                if len(items) >= max_items:
                    break
            if len(items) >= max_items:
                break

    parts: list[str] = []
    if recent:
        parts.append("Recent stored notes:\n" + recent)
    if semantic_blob:
        parts.append(semantic_blob)

    summary = "\n\n".join(parts).strip()
    memory_context = summary[:4500] if summary else recent[:4500]

    used = bool(memory_context.strip())
    return {
        "items": items[:max_items],
        "summary": summary,
        "used": used,
        "memory_context": memory_context,
    }


__all__ = ["build_memory_context_for_turn"]
