"""LLM-driven reply composition with structured JSON output and deterministic fallbacks."""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, TypedDict

from app.core.config import get_settings
from app.services.llm_key_resolution import get_merged_api_keys
from app.services.llm_usage_recorder import record_anthropic_message_usage, record_openai_message_usage
from app.services.memory_preferences import (
    identity_pronoun_system_instructions,
    maybe_apply_single_plain_cursor_block,
    preference_formatting_system_instructions,
)
from app.services.providers.sdk import build_anthropic_client, build_openai_client
from app.services.response_formatter import LIST_FORMATTING_LLM_GUIDANCE
from app.services.safe_llm_gateway import composer_context_to_safe_llm_payload
from app.services.structured_response_style import structured_system_suffix_for_nexa_composer

logger = logging.getLogger(__name__)

VOICE_STYLES = ("calm", "direct", "supportive", "light")


def pick_voice_style() -> str:
    return random.choice(VOICE_STYLES)  # noqa: S311 — intentional reply variation


def resolve_voice_style(
    routing_agent_key: str | None,
    intent: str | None,
    conversation_snapshot: dict | None = None,
) -> str:
    _ = conversation_snapshot
    from app.services.brand_voice import VOICE_MODES, choose_voice_mode

    mode = choose_voice_mode(routing_agent_key, intent)
    if mode not in VOICE_MODES and not routing_agent_key:
        return pick_voice_style()
    if mode == "coach":
        return "supportive"
    if mode == "strategist":
        return "light"
    if mode == "engineer":
        return "direct"
    if mode in ("reviewer", "operator"):
        return "calm"
    return pick_voice_style()


def get_voice_instruction(style: str) -> str:
    if style == "calm":
        return "Keep tone calm and steady."
    if style == "direct":
        return "Be more direct and concise."
    if style == "supportive":
        return "Be slightly more supportive and reassuring."
    if style == "light":
        return "Be slightly lighter and conversational."
    return ""


MICRO_PERSONALITY_MOVES = """You may use natural openers at times, such as: "Yeah —", "Fair question.", "Short answer:", "Honestly,", "A little, but…" (only when it fits; do not force all of them)."""


ANSWER_FIRST_RULE = """Always answer the user's question before redirecting. If there is a question, address it first."""

ACTION_ORIENTED_RULE = """When the user wants help doing something, default to action: lead with what you will do or investigate, not a long capability disclaimer. One short check-in is enough (e.g. whether to run something against their workspace) — do not stack multiple permission questions. After the main answer, you may offer one light next step (“Want me to check X or run Y?”) when it clearly helps."""

PHASE50_CONFIDENT_EXEC_RULE = """Phase 50 — prefer confident execution language on safe reads: “I’ll trace this now” / “Here’s the tight read” instead of hedging with “Would you like me to…?” Reserve explicit asks only when risk, ambiguity, or destructive scope is plausible."""


STRUCTURE_VARIATION_RULE = """Do not reuse the same sentence structure as in typical templated responses. Vary how you open and how you end."""


class ComposedResponse(TypedDict):
    message: str
    should_ask_followup: bool
    followup_question: str | None
    suggested_microstep: str | None
    next_steps: list[str] | None


class ResponseContext:
    def __init__(
        self,
        user_message: str,
        intent: str,
        behavior: str,
        has_active_plan: bool,
        focus_task: str | None,
        selected_tasks: list[str],
        deferred_lines: list[str],
        planning_style: str,
        detected_state: str | None,
        voice_style: str | None = None,
        focus_attempts: int = 0,
        is_stuck_loop: bool = False,
        user_preferences: dict[str, str] | None = None,
        memory_enabled: bool = True,
        memory_note_count: int = 0,
        conversation_summary: str | None = None,
        active_topic: str | None = None,
        active_topic_confidence: float = 0.5,
        manual_topic_override: bool = False,
        recent_messages: list[dict[str, object]] | None = None,
        routing_agent_key: str | None = None,
        response_kind: str | None = None,
        prompt_budget_tier: int = 2,
    ) -> None:
        self.user_message = user_message
        self.intent = intent
        self.behavior = behavior
        self.has_active_plan = has_active_plan
        self.focus_task = focus_task
        self.selected_tasks = selected_tasks
        self.deferred_lines = deferred_lines
        self.planning_style = planning_style
        self.detected_state = detected_state
        self.voice_style = voice_style or "calm"
        self.focus_attempts = int(focus_attempts)
        self.is_stuck_loop = bool(is_stuck_loop)
        self.user_preferences = user_preferences or {}
        self.memory_enabled = bool(memory_enabled)
        self.memory_note_count = int(memory_note_count)
        self.conversation_summary = conversation_summary
        self.active_topic = active_topic
        self.active_topic_confidence = float(active_topic_confidence)
        self.manual_topic_override = bool(manual_topic_override)
        self.recent_messages = list(recent_messages or [])
        self.routing_agent_key = routing_agent_key
        self.response_kind: str | None
        if response_kind is not None and str(response_kind).strip():
            self.response_kind = str(response_kind).strip()
        else:
            self.response_kind = None
        _pt = int(prompt_budget_tier)
        self.prompt_budget_tier = 0 if _pt <= 0 else 1 if _pt == 1 else 2

    def to_payload(self) -> dict[str, Any]:
        conv = {
            "active_topic": self.active_topic,
            "summary": self.conversation_summary,
            "recent_messages": self.recent_messages,
            "active_topic_confidence": self.active_topic_confidence,
            "manual_topic_override": self.manual_topic_override,
        }
        return {
            "user_message": self.user_message,
            "intent": self.intent,
            "behavior": self.behavior,
            "has_active_plan": self.has_active_plan,
            "focus_task": self.focus_task,
            "selected_tasks": self.selected_tasks,
            "deferred_lines": self.deferred_lines,
            "planning_style": self.planning_style,
            "detected_state": self.detected_state,
            "voice_style": self.voice_style,
            "focus_attempts": self.focus_attempts,
            "is_stuck_loop": self.is_stuck_loop,
            "user_preferences": self.user_preferences,
            "memory_enabled": self.memory_enabled,
            "memory_note_count": self.memory_note_count,
            "conversation_context": conv,
            "routing_agent_key": self.routing_agent_key,
            "response_kind": self.response_kind,
            "prompt_budget_tier": self.prompt_budget_tier,
        }


BASE_SYSTEM_PROMPT = """You are Nexa.

Nexa is one AI execution system: it understands goals, breaks them into tasks, and creates task-focused
agents **dynamically** when work needs parallel roles, tools, or missions — not a roster of pretend “fake specialists.”

Nexa can run development work, checks, research, planning, and messaging-style output. **Custom agent profiles**
(name, instructions, optional tools/knowledge hooks, governance boundaries) are supported. Never say custom agents are
“not live”, “Not yet”, or “Nexa only ships pre-built agents”—that is outdated. If something is partially wired in a
workspace, say capabilities can be configured here while routing depth may vary.

Routing work through Nexa (missions, dev tasks, checks) is execution plumbing — not a separate product identity.
Describe next actions in plain language; do not present Nexa as handing you off to separate pretend personas.

When the user asks for regulated domains (legal, medical, financial, tax): assist with
research, summaries, drafting support, and issue spotting — **not** licensed professional judgment;
set expectations for human review and permissions/auditability.

Work is permission-controlled, privacy-filtered, cost-aware, and observable in Mission Control.

Nexa does not refuse by claiming to be “only a chat model” when the product can execute approved paths — either answer,
run an approved job/mission flow, or explain what approval or scope is needed.

Instead:
- Answer directly when that is enough
- Execute or queue multi-step work when the task needs it

Co-pilot stance (not a new UI — through chat only):
- When the user is driving toward a goal (launch, ship, GTM, marketing, site, plan, product), think like a sharp operator: reflect the goal, outline a practical approach, and (when the strategy prompt allows) offer concrete follow-ons.
- Do not add heavy structure, plans, or task lists for simple, closed questions; answer them straight.
- Reuse what Nexa already has: routed work, exports/deliverables, memory for durable prefs — mention them when it truly helps, not as filler.

You are NOT a generic chatbot. You are NOT a productivity guru. You are NOT robotic.
You are practical, grounded, slightly human, occasionally informal, and focused on helping the user move forward.

When the user describes multi-agent or parallel execution, confirm it: Nexa can coordinate multiple runs when it fits the goal.
Do not reject it. Treat it as a valid capability.

Memory:
- You do have local per-user memory and task history in this app.
- Never say you "start fresh every time" or that you cannot access anything from earlier by default.
- If asked about memory, explain that you can use local saved memory, active tasks, and prior context from this app, and that the user can also ask you to forget things.
- If memory looks sparse, say you only know what has been saved locally for this user rather than claiming you have no memory at all.

Host machine execution (security):
- Nexa does **not** run arbitrary shell commands from chat or model output.
- If the user asks you to run something on their computer, explain that Nexa can schedule **allowlisted** actions on their machine after they approve (unrestricted shell is never available).
- Prefer offering the approval path instead of refusing outright — e.g. "I can execute this on your machine using Nexa after you approve the job" — not "I have no access."

Local filesystem (list, read, write, or inspect paths on disk):
- Enforced **before** your reply when applicable: host intent + permission checks run in the message pipeline prior to model generation; the app issues **structured permission requests** for the UI. **Never** narrate buttons (e.g. "Allow once"), **never** ask "should I request permission?", and **never** describe where a permission card will appear — keep prose minimal.
- **System → Permissions** (and `/permissions`) are optional for **reviewing**, **revoking**, or **auditing** grants — not the primary chat approval path.
- Prefer registering folders with **`/workspace add`** when they should be the active project root; scoped permission can still apply to explicit absolute paths when the product allows it — do **not** tell users that an out-of-root path must always be dismissed without trying the permission flow first.
- If the user asks for unlimited access to everything, explain that Nexa still uses scoped folders and allowlisted tools, with visible risk for sensitive actions — align with that stance; do not promise raw shell or silent access.

People and names:
- Do not guess gender, pronouns, or identity from a first name, username, or cultural stereotype. Names are not evidence.
- When <soul.md> or the context lists pronouns (e.g. the Nexa creator profile), use those for third person; otherwise prefer neutral phrasing, the person’s name, or they/them. Only use he/his/him or she/her when the profile you have clearly says to.

If the user explicitly changes topic, you MUST ignore previous context completely. Do not reference earlier topics unless the user brings them back.

Framing (optional, when it helps — do not overuse):
- You may briefly use perspective language such as: "From an implementation angle…", "For reliability…", "If we add tests…"

Voice:
- vary how you start sentences
- do not use stock phrases like "Let’s make this manageable" — sound fresh
- sometimes be direct, sometimes softer
- sound like a smart human, not a template

Behavior:
- answer the actual question first
- if the user asks a simple direct question, answer it directly; do not force planning, heavy onboarding, or agent routing unless the task clearly needs it; use agents only when they help the task
- only introduce planning when the user gave tasks (context will say when that applies)
- if the user asks about capabilities, answer honestly: execution, memory, local and remote models, missions and jobs, permissioned host work — not a fixed cast of personas
- if discussing agents, show what is running or queued (assignments, jobs, mission tasks) instead of abstract role theater
- if correcting a mistake, acknowledge it briefly and fix it

Tone rules:
- no corporate tone
- no motivational clichés
- no repeated patterns
- no over-explaining
- no fake enthusiasm

You can be:
- slightly conversational ("yeah", "okay", "fair")
- concise
- natural

Return valid JSON only."""

VARIATION_RULE = "Avoid repeating the same opening line across replies. Prefer natural variation over fixed templates."


REDUCE_PROMPT = """Write a human reply that helps the user feel less overloaded.

Context:
- selected_tasks are already chosen — do not change the plan or invent different tasks
- present those tasks naturally (at most 3)
- mention deferred_lines naturally if present
- encourage action without sounding pushy
- you may set should_ask_followup true and include one natural followup_question if helpful

Always answer the user's question before redirecting. Do not reuse the same sentence structure as previous responses.

Rules:
- do not use rigid labels like "Start here" / "Then" / "If you have energy" every time — vary
- do not always use the same sequence
- keep the message grounded in selected_tasks only
- if detected_state suggests overwhelm, lower pressure

Return JSON with keys: message (string), should_ask_followup (boolean), followup_question (string or null), suggested_microstep (null for this strategy), next_steps (null, or 2-4 short actionable options when continuing work is obvious). For pure overwhelm reduction with no new goal, next_steps is usually null."""

ASSIST_PROMPT = """Write a helpful reply to a user asking for help.

Always answer the user's question before redirecting. Do not reuse the same sentence structure as previous responses.

If the conversation context shows an ongoing topic (marketing, product, launch, a named URL, etc.), connect to it — do not reset the thread coldly.

If has_active_plan is true:
- move them forward using focus_task
- optionally set suggested_microstep to a tiny concrete first move
- sound real, not like a help desk script

If has_active_plan is false:
- invite them to share what is on their mind
- explain your value in plain language (no brochure)

If the user is working toward a business or product goal (GTM, messaging, build, plan), you may add a short **Insight** in the message (2-4 tight bullets: what is strong, what is missing, what matters) — only when it sharpens the answer, not for chit-chat.

For substantive work-related asks, set next_steps to 2-4 short, copyable lines. Each should name a concrete Nexa action where possible, e.g.:
- run a web positioning review on &lt;domain&gt;
- run a dev task: &lt;short implementation ask&gt;
- export the reply as a PDF deliverable when that fits
- read and summarize https://… with sources
Use null for next_steps for trivial, one-line, or pure emotional / venting messages.
When next_steps is non-empty, do not also paste the same "Next steps" list inside message — the host app will append it.

Return JSON with keys: message, should_ask_followup, followup_question, suggested_microstep, next_steps."""

NUDGE_PROMPT = """Write a low-pressure nudge for a user who has not done the task yet.

Context:
- focus_task is already selected — make the next move feel easy
- optionally set suggested_microstep
- avoid shame, pressure, and repetitive motivational clichés

Vary phrasing. Do not always start with "Try this". Sometimes start with:
- "Just do this:"
- "Start small:"
- "Here's an easy entry point:"

Always answer the user's question before redirecting. Do not reuse the same sentence structure as previous responses.

Return JSON with keys: message, should_ask_followup (usually false), followup_question (null), suggested_microstep, next_steps (null)."""

UNSTICK_PROMPT = """Write a reply for a user who feels stuck.

Context:
- if focus_task exists, shrink it into a tiny first move (optional suggested_microstep)
- if no focus_task, ask what they are trying to work on
- reduce pressure; make the task feel approachable

Vary how you open — do not always use the same one-line opener. Do not always start with "Try this".

Always answer the user's question before redirecting. Do not reuse the same sentence structure as previous responses.

Return JSON with keys: message, should_ask_followup, followup_question, suggested_microstep, next_steps (null)."""

COMPLETION_ACK_PROMPT = """The user just said they completed something (a task, errand, or a small step).

Write a short, warm acknowledgment. No interrogation, no new homework, no focus task list.
If they seem low-key, match that energy. You may offer an open door ("when you want the next step") but do not push.

Return JSON with keys: message, should_ask_followup (usually false), followup_question (null), suggested_microstep (null), next_steps (null)."""

CLARIFY_PROMPT = """Write a natural reply.

Important:
- Answer the user's actual question FIRST.
- Do not ignore the question.
- Do not redirect before you've answered.
- You are a business co-pilot, not a generic Q&A: when the user is steering toward a goal, reflect that goal briefly, suggest a practical approach, and (when it fits) offer a compact step view — but never force a template on a simple, closed question.

Rules by case:
1. Capability questions (can you do X?):
   - Answer honestly.
   - If yes: say how, lightly and realistically.
   - If not really: say so naturally.
   - For short, narrow questions ("can you read links?"), keep the reply short; set next_steps to null.
2. Correction: acknowledge briefly. Fix your answer. No defensiveness. next_steps: null. Do not extract tasks.
3. General: be helpful, not generic documentation. Use conversation context (if present) so you continue the same thread (e.g. marketing, a URL) instead of resetting.

When the user implies a business goal (launch, market, analyze a site, plan, ship, GTM, positioning, product, strategy) or references a public URL/domain:
- Lead with a clear, opinionated but honest answer; hedge only briefly when the facts are weak.
- Optionally add a short **Insight** in the main message (bullets: what is strong, what is missing, what is unclear) — only when it improves substance.
- Set next_steps to 2-4 short, copyable lines. Examples of shape (adjust to the actual topic):
  - analyze positioning for example.com
  - summarize https://example.com with sources
  - turn the answer into a short PDF-style deliverable when useful
  - decide one product tradeoff in a sentence
- When the user clearly commits ("yes, do that", "go ahead", "run with it"), reply with the clearest plain-language next move instead of stalling.
- If the user message is trivial (thanks, ok, hi), or the user only wanted a one-line fact, set next_steps to null.
- When next_steps is non-empty, do not duplicate a full "Next steps" section inside the main message body — the client appends next_steps; keep the body focused on the answer and insight.

You may use brief human hooks when natural ("Yeah —", "Fair question.", "Honestly,") — do not over-bullet unless the user wants structure. Do not sound like documentation.

Always answer the user's question before redirecting. Do not reuse the same sentence structure as previous responses.

intent (capability_question, correction, general_chat) is a hint from the app.

Return JSON with keys: message, should_ask_followup (usually false), followup_question (null), suggested_microstep (null), next_steps (array 0-4, or null)."""


NUDGE_PROMPT_EXTRA = """

If the user has failed the same focus multiple times (see is_stuck_loop / focus_attempts):
- acknowledge it lightly, no shame
- make the step extremely small
- change your approach slightly from a generic nudge"""

UNSTICK_PROMPT_EXTRA = """

If is_stuck_loop is true:
- explicitly acknowledge the loop in human words (short)
- reduce the task to the smallest possible action (almost trivial)
- keep warmth without sounding clinical"""

NUDGE_PROMPT_FULL = NUDGE_PROMPT + NUDGE_PROMPT_EXTRA
UNSTICK_PROMPT_FULL = UNSTICK_PROMPT + UNSTICK_PROMPT_EXTRA

# Appended for intent stuck_dev (tooling / build / deploy / config snags)
STUCK_DEV_COMPOSER_EXTRA = """

This turn is **stuck_dev**: the user is blocked on a technical problem (build, test, error output, deploy, config, K8s/EKS, Docker, CI, DB/OIDC, etc.).
- Give a **short** diagnosis-style outline: reproduce → isolate → fix → verify (adapt to what they said).
- If the stack is hinted (e.g. Mongo, OIDC, Kubernetes), name likely failure modes in plain language — no dashboard tone.
- Offer execution plainly: they can have Nexa run a **development task** on their workspace after approval — one sentence, not a manual.
- Keep **next_steps** to 2–4 concrete lines when useful (commands or checks); otherwise null.
"""


def _conversation_context_block(ctx: ResponseContext) -> str:
    if (
        not ctx.recent_messages
        and not (ctx.active_topic or "").strip()
        and not (ctx.conversation_summary or "").strip()
    ):
        return ""
    try:
        snippet = json.dumps(
            {
                "active_topic": ctx.active_topic,
                "summary": (ctx.conversation_summary or "")[:800],
                "recent_messages": ctx.recent_messages[-6:],
                "active_topic_confidence": ctx.active_topic_confidence,
                "manual_topic_override": ctx.manual_topic_override,
            },
            ensure_ascii=False,
        )[:4000]
    except (TypeError, ValueError):
        snippet = ""
    if not snippet.strip():
        return ""
    extra = ""
    if ctx.manual_topic_override:
        extra = "\n- The user has explicitly locked the current topic. Follow active_topic; do not blend in unrelated prior subjects from earlier turns."
    return f"""Conversation context (use to resolve short references: “it”, “this app”, “the project”, “the bot”, “the dev loop”, “that feature”):
{snippet}

Rules:
- If this context makes the user’s ask clear, do not ask them to re-explain the subject.
- Do not claim access to private systems beyond what the app already stores here.{extra}"""


def _user_behavior_block(ctx: ResponseContext) -> str:
    pref_line = "none yet"
    if ctx.user_preferences:
        try:
            pref_line = json.dumps(ctx.user_preferences, ensure_ascii=False)
        except (TypeError, ValueError):
            pref_line = str(ctx.user_preferences)
    return f"""User behavior context:
- focus_attempts: {ctx.focus_attempts}
- is_stuck_loop: {ctx.is_stuck_loop}
- user_preferences: {pref_line}
- memory_enabled: {ctx.memory_enabled}
- memory_note_count: {ctx.memory_note_count}

Rules:
- If is_stuck_loop is true: shrink the task more than usual, reduce pressure, acknowledge repetition briefly in plain language.
- If preferences suggest avoiding phone calls, prefer a text or email as a first move when relevant.
- Subtle phrasing is OK ("this has been hard to start", "you've tried this a couple times"). Never: "I tracked you", "your data shows", "based on your history."
- If focus_attempts is 2 or higher, make the next step even smaller."""


JSON_SUFFIX = (
    "\n\nRespond with a single JSON object only, with keys: "
    "message (string), should_ask_followup (boolean), "
    "followup_question (string or null), suggested_microstep (string or null), "
    "next_steps (array of 0-4 short strings, or null). Use next_steps as described in the task prompt; "
    "otherwise null."
)


def _parse_json_object_from_llm(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    return json.loads(raw)


def _parse_composer_response_text(response_text: str) -> dict[str, Any]:
    try:
        return _parse_json_object_from_llm(response_text)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("JSON_PARSE_FAILED raw=%s err=%s", response_text[:200], e)
        raise


def _get_clients() -> tuple:
    s = get_settings()
    m = get_merged_api_keys()
    anth = (
        build_anthropic_client(api_key=m.anthropic_api_key) if m.anthropic_api_key else None
    )
    oai = build_openai_client(api_key=m.openai_api_key) if m.openai_api_key else None
    return s, anth, oai


def _system_memory_block() -> str:
    try:
        from app.services.safe_llm_gateway import read_safe_system_memory_snapshot

        snapshot = read_safe_system_memory_snapshot()
    except Exception:  # noqa: BLE001
        logger.debug("system memory snapshot unavailable", exc_info=True)
        return ""

    sm = (snapshot.soul or "").strip()
    mm = (snapshot.memory or "").strip()
    if not sm and not mm:
        return ""

    return f"""Nexa persistent identity and memory:

<soul.md>
{sm}
</soul.md>

<memory.md>
{mm}
</memory.md>

Rules:
- Use this as durable context.
- Do not quote it unless relevant.
- Do not treat secrets as memory.
- If memory conflicts with the current user instruction, ask or prioritize the latest explicit instruction."""


def _build_system_prompt(ctx: ResponseContext, strategy_body: str) -> str:
    from app.services.brand_voice import NEXA_BRAND_PROMPT

    voice = get_voice_instruction(ctx.voice_style)
    pref_extra = preference_formatting_system_instructions()
    id_pr = identity_pronoun_system_instructions()
    parts: list[str] = [
        NEXA_BRAND_PROMPT,
        BASE_SYSTEM_PROMPT,
        _system_memory_block(),
        id_pr,
        pref_extra,
        voice,
        MICRO_PERSONALITY_MOVES,
        ANSWER_FIRST_RULE,
        ACTION_ORIENTED_RULE,
        PHASE50_CONFIDENT_EXEC_RULE,
        STRUCTURE_VARIATION_RULE,
        VARIATION_RULE,
        LIST_FORMATTING_LLM_GUIDANCE,
        _conversation_context_block(ctx),
        _user_behavior_block(ctx),
        strategy_body,
        structured_system_suffix_for_nexa_composer(ctx),
    ]
    return "\n\n".join(p for p in parts if p)


def _invoke_llm(system: str, user_content: str) -> dict[str, Any]:
    settings, anth_client, oai_client = _get_clients()
    m = get_merged_api_keys()
    if anth_client:
        try:
            logger.warning("LLM_CALL_TRIGGERED provider=anthropic")
            msg = anth_client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                temperature=0.8,
                system=system,
                messages=[{"role": "user", "content": user_content}],
            )
            try:
                record_anthropic_message_usage(
                    msg,
                    model=settings.anthropic_model,
                    used_user_key=m.has_user_anthropic,
                )
            except Exception:  # noqa: BLE001
                pass
            parts: list[str] = []
            for block in msg.content:
                t = getattr(block, "text", None)
                if t:
                    parts.append(t)
            body = "".join(parts) if parts else "{}"
            return _parse_composer_response_text(body)
        except Exception as exc:
            logger.warning("Anthropic composer failed: %s", exc)
    if oai_client:
        try:
            logger.warning("LLM_CALL_TRIGGERED provider=openai")
            resp = oai_client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.8,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            )
            try:
                record_openai_message_usage(
                    resp,
                    model=settings.openai_model,
                    used_user_key=m.has_user_openai,
                )
            except Exception:  # noqa: BLE001
                pass
            body = resp.choices[0].message.content or "{}"
            return _parse_composer_response_text(body)
        except Exception as exc:
            logger.warning("OpenAI composer failed: %s", exc)
    raise RuntimeError("No LLM available or both providers failed")


def _apply_single_agent_output_guard(text: str | None) -> str | None:
    """
    Last-resort safety: never ship “single agent” (legacy identity) to the user.
    Replaces the phrase (case-insensitive) with the correct product model.
    """
    if not text or "single agent" not in text.lower():
        return text
    return re.sub(
        re.compile(r"\bsingle agent\b", re.IGNORECASE),
        "multi-agent system",
        text,
    )


def _apply_composed_identity_guards(
    comp: ComposedResponse, *, user_message: str | None = None
) -> ComposedResponse:
    msg = _apply_single_agent_output_guard(comp["message"]) or comp["message"]
    if user_message:
        msg = maybe_apply_single_plain_cursor_block(msg, user_message)
    fq = _apply_single_agent_output_guard(comp.get("followup_question"))
    ms = _apply_single_agent_output_guard(comp.get("suggested_microstep"))
    return {
        "message": msg,
        "should_ask_followup": comp["should_ask_followup"],
        "followup_question": fq,
        "suggested_microstep": ms,
        "next_steps": comp.get("next_steps"),
    }


def validate_composed_response(data: dict[str, Any]) -> ComposedResponse | None:
    message = str(data.get("message", "")).strip()
    if not message:
        return None
    should_ask = bool(data.get("should_ask_followup", False))
    followup = data.get("followup_question")
    if followup is not None:
        followup = str(followup).strip() or None
    micro = data.get("suggested_microstep")
    if micro is not None:
        micro = str(micro).strip() or None
    if should_ask and not followup:
        should_ask = False
    ns: list[str] | None = None
    raw_ns = data.get("next_steps")
    if raw_ns is not None:
        if isinstance(raw_ns, list):
            cleaned: list[str] = []
            for x in raw_ns:
                s = str(x).strip()[:200]
                if s:
                    cleaned.append(s)
                if len(cleaned) >= 4:
                    break
            ns = cleaned or None
        else:
            ns = None
    return {
        "message": message,
        "should_ask_followup": should_ask,
        "followup_question": followup,
        "suggested_microstep": micro,
        "next_steps": ns,
    }


def use_real_llm() -> bool:
    s = get_settings()
    if not s.use_real_llm:
        return False
    m = get_merged_api_keys()
    return bool(m.anthropic_api_key or m.openai_api_key)


def fallback_capability_response(text: str) -> str:
    from app.services.research_capability_copy import (
        format_research_capability_message,
        is_research_capability_question,
    )

    if is_research_capability_question(text):
        return format_research_capability_message()
    t = text.lower()
    if "memory" in t or "remember" in t or "forget" in t:
        return (
            "Yes — in this app I can use local memory, active tasks, and saved preferences. "
            "You can ask me to remember something, show memory, or forget it later."
        )
    if "design" in t:
        return (
            "I can help a bit with ideas or feedback, but I’m not a full design tool. "
            "I’m better at helping you organize, decide what to do next, and get unstuck."
        )
    if "code" in t or "coding" in t:
        return (
            "Nexa routes that kind of work: the **Developer** agent and local dev loop handle code changes "
            "when you queue a job. I can also help you decide what to ask for first."
        )
    return (
        "Nexa is a multi-agent system: I can help you sort priorities and next steps, "
        "and route deeper work to the right specialist (e.g. code to Developer, quality to QA) when that fits."
    )


def _hash_pick(seed: str, options: list[str]) -> str:
    h = sum(ord(c) for c in seed) if seed else 0
    return options[h % len(options)]


def fallback_compose_response(
    ctx: ResponseContext, *, reason: str = "fallback"
) -> ComposedResponse:
    from app.services.legacy_behavior_utils import generate_microstep
    from app.services.telegram_onboarding import clarify_general_response

    logger.error("FALLBACK_TRIGGERED behavior=%s reason=%s", ctx.behavior, reason)
    b = ctx.behavior
    raw = (ctx.user_message or "").strip()
    tlow = raw.lower()
    if b == "clarify":
        if ctx.intent == "correction":
            return {
                "message": (
                    "You’re right — I sidestepped that. What were you going for? I’ll answer directly, "
                    "and I won’t turn it into a plan unless you list tasks you want organized."
                ),
                "should_ask_followup": False,
                "followup_question": None,
                "suggested_microstep": None,
                "next_steps": None,
            }
        if ctx.intent == "capability_question":
            return {
                "message": fallback_capability_response(raw),
                "should_ask_followup": False,
                "followup_question": None,
                "suggested_microstep": None,
                "next_steps": None,
            }
        return {
            "message": clarify_general_response(),
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "completion":
        return {
            "message": _hash_pick(
                ctx.user_message,
                [
                    "Nice — that counts. You can pick up the next small thing whenever you want.",
                    "Good. Even one thing finished in a heavy week is real progress.",
                    "Got it. Rest a second if you can; I’m here when you want the next tiny step.",
                ],
            ),
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "unstick" and ctx.intent == "stuck_dev":
        return {
            "message": (
                "Sounds like a build or tooling snag.\n\n"
                "Paste the shortest error or failing command, note what changed before it broke, "
                "and I’ll outline a tight fix path. If you want execution on your workspace, say so — "
                "development tasks run after approval."
            ),
            "should_ask_followup": True,
            "followup_question": "Want me to narrow down repro first, or sketch the patch sequence?",
            "suggested_microstep": None,
            "next_steps": [
                "paste command + first lines of stderr",
                "note dependency / config change before it broke",
            ],
        }
    if b == "unstick" and ctx.focus_task:
        if ctx.is_stuck_loop or ctx.focus_attempts >= 2:
            micro = _hash_pick(
                ctx.user_message,
                [
                    (
                        f"Okay — this one’s been hard to start. For ‘{ctx.focus_task}’, don’t “work” on it yet. "
                        "Open it, look for ~10 seconds, then close. That’s enough for today."
                    ),
                    (
                        f"This has been a sticking point. Smallest possible move: open ‘{ctx.focus_task}’ only. "
                        "You don’t have to change anything."
                    ),
                ],
            )
        else:
            micro = _hash_pick(
                ctx.user_message,
                [
                    f"Open ‘{ctx.focus_task}’ and do the smallest bit you can. That’s enough to break the freeze.",
                    f"For ‘{ctx.focus_task}’: one tiny action, two minutes, then you can stop.",
                    f"Get into ‘{ctx.focus_task}’ in whatever way is easiest; you don’t have to finish anything yet.",
                ],
            )
        return {
            "message": micro,
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "unstick":
        return {
            "message": (
                "What are you actually trying to work on? Even one sentence helps — "
                "I’ll help you make the next move smaller."
            ),
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "reduce" and ctx.selected_tasks:
        head = _hash_pick(
            ctx.user_message,
            [
                "Here’s a tighter set to focus on:",
                "Narrowing to what matters most first:",
                "These are the moves I’d line up for you right now:",
            ],
        )
        lines = [head, ""]
        for i, task in enumerate(ctx.selected_tasks[:3], start=1):
            lines.append(f"{i}. {task}")
        lines.append("")
        for note in ctx.deferred_lines:
            lines.append(note)
            lines.append("")
        lines.append("You don’t have to do all of it today — just what you can face next.")
        return {
            "message": "\n".join(lines).strip(),
            "should_ask_followup": True,
            "followup_question": "Which one feels easiest to start right now?",
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "assist" and ctx.has_active_plan and ctx.focus_task:
        step = generate_microstep(ctx.focus_task)
        return {
            "message": _hash_pick(
                ctx.user_message,
                [
                    f"Got you — a concrete nudge: {step}\n\nIf that still feels big, I can make it smaller.",
                    f"Here’s one way in: {step}\n\nWant an even smaller step than that?",
                ],
            ),
            "should_ask_followup": True,
            "followup_question": "Which one feels easiest to start right now?",
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "assist":
        return {
            "message": _hash_pick(
                ctx.user_message,
                [
                    "If you list what’s on your mind — even messy — I can turn that into 1–3 next steps you can stand.",
                    "When you’re ready, dump what you’re holding in your head; I’ll help you find the smallest way forward.",
                ],
            ),
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    if b == "nudge":
        task = ctx.focus_task or "that task"
        step = generate_microstep(task)
        prefs = ctx.user_preferences or {}
        avoids = prefs.get("learned:avoids_calls", "").lower() in (
            "true",
            "yes",
            "1",
        ) or prefs.get("learned:avoids_phone", "").lower() in ("true", "yes", "1")
        tlow = task.lower()
        if avoids and any(x in tlow for x in ("call", "phone")):
            step = _hash_pick(
                ctx.user_message,
                [
                    f"Could you send a short text or voice note about ‘{task}’ instead of a call? One line is enough.",
                    f"If a call feels like a lot, start with a two-line message about ‘{task}’ and leave it at that.",
                ],
            )
        if ctx.is_stuck_loop or ctx.focus_attempts >= 2:
            msg = _hash_pick(
                ctx.user_message,
                [
                    f"Yeah — you’ve tried this a couple times. Let’s go smaller: just open the thing for ‘{task}’. Don’t improve it yet.\n{step}",
                    f"This has been hard to start. Tiniest version: {step} Stop right after; no quality bar.",
                ],
            )
        else:
            msg = _hash_pick(
                ctx.user_message,
                [
                    f"Start small: {step}\nThat can be the whole move for now.",
                    f"Easy entry: {step}\nYou can stop right after that.",
                ],
            )
        return {
            "message": msg,
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": None,
        }
    return {
        "message": "When you can, send what’s floating around in your head; I’ll help you boil it down to a doable next step.",
        "should_ask_followup": False,
        "followup_question": None,
        "suggested_microstep": None,
        "next_steps": None,
    }


def _composer_user_payload_json(ctx: ResponseContext) -> str:
    tier = getattr(ctx, "prompt_budget_tier", 2)
    if tier == 0:
        return json.dumps({"user_message": ctx.user_message}, ensure_ascii=False)
    if tier == 1:
        p = composer_context_to_safe_llm_payload(ctx)
        slim: dict[str, Any] = {
            "user_message": p.get("user_message"),
            "intent": p.get("intent"),
            "behavior": p.get("behavior"),
        }
        cc = p.get("conversation_context")
        if isinstance(cc, dict):
            rm = cc.get("recent_messages") or []
            if isinstance(rm, list) and rm:
                slim["recent_messages"] = rm[-4:]
        return json.dumps(slim, ensure_ascii=False)
    return json.dumps(composer_context_to_safe_llm_payload(ctx), ensure_ascii=False)


def _run_strategy(ctx: ResponseContext, strategy_body: str) -> ComposedResponse:
    from app.services.llm_usage_context import push_llm_action

    with push_llm_action(source="response_composer", action_type="chat_response", agent_key="nexa"):
        system = _build_system_prompt(ctx, strategy_body)
        user_content = _composer_user_payload_json(ctx) + JSON_SUFFIX
        try:
            data = _invoke_llm(system, user_content)
            validated = validate_composed_response(data)
            if validated:
                return validated
            logger.warning(
                "compose strategy empty message after parse behavior=%s", ctx.behavior
            )
        except Exception as exc:
            logger.warning("compose strategy failed: %s", exc)
        return fallback_compose_response(
            ctx, reason="llm_failed_empty_or_invalid_json"
        )


def compose_reduce_response(ctx: ResponseContext) -> ComposedResponse:
    return _run_strategy(ctx, REDUCE_PROMPT)


def compose_assist_response(ctx: ResponseContext) -> ComposedResponse:
    return _run_strategy(ctx, ASSIST_PROMPT)


def compose_nudge_response(ctx: ResponseContext) -> ComposedResponse:
    return _run_strategy(ctx, NUDGE_PROMPT_FULL)


def compose_unstick_response(ctx: ResponseContext) -> ComposedResponse:
    body = UNSTICK_PROMPT_FULL
    if (ctx.intent or "").strip() == "stuck_dev":
        body = UNSTICK_PROMPT_FULL + STUCK_DEV_COMPOSER_EXTRA
    return _run_strategy(ctx, body)


def compose_clarify_response(ctx: ResponseContext) -> ComposedResponse:
    if ctx.intent == "capability_question":
        from app.services.research_capability_copy import (
            format_research_capability_message,
            is_research_capability_question,
        )

        if is_research_capability_question(ctx.user_message or ""):
            return {
                "message": format_research_capability_message(),
                "should_ask_followup": False,
                "followup_question": None,
                "suggested_microstep": None,
                "next_steps": None,
            }
    return _run_strategy(ctx, CLARIFY_PROMPT)


def compose_completion_response(ctx: ResponseContext) -> ComposedResponse:
    return _run_strategy(ctx, COMPLETION_ACK_PROMPT)


def compose_response(ctx: ResponseContext) -> ComposedResponse:
    ur = use_real_llm()
    logger.warning(
        "COMPOSER_USED behavior=%s use_real_llm=%s",
        ctx.behavior,
        ur,
    )
    if not ur:
        return _apply_composed_identity_guards(
            fallback_compose_response(
                ctx, reason="llm_disabled_or_missing_api_key"
            ),
            user_message=ctx.user_message,
        )
    try:
        if ctx.behavior == "reduce":
            res = compose_reduce_response(ctx)
        elif ctx.behavior == "assist":
            res = compose_assist_response(ctx)
        elif ctx.behavior == "completion":
            res = compose_completion_response(ctx)
        elif ctx.behavior == "nudge":
            res = compose_nudge_response(ctx)
        elif ctx.behavior == "unstick":
            res = compose_unstick_response(ctx)
        else:
            res = compose_clarify_response(ctx)
        return _apply_composed_identity_guards(res, user_message=ctx.user_message)
    except Exception as exc:
        logger.exception("compose_response: %s", exc)
        return _apply_composed_identity_guards(
            fallback_compose_response(ctx, reason="compose_response_exception"),
            user_message=ctx.user_message,
        )


def append_microstep_if_useful(text: str, composed: ComposedResponse) -> str:
    ms = composed.get("suggested_microstep")
    if not ms:
        return text
    if ms.lower() in text.lower():
        return text
    return text + "\n\n" + ms
