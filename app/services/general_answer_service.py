"""Direct LLM answers for normal questions (Nexa is not only static fallbacks)."""

from __future__ import annotations

import json
from typing import Any

from app.services.memory_preferences import (
    general_answer_memory_formatting_block,
    maybe_apply_single_plain_cursor_block,
)
from app.services.owner_identity_faq import try_canned_owner_identity_faq
from app.services.response_formatter import finalize_user_facing_text
from app.services.safe_llm_gateway import safe_llm_text_call

GENERAL_ANSWER_SYSTEM_PROMPT = """
You are Nexa.

Nexa is a multi-agent command center, but you can also answer normal questions directly.

Rules:
- Answer the user's actual question.
- Do not force everything into planning, agents, or onboarding.
- Only say that live web / real-time data is not available in this chat when the user clearly needs
  current news, today's prices, live market data, real-time logs, or a "latest update" as of now.
  For conceptual, historical, or general "how/what/why" questions, answer directly without that disclaimer.
- The product may fetch **public** http(s) pages in other routes. If the user only asked a normal
  question here, do not claim you just fetched a page unless a tool did. Never tell the user you
  “cannot browse” or “can’t open websites” when the server has public URL reading enabled; say you
  do not have that fetch in *this* reply, or that they can paste a public URL in chat with
  @research or “check <url>”.
- When live data would help but is unavailable, say that once clearly, then be useful: structure, background, frameworks, and what official sources to check.
- Be concise but helpful; use short sections or bullets when it helps.
- Do not pretend to browse or access private or logged-in content without the user providing credentials
  through a supported, explicit flow.
- If the user is correcting a previous misunderstanding, acknowledge briefly and answer the corrected question.
- For people: do not infer gender or pronouns from names. Use soul.md / memory when the profile states pronouns; otherwise stay neutral (name, they) rather than defaulting to she.
""".strip()


def _general_answer_memory_block() -> str:
    try:
        from app.services.safe_llm_gateway import read_safe_system_memory_snapshot

        snapshot = read_safe_system_memory_snapshot()
    except Exception:  # noqa: BLE001
        return ""

    sm = (snapshot.soul or "").strip()
    mm = (snapshot.memory or "").strip()
    if not sm and not mm:
        return ""

    return (
        "Persistent Nexa context:\n\n"
        f"<soul.md>\n{sm}\n</soul.md>\n\n"
        f"<memory.md>\n{mm}\n</memory.md>"
    )


def _slim_conversation_context(snapshot: dict[str, Any] | None) -> str:
    if not snapshot or not isinstance(snapshot, dict):
        return ""
    slim: dict[str, Any] = {
        "active_topic": snapshot.get("active_topic"),
        "active_project": snapshot.get("active_project"),
        "last_intent": snapshot.get("last_intent"),
    }
    rm = snapshot.get("recent_messages")
    if isinstance(rm, list) and rm:
        slim["recent_messages_tail"] = rm[-4:]
    return json.dumps(slim, default=str)[:4000]


def answer_general_question(
    text: str,
    conversation_snapshot: dict | None = None,
    *,
    research_mode: bool = False,
) -> str:
    t = (text or "").strip()
    if not t:
        return fallback_general_answer("")

    c0 = try_canned_owner_identity_faq(t, user_preferences=None)
    if c0 is not None:
        return finalize_user_facing_text(c0, user_preferences=None)

    ctx = _slim_conversation_context(conversation_snapshot)
    user_request = t[:12_000]
    extra = None
    if ctx:
        extra = f"Context (for reference only, may be partial):\n{ctx}"

    memory_block = _general_answer_memory_block()
    system_prompt = GENERAL_ANSWER_SYSTEM_PROMPT
    if memory_block:
        system_prompt = f"{GENERAL_ANSWER_SYSTEM_PROMPT}\n\n{memory_block}"
    if research_mode:
        from app.services.structured_response_style import structured_style_guidance_for

        system_prompt = f"{system_prompt}\n\n{structured_style_guidance_for('research', 'public_web')}"
    system_prompt += general_answer_memory_formatting_block()

    try:
        from app.services.llm_usage_context import push_llm_action

        with push_llm_action(
            source="general_answer", action_type="chat_response", agent_key="nexa"
        ):
            result = safe_llm_text_call(
                system_prompt=system_prompt,
                user_request=user_request,
                extra_text=extra,
            )
        if result and result.strip():
            out = maybe_apply_single_plain_cursor_block(result.strip(), t)
            return finalize_user_facing_text(out[:10_000], user_preferences=None)[:10_000]
    except Exception:  # noqa: BLE001
        pass

    return fallback_general_answer(t)


def fallback_general_answer(text: str) -> str:
    _ = text
    return (
        "I can help with that, but I need a little more detail or a working LLM connection.\n\n"
        "Ask it as a direct question, or tell me whether you want an explanation, comparison, plan, or action."
    )
