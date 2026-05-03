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


def build_memory_context_for_turn(
    user_id: str,
    text: str,
    *,
    max_items: int = 5,
    purpose: str = "chat",
) -> dict[str, Any]:
    """
    Build structured memory for one user turn.

    ``purpose`` is informational for logs/future filtering (e.g. ``gateway_structured``, ``chat``).

    Returns a dict suitable for merging into :attr:`~app.services.gateway.context.GatewayContext.memory`
    and for setting ``memory_context`` on behavior Context.
    """
    _ = purpose  # reserved for future retrieval tuning
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
    tags: list[str] = []
    for w in _keyword_tokens(raw):
        if w not in tags:
            tags.append(w)
    for e in items[:max_items]:
        tl = str(e.get("title") or "").lower()
        for token in re.findall(r"[a-z][a-z0-9]{2,}", tl):
            if token not in tags and len(tags) < 24:
                tags.append(token)

    out: dict[str, Any] = {
        "items": items[:max_items],
        "summary": summary,
        "used": used,
        "memory_context": memory_context,
        "tags": tags[:24],
        "purpose": purpose,
    }

    # Optional structured workspace files (markdown/json under data/nexa_workspace/).
    from app.core.config import get_settings as _gs_workspace

    _s = _gs_workspace()
    if getattr(_s, "nexa_workspace_intelligence_enabled", False):
        from app.services.workspace_intelligence.bundle import select_workspace_context_pack as _wi_pack

        _pack = _wi_pack(raw)
        if _pack is not None and (_pack.summary or "").strip():
            _addon = (_pack.summary or "")[:3800]
            _mc = ((out.get("memory_context") or "").strip() + "\n\n[Workspace intelligence]\n" + _addon).strip()
            out["memory_context"] = _mc[:4500]
            out["workspace_intel"] = {
                "used": True,
                "files": list(_pack.files),
                "skills": list(_pack.skills),
                "token_estimate": int(_pack.token_estimate),
            }
        else:
            out["workspace_intel"] = {"used": False}

    return out


__all__ = ["build_memory_context_for_turn"]
