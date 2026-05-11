"""Conversation memory enrichment for LLM context — recent turns + lightweight contradiction hints."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings
from app.models.conversation_context import ConversationContext

_CORRECTION_CUES = re.compile(
    r"(?i)\b(actually|wrong|incorrect|not right|mistake|misunderstood|"
    r"i didn\'t mean|no that\'s not|that\'s false|contradict)\b"
)
_DONE_UNDONE = re.compile(
    r"(?i)\b(not done|still broken|didn\'t work|failed again|isn\'t fixed)\b"
)


def _recent_raw(ctx: ConversationContext) -> list[dict[str, Any]]:
    try:
        raw = json.loads(ctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return raw if isinstance(raw, list) else []


def detect_contradiction_hint(user_text: str, recent_messages: list[dict[str, Any]]) -> str | None:
    """Surface a short hint when the latest user message may contradict recent assistant claims."""
    u = (user_text or "").strip()
    if not u or len(u) < 4:
        return None
    if _CORRECTION_CUES.search(u):
        return (
            "The user may be correcting something from earlier in the thread — "
            "double-check facts before repeating confident claims."
        )
    last_asst = ""
    for m in reversed(recent_messages):
        if not isinstance(m, dict):
            continue
        if (m.get("role") or "").strip() == "assistant":
            last_asst = str(m.get("text") or "")
            break
    if last_asst and _DONE_UNDONE.search(u):
        low_a = last_asst.lower()
        if any(x in low_a for x in ("done", "complete", "fixed", "success", "finished")):
            return (
                "Possible mismatch: a prior reply sounded complete, but the user signals it is not resolved."
            )
    return None


def enrich_conversation_snapshot_for_llm(
    snap: dict[str, Any],
    ctx: ConversationContext,
    user_text: str,
) -> dict[str, Any]:
    """
    Expand ``recent_messages`` to the last N turns (configurable) and optionally prefix ``summary``
    with a contradiction/consistency hint for the LLM path.
    """
    s = get_settings()
    if not bool(getattr(s, "nexa_conversation_memory_enabled", True)):
        return snap
    n = max(5, min(20, int(getattr(s, "nexa_conversation_memory_turns", 10))))
    raw_list = _recent_raw(ctx)
    recent = raw_list[-n:] if raw_list else []

    out = dict(snap)
    out["recent_messages"] = recent

    hint = detect_contradiction_hint(user_text, recent)
    if hint:
        summ = (out.get("summary") or "").strip()
        prefix = f"⚠️ **Consistency note:** {hint}\n\n"
        out["summary"] = (prefix + summ).strip()[:8000]
        out["contradiction_hint"] = hint

    return out


__all__ = [
    "detect_contradiction_hint",
    "enrich_conversation_snapshot_for_llm",
]
