"""LLM + conservative fallback intent routing (Intent Classification v2)."""

from __future__ import annotations

import logging
import re

from app.core.config import get_settings
from app.services.multi_agent_routing import is_multi_agent_capability_question
from app.services.safe_llm_gateway import safe_llm_json_call

logger = logging.getLogger(__name__)

INTENT_CLASSIFIER_PROMPT = """You are an intent classifier for Nexa.
Classify the user's message into exactly one intent.

Valid intents:
- brain_dump: user is listing tasks, responsibilities, errands, or things they need to organize
- create_custom_agent: user wants to create a new Nexa custom agent (message starts with "create" and mentions "agent")
- capability_question: user asks what the assistant can do, cannot do, or whether it can help with a specific domain
- help_request: user asks for help, but does not provide actual tasks yet
- followup_reply: user says they did not complete something, or replies to a check-in
- stuck: user says they are stuck, blocked, frozen, overwhelmed without listing tasks, or cannot start
- status_update: user says they completed something
- correction: user says the assistant misunderstood, asks it to answer the question, or rejects the previous response
- general_chat: anything else

Important rules:
- Do NOT classify as brain_dump just because the message contains "and".
- Do NOT classify questions as brain_dump.
- If the message asks "what can you do", "can you do design", "can you code", "what can't you do", or asks about custom agents / user-defined agents / building their own specialist, classify as capability_question.
- If the user says "No, answer the question" or similar, classify as correction.
- If the user lists 2 or more concrete tasks, classify as brain_dump.
- If the user says only "I feel overwhelmed" without tasks, classify as stuck.
- If the user message (after trimming) starts with "create" and contains the word "agent", classify as create_custom_agent — except vague multi-agent capability questions (e.g. "can you create multi agents that communicate"); those are capability_question.
- If uncertain, choose general_chat, not brain_dump.

Return JSON only:
{{
  "intent": "one_valid_intent",
  "confidence": 0.0-1.0,
  "reason": "short explanation"
}}

User message: {message}"""

INTENT_CLASSIFIER_SYSTEM = INTENT_CLASSIFIER_PROMPT.rsplit("User message:", 1)[0].strip()

VALID_INTENTS = {
    "brain_dump",
    "create_custom_agent",
    "capability_question",
    "help_request",
    "followup_reply",
    "stuck",
    "status_update",
    "correction",
    "general_chat",
    "dev_command",
}

TASK_VERBS = [
    "finish",
    "call",
    "email",
    "send",
    "book",
    "buy",
    "clean",
    "fix",
    "write",
    "submit",
    "pay",
    "schedule",
    "go to",
    "pick up",
    "prepare",
]


def looks_like_brain_dump(text: str) -> bool:
    t = text.lower().strip()

    if "?" in t:
        return False
    question_starters = (
        "what ",
        "why ",
        "how ",
        "can you ",
        "could you ",
        "do you ",
        "tell me ",
        "explain ",
    )
    if t.startswith(question_starters):
        return False
    if any(p in t for p in ["i need to", "i have to", "need to", "have to", "gotta"]):
        return True
    if "," in t:
        parts = [p.strip() for p in t.split(",") if p.strip()]
        task_like_parts = 0
        for part in parts:
            if any(v in part for v in TASK_VERBS):
                task_like_parts += 1
        if task_like_parts >= 2:
            return True
    verb_hits = sum(1 for v in TASK_VERBS if v in t)
    if verb_hits >= 2 and len(t.split()) >= 6:
        return True
    return False


def classify_intent_fallback(message: str) -> dict:
    t = message.lower().strip()

    if is_multi_agent_capability_question(message):
        return {
            "intent": "capability_question",
            "confidence": 0.93,
            "reason": "multi-agent team capability",
        }

    if t.startswith("create") and "agent" in t:
        return {"intent": "create_custom_agent", "confidence": 0.95, "reason": "create agent phrase"}

    if any(
        x in t
        for x in [
            "what can you do",
            "what can't you do",
            "what cant you do",
            "can you do",
            "can you code",
            "can you design",
            "what are you able to do",
            "what do you do",
            "what things you can",
            "what you can do",
            "what you can't do",
            "what you cant do",
            "besides planning",
            "what else can you",
            "web research",
            "search the web",
            "search online",
            "do you have access to the web",
            "do you have access to google",
            "custom agent",
            "custom agents",
            "my own agent",
            "personal agent",
            "build my own agent",
            "senior attorney",
            "lawyer agent",
        ]
    ):
        return {"intent": "capability_question", "confidence": 0.9, "reason": "capability phrase"}
    if "tell me what" in t and "can" in t and "you" in t:
        return {"intent": "capability_question", "confidence": 0.85, "reason": "tell me what you can"}

    if any(
        x in t
        for x in [
            "answer the question",
            "not what i asked",
            "you misunderstood",
            "stop making a plan",
            "that's not what i asked",
            "that is not what i asked",
        ]
    ):
        return {"intent": "correction", "confidence": 0.9, "reason": "correction phrase"}

    if re.search(r"\bstuck\b|can't start|cant start|\bfrozen\b", t):
        return {"intent": "stuck", "confidence": 0.9, "reason": "stuck phrase"}

    if t in {"not done", "didn't do it", "didnt do it", "no", "nope", "not yet"}:
        return {"intent": "followup_reply", "confidence": 0.9, "reason": "followup phrase"}

    if any(x in t for x in ["done", "finished", "completed"]):
        return {"intent": "status_update", "confidence": 0.8, "reason": "completion phrase"}

    if "help" in t and len(t.split()) <= 8:
        return {"intent": "help_request", "confidence": 0.75, "reason": "short help request"}

    # Emotional overload without a concrete list → stuck (not a plan)
    if (
        not looks_like_brain_dump(t)
        and "?" not in t
        and (
            re.search(
                r"\boverwhelmed\b|\btoo much\b|so much to do|so much todo|i feel stressed|i am stressed|i'm stressed|im stressed",
                t,
            )
        )
    ):
        return {"intent": "stuck", "confidence": 0.85, "reason": "overload without task list"}

    if looks_like_brain_dump(t):
        return {"intent": "brain_dump", "confidence": 0.75, "reason": "task-list pattern"}

    return {"intent": "general_chat", "confidence": 0.5, "reason": "fallback default"}


def classify_intent_llm(
    message: str, conversation_snapshot: dict | None = None
) -> dict:
    from app.services.llm_key_resolution import get_merged_api_keys

    s = get_settings()
    m = get_merged_api_keys()
    if not s.use_real_llm or not m.has_any_key:
        return classify_intent_fallback(message)

    user_block = message
    if conversation_snapshot:
        import json

        from app.services.safe_llm_gateway import sanitize_text

        try:
            snap = json.dumps(conversation_snapshot, ensure_ascii=False)[:3500]
        except (TypeError, ValueError):
            snap = "{}"
        user_block = (
            "Recent conversation context (JSON, may be partial):\n"
            f"{sanitize_text(snap)}\n\nUser message to classify:\n{message}"
        )

    try:
        from app.services.llm_usage_context import push_llm_action

        with push_llm_action(
            source="intent_classifier", action_type="intent_classification", agent_key="nexa"
        ):
            data = safe_llm_json_call(
                system_prompt=INTENT_CLASSIFIER_SYSTEM,
                user_request=user_block,
                schema_hint='{ "intent": "string", "confidence": 0.0, "reason": "string" }',
            )
        raw = data.get("intent", "general_chat")
        intent = str(raw).strip() if raw is not None else "general_chat"
        if intent not in VALID_INTENTS:
            intent = "general_chat"
        confidence = float(data.get("confidence", 0.0))
        reason = str(data.get("reason", "") or "")
        return {"intent": intent, "confidence": confidence, "reason": reason}
    except Exception as e:  # noqa: BLE001
        logger.exception("LLM intent classification failed: %s", e)
        return classify_intent_fallback(message)


def get_intent(
    message: str, conversation_snapshot: dict | None = None
) -> str:
    t0 = (message or "").strip()
    tl0 = t0.lower()
    if tl0.startswith("create") and "agent" in tl0:
        return "create_custom_agent"

    result = classify_intent_llm(message, conversation_snapshot=conversation_snapshot)
    intent = result["intent"]
    confidence = result["confidence"]

    if intent == "create_custom_agent" and is_multi_agent_capability_question(t0):
        intent = "capability_question"
        confidence = max(confidence, 0.9)

    logger.info(
        "intent_classifier intent=%s confidence=%s reason=%s text_preview=%s",
        intent,
        confidence,
        result.get("reason"),
        message[:80],
    )

    if intent == "brain_dump" and confidence < 0.72:
        return "general_chat"
    return intent


def is_command_question(text: str) -> bool:
    """User is asking for Nexa’s command / capability list, not the agent lens view."""
    t = (text or "").lower()
    patterns = [
        "what commands",
        "what can you do",
        "what do you support",
        "list commands",
        "available commands",
        "what are the commands",
    ]
    if any(p in t for p in patterns):
        return True
    # Word "help" / "/help" — not substrings of "helpful" etc.
    if re.search(r"/help\b", t) or re.search(r"(?i)\bhelp\b", t):
        return True
    return False
