"""Rolling per-chat conversation state (topic, last agent, short recent turns)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.services.safe_llm_gateway import sanitize_text

logger = logging.getLogger(__name__)

MAX_RECENT_MESSAGES = 12

_RE_COMBINED_SWITCH = re.compile(
    r"(?is)(?:forget|ignore)\s+.+?\bnow\b,?\s*"
    r"(?:(?:(?:let'|let)\s*)?s|we)\s+(?:talk about|focus on)\s+(.+?)(?:[.!?\s]*)\s*$"
)
_RE_NOW_FOCUS = re.compile(
    r"(?is)(?:^|[.!?\n]\s*)"
    r"now,?\s*(?:(?:(?:let'|let)\s*)?s|we)\s+(?:talk about|focus on)\s+(.+?)(?:[.!?\s]*)\s*$"
)
_RE_SWITCH_TO = re.compile(
    r"(?is)\bswitch (?:the )?topic to\s+(.+?)(?:[.!?\s]*)\s*$"
)
_RE_STOP = re.compile(
    r"(?is)\bstop (?:talking about|focusing on)\s+([^\n.!?]+)"
)
_RE_STANDALONE_FORGET = re.compile(
    r"(?is)^\s*forget(?:\s+about)?\s+(.+?)(?:[.!?\s]*)\s*$"
)
_RE_STANDALONE_IGNORE = re.compile(
    r"(?is)^\s*ignore(?:\s+the)?\s+(.+?)(?:[.!?\s]*)\s*$"
)


def get_or_create_context(
    db: Session, user_id: str, *, web_session_id: str = "default"
) -> ConversationContext:
    uid = str(user_id)
    sid = (web_session_id or "default").strip()[:64] or "default"
    st = select(ConversationContext).where(
        ConversationContext.user_id == uid,
        ConversationContext.session_id == sid,
    ).limit(1)
    row = db.scalars(st).first()
    if row:
        return row
    title0 = "Main session" if sid == "default" else "New chat"
    row = ConversationContext(
        user_id=uid,
        session_id=sid,
        web_chat_title=title0,
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_conversation_contexts_for_user(
    db: Session, user_id: str, *, limit: int = 50
) -> list[ConversationContext]:
    uid = str(user_id)
    st = (
        select(ConversationContext)
        .where(ConversationContext.user_id == uid)
        .order_by(ConversationContext.updated_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    return list(db.scalars(st).all())


def get_conversation_context_by_session(
    db: Session, user_id: str, web_session_id: str
) -> ConversationContext | None:
    uid = str(user_id)
    sid = (web_session_id or "").strip()[:64] or "default"
    st = select(ConversationContext).where(
        ConversationContext.user_id == uid,
        ConversationContext.session_id == sid,
    ).limit(1)
    return db.scalars(st).first()


def _clear_web_chat_rollups(row: ConversationContext) -> None:
    """Reset stored chat turns and derived session state without removing the row."""
    row.recent_messages_json = "[]"
    row.summary = None
    row.active_topic = None
    row.last_intent = None
    row.last_agent_key = None
    row.active_agent = None
    row.last_decision_json = None
    row.last_suggested_actions_json = None
    row.next_action_pending_inject_json = None
    row.last_injected_action_json = None
    row.current_flow_state_json = None
    row.blocked_host_executor_json = None
    row.simulate_execute_pending_json = None
    row.sandbox_pending_plan_json = None
    row.pending_project_json = None
    row.manual_topic_override = False
    row.active_topic_confidence = 0.5
    row.last_topic_update_at = None


def delete_or_clear_web_session(
    db: Session, user_id: str, web_session_id: str
) -> None:
    """
    Remove a non-main web thread, or clear stored history for the main session (session_id ``default``).
    Raises LookupError when the session does not exist (non-default only).
    """
    uid = str(user_id)
    sid = (web_session_id or "").strip()[:64] or "default"
    if sid == "default":
        row = get_or_create_context(db, uid, web_session_id="default")
        _clear_web_chat_rollups(row)
        db.add(row)
        db.commit()
        return
    row = get_conversation_context_by_session(db, uid, sid)
    if row is None:
        raise LookupError("unknown session")
    db.delete(row)
    db.commit()


def create_new_web_conversation_context(
    db: Session, user_id: str, title: str = "New chat"
) -> ConversationContext:
    import uuid

    title_clean = (title or "New chat")[:80].strip() or "New chat"
    sid = f"w{uuid.uuid4().hex[:32]}"
    row = ConversationContext(
        user_id=str(user_id)[:64],
        session_id=sid[:64],
        web_chat_title=title_clean,
        recent_messages_json="[]",
        active_topic_confidence=0.5,
        manual_topic_override=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def detect_topic_override(user_message: str) -> tuple[str, str] | None:
    """
    (\"set\", new_topic) | (\"clear\", \"\") for explicit hard topic control; else None.
    Stops mixing sticky inferred topic with a user-directed switch.
    """
    t = (user_message or "").strip()
    if not t or t.startswith("/"):
        return None

    m = _RE_COMBINED_SWITCH.search(t)
    if m:
        topic = (m.group(1) or "").strip()
        if topic and len(topic) < 200:
            return ("set", topic)

    m = _RE_NOW_FOCUS.search(t)
    if m:
        topic = (m.group(1) or "").strip()
        if topic and len(topic) < 200:
            return ("set", topic)

    m = _RE_SWITCH_TO.search(t)
    if m:
        topic = (m.group(1) or "").strip()
        if topic and len(topic) < 200:
            return ("set", topic)

    m = _RE_STOP.search(t)
    if m and (m.group(1) or "").strip():
        return ("clear", "")

    if not re.search(
        r"(?is)(?:\bnow\b,?\s*)?(?:(?:(?:let'|let)\s*)?s|we)\s+(?:talk about|focus on)\b",
        t,
    ):
        m = _RE_STANDALONE_FORGET.match(t)
        if m and (m.group(1) or "").strip():
            return ("clear", "")

    if not re.search(
        r"(?is)(?:\bnow\b,?\s*)?(?:(?:(?:let'|let)\s*)?s|we)\s+(?:talk about|focus on)\b",
        t,
    ):
        m = _RE_STANDALONE_IGNORE.match(t)
        if m and (m.group(1) or "").strip():
            return ("clear", "")

    return None


def _mutate_topic_set(ctx: ConversationContext, new_topic: str) -> None:
    clean = (new_topic or "")[:255].strip() or "general"
    ctx.active_topic = clean
    ctx.active_topic_confidence = 1.0
    ctx.manual_topic_override = True
    ctx.last_topic_update_at = datetime.utcnow()
    safe = sanitize_text(new_topic[:500] if new_topic else "general")
    ctx.summary = f"User explicitly switched topic to: {safe}"[:10_000]
    ctx.recent_messages_json = "[]"
    ctx.last_suggested_actions_json = None
    ctx.next_action_pending_inject_json = None
    ctx.blocked_host_executor_json = None
    ctx.simulate_execute_pending_json = None
    ctx.sandbox_pending_plan_json = None


def set_manual_topic(db: Session, ctx: ConversationContext, new_topic: str) -> None:
    """Persist a manual topic (same semantics as a natural-language topic switch)."""
    _mutate_topic_set(ctx, new_topic)
    try:
        db.add(ctx)
        db.commit()
        db.refresh(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("set_manual_topic: %s", exc)
        db.rollback()


def _mutate_topic_clear(ctx: ConversationContext) -> None:
    ctx.active_topic = None
    ctx.active_topic_confidence = 0.5
    ctx.manual_topic_override = False
    ctx.last_topic_update_at = datetime.utcnow()
    ctx.summary = (
        "User asked to clear or stop the previous topic. Treat the next user message as fresh; "
        "do not assume the old subject unless they bring it back."
    )[:10_000]
    ctx.recent_messages_json = "[]"
    ctx.last_suggested_actions_json = None
    ctx.next_action_pending_inject_json = None
    ctx.blocked_host_executor_json = None
    ctx.simulate_execute_pending_json = None
    ctx.sandbox_pending_plan_json = None


def hard_clear_conversation_state(ctx: ConversationContext) -> None:
    """Clears topic, active agent, manual override, and rolling summary/turns (topic reset)."""
    ctx.active_topic = None
    ctx.active_project = None
    ctx.active_project_id = None
    ctx.active_agent = None
    ctx.last_intent = None
    ctx.last_agent_key = None
    ctx.active_topic_confidence = 0.5
    ctx.manual_topic_override = False
    ctx.last_topic_update_at = datetime.utcnow()
    ctx.summary = "Context cleared in Nexa. The next message starts fresh (no prior topic or agent handoff)."
    ctx.recent_messages_json = "[]"
    ctx.last_suggested_actions_json = None
    ctx.next_action_pending_inject_json = None
    ctx.blocked_host_executor_json = None
    ctx.simulate_execute_pending_json = None
    ctx.sandbox_pending_plan_json = None


def hard_clear_conversation_state_commit(db: Session, ctx: ConversationContext) -> None:
    hard_clear_conversation_state(ctx)
    try:
        db.add(ctx)
        db.commit()
        db.refresh(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hard_clear_conversation_state_commit: %s", exc)
        db.rollback()


def apply_topic_intent_to_context(
    ctx: ConversationContext, user_text: str
) -> tuple[str, str] | None:
    """Apply explicit topic / clear if `user_text` matches. Idempotent. Does not commit."""
    o = detect_topic_override(user_text)
    if not o:
        return None
    if o[0] == "set":
        _mutate_topic_set(ctx, o[1])
    else:
        _mutate_topic_clear(ctx)
    return o


def short_reply_for_topic_intent(intent: tuple[str, str] | None) -> str:
    if not intent:
        return ""
    if intent[0] == "set":
        t = (intent[1] or "general")[:200].strip() or "general"
        return f"Got it — switching context to: {t}"
    return "Got it — context reset."


def append_message(db: Session, ctx: ConversationContext, role: str, text: str) -> None:
    """Appends a sanitized line to the rolling list (mutates `ctx`); does not `commit` alone."""
    safe = sanitize_text((text or "")[:1500])
    try:
        messages = json.loads(ctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        messages = []
    messages.append(
        {
            "role": role,
            "text": safe,
            "ts": datetime.utcnow().isoformat(),
        }
    )
    messages = messages[-MAX_RECENT_MESSAGES:]
    ctx.recent_messages_json = json.dumps(messages, ensure_ascii=False)
    db.add(ctx)


def infer_lightweight_topic(text: str, existing_topic: str | None) -> str | None:
    t = (text or "").lower()
    if any(x in t for x in ("aethos", "nexa", "this app", "the app", "product", "platform")):
        return "Nexa product"
    if any(
        x in t
        for x in (
            "cursor",
            "aider",
            "repo",
            "code",
            "worker",
            "dev loop",
        )
    ):
        return "Nexa autonomous development loop"
    if any(x in t for x in ("overwhelmed", "tasks", "plan", "stuck", "brain dump", "focus")):
        return "personal focus and overwhelm"
    return existing_topic


def update_context_after_turn(
    db: Session,
    ctx: ConversationContext,
    *,
    user_text: str,
    assistant_text: str,
    intent: str | None = None,
    agent_key: str | None = None,
    decision_summary: dict | None = None,
) -> None:
    u = sanitize_text(user_text or "")[:4000]
    a = sanitize_text(assistant_text or "")[:4000]
    override = detect_topic_override(u)
    if override:
        if override[0] == "set":
            _mutate_topic_set(ctx, override[1])
        else:
            _mutate_topic_clear(ctx)
        append_message(db, ctx, "user", u)
        append_message(db, ctx, "assistant", a)
        if intent is not None:
            ctx.last_intent = (intent or "")[:64] or None
        if agent_key is not None:
            ctx.last_agent_key = (agent_key or "")[:64] or None
            ctx.active_agent = (agent_key or "")[:64] or None
        if decision_summary is not None:
            try:
                ctx.last_decision_json = json.dumps(
                    decision_summary, ensure_ascii=False, default=str
                )[:20_000]
            except (TypeError, ValueError, OverflowError):
                pass
        try:
            db.add(ctx)
            db.commit()
            db.refresh(ctx)
        except Exception as exc:  # noqa: BLE001
            logger.warning("update_context_after_turn(override): %s", exc)
            db.rollback()
        return

    append_message(db, ctx, "user", u)
    append_message(db, ctx, "assistant", a)
    if intent is not None:
        ctx.last_intent = (intent or "")[:64] or None
    if agent_key is not None:
        ctx.last_agent_key = (agent_key or "")[:64] or None
        ctx.active_agent = (agent_key or "")[:64] or None

    if ctx.manual_topic_override and ctx.active_topic:
        ctx.active_topic_confidence = (ctx.active_topic_confidence or 1.0) * 0.9
    elif ctx.active_topic:
        ctx.active_topic_confidence = (ctx.active_topic_confidence or 0.5) * 0.85
    if (ctx.active_topic_confidence or 0) < 0.3 and ctx.active_topic is not None:
        ctx.active_topic = None
        ctx.manual_topic_override = False
        ctx.active_topic_confidence = 0.5
    if u and not ctx.manual_topic_override:
        inferred = infer_lightweight_topic(u, ctx.active_topic)
        if inferred:
            ctx.active_topic = inferred[:255]
    if decision_summary is not None:
        try:
            ctx.last_decision_json = json.dumps(
                decision_summary, ensure_ascii=False, default=str
            )[:20_000]
        except (TypeError, ValueError, OverflowError):
            pass
    wct0 = (ctx.web_chat_title or "").strip()
    if (
        wct0 == "New chat"
        and (getattr(ctx, "session_id", None) or "") != "default"
        and u
    ):
        from app.services.web_session_title import derive_web_chat_title_from_message

        ctx.web_chat_title = (derive_web_chat_title_from_message(u) or "New chat")[:80]
    try:
        db.add(ctx)
        db.commit()
        db.refresh(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("update_context_after_turn: %s", exc)
        db.rollback()


def get_last_decision_from_context(ctx: ConversationContext) -> dict | None:
    raw = (getattr(ctx, "last_decision_json", None) or "").strip()
    if not raw:
        return None
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return o if isinstance(o, dict) else None


def get_pending_project_dict(ctx: ConversationContext) -> dict | None:
    raw = (getattr(ctx, "pending_project_json", None) or "").strip()
    if not raw:
        return None
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return o if isinstance(o, dict) else None


def set_pending_project(ctx: ConversationContext, payload: dict) -> None:
    ctx.pending_project_json = json.dumps(payload, default=str)[:20_000]


def clear_pending_project(ctx: ConversationContext) -> None:
    ctx.pending_project_json = None


def build_context_snapshot(ctx: ConversationContext, db: Session | None = None) -> dict:
    try:
        recent = json.loads(ctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        recent = []
    if not isinstance(recent, list):
        recent = []
    snap: dict = {
        "active_topic": ctx.active_topic,
        "active_project": ctx.active_project,
        "active_agent": ctx.active_agent,
        "last_intent": ctx.last_intent,
        "last_agent_key": ctx.last_agent_key,
        "recent_messages": recent[-6:],
        "summary": ctx.summary,
        "active_topic_confidence": ctx.active_topic_confidence or 0.5,
        "manual_topic_override": bool(ctx.manual_topic_override),
        "last_topic_update_at": (ctx.last_topic_update_at.isoformat() if ctx.last_topic_update_at else None),
        "pending_project": get_pending_project_dict(ctx),
    }
    try:
        from app.services.external_execution_session import get_external_execution_fragment

        exf = get_external_execution_fragment(ctx)
        if exf:
            snap["external_execution_flow"] = exf
    except Exception:
        pass
    apid = getattr(ctx, "active_project_id", None)
    if db is not None and apid:
        from app.models.project_context import NexaWorkspaceProject

        row = db.get(NexaWorkspaceProject, int(apid))
        if row and row.owner_user_id == ctx.user_id:
            _wp = {
                "id": row.id,
                "name": row.name,
                "path": row.path_normalized,
            }
            snap["aethos_workspace_project"] = _wp
            snap["nexa_workspace_project"] = _wp  # legacy snapshot key
    return snap


def format_context_ux_status(ctx: ConversationContext) -> str:
    conf = float(ctx.active_topic_confidence or 0.5)
    if conf >= 0.75:
        c_label = "high"
    elif conf >= 0.4:
        c_label = "medium"
    else:
        c_label = "low"
    at = (ctx.active_topic or "—")[:200]
    if ctx.manual_topic_override:
        src = "user override"
    else:
        src = "inferred / decayed"
    return (
        f"Active topic: {at}\n"
        f"Confidence: {c_label}\n"
        f"Source: {src}\n"
        f"(numeric: {conf:.2f})"
    )


def get_last_assistant_text(
    db: Session, app_user_id: str, *, web_session_id: str = "default"
) -> str | None:
    """Most recent assistant message in rolling context (for document export)."""
    ctx = get_or_create_context(db, app_user_id, web_session_id=web_session_id)
    try:
        messages: list = json.loads(ctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        messages = []
    if not isinstance(messages, list):
        return None
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if (m.get("role") or "").strip() != "assistant":
            continue
        tx = m.get("text")
        if tx and str(tx).strip():
            return str(tx)
    return None
