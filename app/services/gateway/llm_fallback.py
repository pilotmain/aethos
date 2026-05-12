"""Gateway NL: LLM interpretation for imperative text that missed structured handlers.

This path is **advisory only** — it does not execute shell, write files, or open URLs from model
output. Host mutations stay on the host-executor / approval flows.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext

# First word / leading phrase signals a task-style line (not a pure Q&A greeting).
_LEADING_QUESTION = re.compile(
    r"^(what|who|why|when|where|which|whose)\b",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|yep|nope)\b[!.?\s]*$",
    re.IGNORECASE,
)


def looks_like_unrouted_command(text: str) -> bool:
    """
    Heuristic: short imperative / tooling line likely meant as a command, not open chat.

    Kept conservative so normal conversation still flows through :meth:`NexaGateway.handle_full_chat`.
    """
    raw = (text or "").strip()
    if not raw or len(raw) < 10:
        return False
    if len(raw) > 1_200:
        return False
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 6:
        return False
    first = lines[0].strip()
    low = first.lower()
    if _GREETING.match(low):
        return False
    if _LEADING_QUESTION.match(low) and not re.match(
        r"^(how\s+(do|can|should|would)\s+i|how\s+to)\b",
        low,
        re.IGNORECASE,
    ):
        return False

    verbs = (
        r"^(?:please\s+)?(?:"
        r"install|uninstall|add|remove|delete|run|start|stop|restart|build|compile|test|lint|"
        r"deploy|push|pull|commit|merge|rebase|clone|open|show|list|print|cat|grep|find|cd|mkdir|"
        r"touch|mv|cp|chmod|npm|npx|yarn|pnpm|pip|poetry|uv|cargo|go\s+run|docker|kubectl|git|"
        r"create|make|generate|scaffold|refactor|fix|update|upgrade|downgrade|import|export|"
        r"execute|exec|kill|ps|curl|wget|ssh|scp|rsync|terraform|vercel|railway"
        r")\b"
    )
    if re.match(verbs, low, re.IGNORECASE):
        return True
    # Capitalized multi-word line (e.g. product names) — skip pure "How are you" style small talk.
    if re.match(r"^[A-Z][a-zA-Z0-9_-]{2,40}\s+\w+", first):
        if low.startswith("how"):
            return bool(
                re.match(r"^(how\s+(do|can|should|would)\s+i|how\s+to)\b", low, re.IGNORECASE)
            )
        if not low.startswith(("what", "who", "why", "when", "where", "which", "whose")):
            return True
    return False


_FALLBACK_SYSTEM = """
You are AethOS (an AI execution system with gateway routing, optional host executor jobs, skills,
sub-agents, and workspace projects).

The user's line did **not** match a built-in shortcut handler. Your job is to interpret what they
want and respond helpfully.

Rules:
- Be concise; use short sections or numbered steps.
- Do **not** claim you already ran shell commands, edited files, deployed, or opened browsers.
  Nothing in this path executes code — describe what the user (or AethOS via approved flows) would do.
- Prefer mapping the request to **existing AethOS surfaces** when plausible, for example:
  - Natural-language **Development …** / **build a … app** / **deploy** patterns when they fit.
  - **Host executor** / approval flows for local file or command work (user may need to confirm).
  - **@subagent** or **create a … agent** for delegated multi-step work.
  - **/subagent list**, **/key set …**, Mission Control / workspace registration when blocked.
- If the ask is unsafe, ambiguous, or needs credentials, say what is missing and offer a safe next step.
- Never ask for or repeat secrets; respect [TOKEN]/[SECRET] style redactions if present.
""".strip()


def _slim_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot or not isinstance(snapshot, dict):
        return ""
    slim: dict[str, Any] = {
        "active_topic": snapshot.get("active_topic"),
        "active_project": snapshot.get("active_project"),
        "last_intent": snapshot.get("last_intent"),
    }
    rm = snapshot.get("recent_messages")
    if isinstance(rm, list) and rm:
        slim["recent_messages_tail"] = rm[-3:]
    return json.dumps(slim, default=str)[:3500]


def try_gateway_llm_fallback_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Optional LLM interpretation before :meth:`~app.services.gateway.runtime.NexaGateway.handle_full_chat`.

    Returns ``None`` when disabled, ineligible, or LLM is off (fall through to normal chat path).
    """
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None
    settings = get_settings()
    if not bool(getattr(settings, "use_real_llm", False)):
        return None
    if not looks_like_unrouted_command(raw):
        return None

    ws = (getattr(settings, "nexa_workspace_root", None) or "").strip() or "(workspace not configured)"

    from app.services.conversation_context_service import build_context_snapshot, get_or_create_context
    from app.services.intent_classifier import get_intent
    from app.services.safe_llm_gateway import safe_llm_text_call

    _ws_id = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
    cctx = get_or_create_context(db, uid, web_session_id=_ws_id)
    snap = build_context_snapshot(cctx, db)
    mem_sum = None
    if isinstance(gctx.memory, dict):
        mem_sum = str(gctx.memory.get("summary") or "").strip() or None
    routed = get_intent(raw, conversation_snapshot=snap if isinstance(snap, dict) else None, memory_summary=mem_sum)
    if routed != "general_chat":
        return None

    extra = _slim_snapshot(snap if isinstance(snap, dict) else None)
    extra = (
        f"Channel: {gctx.channel}\n"
        f"Configured workspace root (operator): {ws}\n\n"
        f"Conversation hints:\n{extra}"
        if extra
        else f"Channel: {gctx.channel}\nConfigured workspace root (operator): {ws}"
    )

    tg_id = gctx.extras.get("telegram_user_id")
    telegram_user_id: int | None
    if isinstance(tg_id, int):
        telegram_user_id = tg_id
    elif isinstance(tg_id, str) and tg_id.strip().isdigit():
        telegram_user_id = int(tg_id.strip())
    else:
        telegram_user_id = None

    try:
        body = safe_llm_text_call(
            system_prompt=_FALLBACK_SYSTEM,
            user_request=raw[:8000],
            extra_text=extra,
            db=db,
            telegram_user_id=telegram_user_id,
        )
    except Exception:
        return None
    body = (body or "").strip()
    if not body:
        return None

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(
            body,
            source="gateway_llm_fallback",
            user_text=raw,
        ),
        "intent": "llm_fallback_command",
    }


__all__ = ["looks_like_unrouted_command", "try_gateway_llm_fallback_turn"]
