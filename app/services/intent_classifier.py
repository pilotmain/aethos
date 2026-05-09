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
- orchestrate_system: user wants a Nexa-wide status report — Mission Control, missions, dev runs, what succeeded/failed, act as orchestrator (not asking for a disk path)
- external_execution: user wants an end-to-end pipeline on hosted infra — check logs/service, fix code in repo, push, redeploy, verify production (not “explain Railway” alone)
- external_execution_continue: user is replying to Nexa’s Railway/deploy access or preferences questions (short confirmation, not a new unrelated topic)
- external_investigation: user is asking about a hosted provider/service (Railway, Render, deploy health, production outage) without necessarily naming local files
- brain_dump: user is listing tasks, responsibilities, errands, or things they need to organize
- create_sub_agent: user wants to spawn an orchestration sub-agent (registry; natural language or ``subagent create`` style)
- create_custom_agent: legacy LLM-only profile (rare); Phase 48 routes **create … agent** to **create_sub_agent** when orchestration NL matches
- capability_question: user asks what the assistant can do, cannot do, or whether it can help with a specific domain
- help_request: user asks for help, but does not provide actual tasks yet
- followup_reply: user says they did not complete something, or replies to a check-in
- stuck_dev: user is blocked on a technical problem (build/test error, deploy, CI, config, tooling) — not general life overwhelm
- analysis: user wants a deep read of an error, root cause, or postmortem (not a generic chat)
- stuck: user says they are stuck, blocked, frozen, overwhelmed without listing tasks, or cannot start
- status_update: user says they completed something
- correction: user says the assistant misunderstood, asks it to answer the question, or rejects the previous response
- general_chat: anything else
- config_query: user asks about **this deployment's** configuration — LLM provider/model, workspace paths on the host, whether API keys are set (never the secret values)

Important rules:
- Do NOT classify as brain_dump just because the message contains "and".
- Do NOT classify questions as brain_dump.
- If the message asks "what can you do", "can you do design", "can you code", "what can't you do", or asks about custom agents / user-defined agents / building their own specialist, classify as capability_question.
- If the user says "No, answer the question" or similar, classify as correction.
- If the user lists 2 or more concrete tasks, classify as brain_dump.
- If the user says only "I feel overwhelmed" without tasks, classify as stuck.
- If the message is about errors, failing builds/tests, deployment, CI, K8s/EKS, Docker, databases, or auth config AND the user is blocked or asking for a fix, classify as stuck_dev (not generic stuck).
- If the user asks for root cause, postmortem, or to analyze a specific error/trace, classify as analysis.
- If the user asks to check Mission Control, report what succeeded/failed, act as orchestrator, wants an update on missions/runs — classify as orchestrate_system (not general_chat).
- If the user asks you to run a full pipeline (check/fix/push/redeploy/verify) against Railway or production — classify as external_execution (not external_investigation).
- If the user is answering a prior prompt about Railway/CLI auth or deploy preferences — classify as external_execution_continue.
- If the user focuses on Railway/hosted deploy/service health/production outage without that full execution pipeline or follow-up context — classify as external_investigation unless they only want local repo debugging paths.
- If the user wants orchestration/registry agents (natural “create agents …”, conversational lines like “Create a marketing agent”, “Can you create a QA agent?”, “I need a QA specialist”, ``*_agent`` handles, ``subagent create``), classify as **create_sub_agent**.
- **create … agent** without orchestration cues may still classify **create_custom_agent** only when registry NL routing is off (e.g. numbered lists); prefer **create_sub_agent** per Phase 48.
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
    "orchestrate_system",
    "external_execution",
    "external_execution_continue",
    "external_investigation",
    "brain_dump",
    "create_sub_agent",
    "create_custom_agent",
    "capability_question",
    "help_request",
    "followup_reply",
    "stuck",
    "stuck_dev",
    "analysis",
    "status_update",
    "correction",
    "general_chat",
    "dev_command",
    "config_query",
}

# Phase 77 — questions about this deployment's Settings (.env), not user files or missions.
CONFIG_QUERY_PATTERNS = [
    r"what model (?:are you using|are we using|do you use)\??",
    r"which (?:llm|model|anthropic|openai|deepseek|ollama) (?:are we using|is running|do you use)\??",
    r"what (?:llm|model|provider) (?:is configured|am i using|are you using)\??",
    r"show (?:me )?my (?:llm|model|provider) settings",
    r"what (?:api key|token) (?:is configured|am i using)",
    r"where is my workspace",
    r"show (?:me )?my workspace",
    r"what (?:workspace|repository) (?:path|root) (?:is set|am i using)\??",
    r"show (?:me )?my configuration",
    r"what settings (?:do i have|are active)\??",
]


def is_config_query(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 6:
        return False
    return any(re.search(p, t, re.I) for p in CONFIG_QUERY_PATTERNS)

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


def looks_like_stuck_dev(message: str) -> bool:
    """Heuristic: tooling/build/deploy blockage (Phase 49), distinct from generic overwhelm."""
    t = (message or "").lower()
    if len(t) < 8:
        return False
    dev_hints = (
        "pytest",
        "npm ",
        "pip ",
        "docker",
        "kubernetes",
        "k8s",
        "helm",
        "terraform",
        "gradle",
        "cargo",
        "typescript",
        "eslint",
        "jest",
        "vitest",
        "build",
        "compile",
        "traceback",
        "exception",
        "segfault",
        "deploy",
        "pipeline",
        "github action",
        "gitlab ci",
        "mongodb",
        "mongo ",
        "postgres",
        "redis",
        "kafka",
        "grpc",
        "oidc",
        "oauth",
        "ingress",
        "eks ",
        "ci/",
        "http 401",
        "http 500",
        "timeout",
    )
    if not any(h in t for h in dev_hints):
        return False
    pain = (
        "stuck",
        "blocked",
        "can't",
        "cant ",
        "cannot ",
        "won't",
        "wont ",
        "doesn't work",
        "doesnt work",
        "not working",
        "broken",
        "fails",
        "failed",
        "failing",
        "error",
        "help me fix",
        "figure out",
        "debug",
        "why ",
        "how do i fix",
        "how can i fix",
    )
    return any(p in t for p in pain)


def looks_like_orchestrate_system(message: str) -> bool:
    """User wants MC/orchestration overview — must not route to local file path clarification."""
    t = (message or "").lower()
    if len(t) < 6:
        return False
    cues = (
        "mission control",
        "what succeeded",
        "what failed",
        "report back",
        "give me a report",
        "summarize what",
        "what ran",
        "what happened",
        "status of my",
        "update me on",
        "update me",
        "orchestrat",
        "act as orchestrator",
        "as orchestrator",
        "run overview",
        "which missions",
        "show me missions",
        "active work",
        "nexa forge",
    )
    return any(c in t for c in cues)


def _looks_like_local_git_workspace_without_hosted_provider(message: str) -> bool:
    """True for laptop/local-git checks without naming Railway/Vercel/etc."""
    t = (message or "").lower()
    if not re.search(r"(?i)\bgit\b", t):
        return False
    local_cue = bool(
        re.search(
            r"(?i)(check\s+this\s+git\s+in\s+local|this\s+git\s+in\s+local|git\s+in\s+local|"
            r"\blocal\s+git\b|on\s+my\s+machine|this\s+git\s+locally)",
            message or "",
        )
    )
    hosted_named = bool(
        re.search(
            r"(?i)\b(railway|vercel|render\.com|fly\.io|heroku|netlify)\b",
            t,
        )
    ) or "railway.app" in t or ".vercel.app" in t
    return local_cue and not hosted_named


def looks_like_external_execution(message: str) -> bool:
    """
    User wants Nexa to coordinate real steps: hosted provider + repo + push/deploy.

    Narrower than external_investigation (diagnose/triage). Must stay after orchestrate_system.
    """
    if looks_like_orchestrate_system(message):
        return False
    if _looks_like_local_git_workspace_without_hosted_provider(message):
        return False
    t = (message or "").lower()
    if len(t) < 10:
        return False
    hosted = (
        "railway",
        "render.com",
        "fly.io",
        "flyctl",
        "heroku",
        "vercel",
        "netlify",
        "production",
        "deploy",
        "hosted",
        "github",
        "git ",
        "repo",
        "service",
    )
    pipeline_markers = (
        "redeploy",
        "push changes",
        "push to git",
        "push to github",
        "fix repo",
        "fix the repo",
        "commit and push",
        "commit & push",
        "run tests and",
        "deploy and verify",
        "rollback",
        "trigger deploy",
        "open a pr",
        "merge and deploy",
    )
    if any(p in t for p in pipeline_markers):
        if any(h in t for h in hosted):
            return True
        if "redeploy" in t or "push changes" in t:
            return True
    if ("fix issue" in t or "fix the issue" in t) and any(h in t for h in hosted):
        return True
    if "service failing" in t and any(x in t for x in ("railway", "production", "deploy", "hosted")):
        return True
    check_svc = (
        "check railway" in t
        or "check render" in t
        or "check production" in t
        or "check the service" in t
        or "check service" in t
    )
    if check_svc and any(v in t for v in ("fix", "push", "redeploy", "deploy", "commit", "patch", "repo")):
        return True
    return False


def looks_like_external_execution_continue(
    message: str,
    conversation_snapshot: dict | None = None,
) -> bool:
    """Short confirmation while external_execution_flow awaits input — requires snapshot hint."""
    if looks_like_orchestrate_system(message):
        return False
    if looks_like_external_execution(message):
        return False
    snap = conversation_snapshot or {}
    ex = snap.get("external_execution_flow")
    if not isinstance(ex, dict) or ex.get("status") != "awaiting_followup":
        return False
    t = (message or "").strip()
    return len(t) >= 2


def looks_like_external_investigation(message: str, conversation_snapshot: dict | None = None) -> bool:
    """Hosted infra / deploy context — not a request to read a local folder by default."""
    if looks_like_orchestrate_system(message):
        return False
    if looks_like_external_execution(message):
        return False
    if looks_like_external_execution_continue(message, conversation_snapshot):
        return False
    t = (message or "").lower()
    if len(t) < 6:
        return False
    if re.search(r"https?://", t):
        return True
    if re.search(
        r"\b(railway|render\.com|fly\.io|flyctl|heroku|vercel|netlify|cloudflare)\b",
        t,
    ):
        return True
    if "production" in t and any(x in t for x in ("down", "outage", "crash", "unhealthy")):
        return True
    if "deploy" in t and "service" in t:
        return True
    if "service" in t and any(x in t for x in ("crash", "crashed", "failing", "unhealthy")):
        return True
    return False


def looks_like_analysis(message: str) -> bool:
    """Heuristic: user wants error/root-cause analysis (Phase 50)."""
    t = (message or "").lower()
    if len(t) < 10:
        return False
    return bool(
        re.search(
            r"(?i)(root\s+cause|post-?mortem|postmortem|"
            r"analyze\s+(this|the)\s+(error|failure|issue|traceback|log)|"
            r"break\s+down\s+(this|the)\s+error|"
            r"why\s+(did|is|does)\s+(this|it|the)\s+(build|test|deploy|pipeline)|"
            r"error\s+analysis|incident\s+review)\b",
            t,
        )
    )


_INFO_QUESTION_STARTERS: tuple[str, ...] = (
    "what ",
    "what's ",
    "whats ",
    "how ",
    "why ",
    "where ",
    "when ",
    "who ",
    "can you ",
    "could you ",
    "would you ",
    "should i ",
    "should we ",
    "do you ",
    "does it ",
    "does the ",
    "is it ",
    "is there ",
    "are you ",
    "am i ",
    "tell me ",
    "explain ",
    "i'm curious",
    "im curious",
    "i am curious",
)

_INFO_QUESTION_IMPERATIVE_HINTS: tuple[str, ...] = (
    " now",
    " now.",
    " now?",
    " now!",
    "go ahead",
    "let's deploy",
    "let me deploy",
    "let's push",
    "let me push",
    "let's run",
    "let me run",
    "do it",
    "ship it",
    "kick off",
    "run it",
    "please run",
    "please deploy",
    "please push",
    "please commit",
    "execute it",
    "execute now",
    "right now",
)

_INFO_QUESTION_LEAD_VERBS = re.compile(
    r"^(deploy|push|commit|run|execute|build|start|stop|migrate|rollback|merge|ship|kick)\b",
    re.IGNORECASE,
)

_INFO_QUESTION_PROVIDER_NAMES = re.compile(
    r"\b(railway|render\.com|fly\.io|flyctl|heroku|vercel|netlify|cloudflare|render\b)\b",
    re.IGNORECASE,
)

# ``looks_like_stuck_dev`` keys off any pain word + dev hint, but the bare interrogative
# starter "why " is also in that pain set, so genuine curiosity questions about dev
# topics ("Why does Kubernetes ingress exist?") get pulled into stuck_dev. Treat the
# remaining pain phrases as the real signal that the user is blocked / asking for a fix.
_INFO_QUESTION_REAL_PAIN: tuple[str, ...] = (
    "stuck",
    "blocked",
    "can't",
    "cant ",
    "cannot ",
    "won't",
    "wont ",
    "doesn't work",
    "doesnt work",
    "not working",
    "broken",
    "fails",
    "failed",
    "failing",
    "error",
    "help me fix",
    "figure out",
    "debug",
    "how do i fix",
    "how can i fix",
)


def looks_like_informational_question(
    text: str,
    conversation_snapshot: dict | None = None,
) -> bool:
    """
    Phase 69 — clearly interrogative messages with no pain/provider/imperative cues.

    Returns True only when the message is shaped like a question and free of signals
    that should route it to ``stuck_dev``, ``analysis``, ``external_execution``,
    ``external_investigation``, ``external_execution_continue``, or
    ``orchestrate_system``. Used by :func:`get_intent` to short-circuit the LLM
    classifier and avoid hijacking informational queries into the dev pipeline.
    """
    t = (text or "").strip()
    if not t or len(t) < 2:
        return False
    tl = t.lower()

    interrogative_shape = t.endswith("?") or any(tl.startswith(s) for s in _INFO_QUESTION_STARTERS)
    if not interrogative_shape:
        return False

    if re.search(r"https?://", tl):
        return False
    if _INFO_QUESTION_PROVIDER_NAMES.search(tl):
        return False

    if any(marker in tl for marker in _INFO_QUESTION_IMPERATIVE_HINTS):
        return False
    if _INFO_QUESTION_LEAD_VERBS.match(tl):
        return False

    # Defer to the existing deterministic intents — they have stronger signals than question-shape.
    if looks_like_orchestrate_system(text):
        return False
    if looks_like_external_execution(text):
        return False
    if looks_like_external_execution_continue(text, conversation_snapshot):
        return False
    if looks_like_external_investigation(text, conversation_snapshot):
        return False
    if looks_like_analysis(text):
        return False
    if looks_like_stuck_dev(text):
        # If the only pain match is the bare "why " starter, keep treating as informational.
        if any(p in tl for p in _INFO_QUESTION_REAL_PAIN):
            return False

    return True


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


def classify_intent_fallback(
    message: str,
    conversation_snapshot: dict | None = None,
) -> dict:
    t = message.lower().strip()

    if is_config_query(message):
        return {"intent": "config_query", "confidence": 0.95, "reason": "configuration / settings question"}

    if looks_like_orchestrate_system(message):
        return {"intent": "orchestrate_system", "confidence": 0.92, "reason": "mission control / orchestration cues"}

    if looks_like_external_execution(message):
        return {"intent": "external_execution", "confidence": 0.91, "reason": "hosted execution pipeline (fix/push/deploy)"}

    if looks_like_external_execution_continue(message, conversation_snapshot):
        return {"intent": "external_execution_continue", "confidence": 0.9, "reason": "Railway/deploy prefs reply"}

    if looks_like_external_investigation(message, conversation_snapshot):
        return {"intent": "external_investigation", "confidence": 0.9, "reason": "hosted infra / deploy cues"}

    if is_multi_agent_capability_question(message):
        return {
            "intent": "capability_question",
            "confidence": 0.93,
            "reason": "multi-agent team capability",
        }

    from app.services.sub_agent_natural_creation import looks_like_registry_agent_creation_nl

    if looks_like_registry_agent_creation_nl(message):
        return {"intent": "create_sub_agent", "confidence": 0.94, "reason": "orchestration sub-agent natural language"}

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

    if looks_like_stuck_dev(message):
        return {"intent": "stuck_dev", "confidence": 0.9, "reason": "dev blockage heuristic"}

    if looks_like_analysis(message):
        return {"intent": "analysis", "confidence": 0.86, "reason": "error analysis or root cause"}

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
    message: str,
    conversation_snapshot: dict | None = None,
    *,
    memory_summary: str | None = None,
) -> dict:
    from app.services.llm_key_resolution import get_merged_api_keys
    from app.services.safe_llm_gateway import sanitize_text

    s = get_settings()
    m = get_merged_api_keys()
    if not s.use_real_llm or not m.has_any_key:
        return classify_intent_fallback(message)

    mem_note = ""
    if (memory_summary or "").strip():
        mem_note = (
            "User's stored context (helps disambiguate 'my project', 'the stack', 'same as before'):\n"
            f"{sanitize_text((memory_summary or '').strip()[:2500])}\n\n"
        )

    user_block = message
    if conversation_snapshot:
        import json

        try:
            snap = json.dumps(conversation_snapshot, ensure_ascii=False)[:3500]
        except (TypeError, ValueError):
            snap = "{}"
        user_block = (
            mem_note
            + "Recent conversation context (JSON, may be partial):\n"
            f"{sanitize_text(snap)}\n\nUser message to classify:\n{message}"
        )
    elif mem_note:
        user_block = mem_note + f"User message to classify:\n{message}"

    try:
        from app.services.llm_usage_context import push_llm_action

        with push_llm_action(
            source="intent_classifier", action_type="intent_classification", agent_key="aethos"
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
        return classify_intent_fallback(message, conversation_snapshot)


def get_intent(
    message: str,
    conversation_snapshot: dict | None = None,
    *,
    memory_summary: str | None = None,
) -> str:
    t0 = (message or "").strip()
    tl0 = t0.lower()
    from app.services.sub_agent_natural_creation import looks_like_registry_agent_creation_nl

    # Phase 77 — before registry/orchestration cues so "what model…" is never mistaken for actions.
    if is_config_query(t0):
        return "config_query"

    if looks_like_registry_agent_creation_nl(t0):
        return "create_sub_agent"

    if looks_like_orchestrate_system(t0):
        return "orchestrate_system"

    if looks_like_external_execution(t0):
        return "external_execution"

    if looks_like_external_execution_continue(t0, conversation_snapshot):
        return "external_execution_continue"

    if looks_like_external_investigation(t0, conversation_snapshot):
        from app.services.hosted_service_mission_gate import hosted_deploy_provider_match

        # Railway / deploy dashboard URLs → external_execution access gate + runner path, not generic investigation UX.
        if hosted_deploy_provider_match(t0):
            return "external_execution"
        return "external_investigation"

    # Phase 69 — interrogative messages with no pain/provider/imperative cues skip the LLM
    # classifier and route through the deterministic fallback. Action-oriented intents
    # (stuck_dev / analysis / external_*) are coerced to general_chat because our gate
    # already verified those patterns aren't a real fit. Prevents the dev pipeline from
    # hijacking questions like "what do you need to deploy to AWS?".
    if (
        get_settings().nexa_informational_question_skip_llm
        and looks_like_informational_question(t0, conversation_snapshot)
    ):
        fb_intent = classify_intent_fallback(t0, conversation_snapshot)["intent"]
        if fb_intent in {
            "stuck_dev",
            "stuck",
            "analysis",
            "external_execution",
            "external_execution_continue",
            "external_investigation",
            "orchestrate_system",
            "brain_dump",
        }:
            return "general_chat"
        return fb_intent

    result = classify_intent_llm(
        message,
        conversation_snapshot=conversation_snapshot,
        memory_summary=memory_summary,
    )
    intent = result["intent"]
    confidence = result["confidence"]

    if intent == "create_custom_agent" and looks_like_registry_agent_creation_nl(t0):
        intent = "create_sub_agent"

    if intent in ("create_custom_agent", "create_sub_agent") and is_multi_agent_capability_question(t0):
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

    if intent == "stuck" and looks_like_stuck_dev(t0):
        intent = "stuck_dev"

    return intent


def is_command_question(text: str) -> bool:
    """User is asking for AethOS command / capability guidance, not the agent lens view."""
    t = (text or "").lower()
    patterns = [
        "what commands",
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


def get_fallback_response(user_input: str) -> str:
    """Return a friendly response when intent not recognized"""
    
    # Check if it MIGHT be an agent creation
    if any(word in user_input.lower() for word in ['create', 'make', 'agent', 'new']):
        return "I can help you create an agent. Try: 'Create a marketing agent'"
    
    # Otherwise, normal fallback
    return "I'm not sure what you mean. Can you rephrase?"
