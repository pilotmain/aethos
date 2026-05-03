"""Legacy behavior / LLM reply composition (``build_response`` and helpers).

Phase 36: user-facing entry is :class:`~app.services.gateway.runtime.NexaGateway`; this module
remains the internal text composition layer. Prefer :meth:`~app.services.gateway.runtime.NexaGateway.compose_llm_reply`
from orchestrators instead of importing ``build_response`` directly.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.services.agent_router import (
    format_active_agent_projection,
    infer_active_agents_from_text,
    should_emit_active_agent_projection,
)
from app.services.command_help import format_command_help_response
from app.services.intent_classifier import is_command_question
from app.services.memory_service import MemoryService
from app.services.multi_agent_routing import (
    is_multi_agent_capability_question,
    reply_multi_agent_capability_clarification,
)
from app.services.orchestrator_service import OrchestratorService
from app.services.research_capability_copy import (
    format_research_capability_message,
    is_research_capability_question,
)
from app.services.telegram_onboarding import capability_response, clarify_general_response

logger = logging.getLogger(__name__)


def _decisive_skip_plan_followup(intent: str) -> bool:
    from app.services.execution_trigger import should_use_decisive_dev_tone

    return should_use_decisive_dev_tone(intent)


QUESTION_BACK_SUFFIX = "\n\nWhich one feels easiest to start right now?"

BEHAVIORS = [
    "plan",
    "assist",
    "nudge",
    "reduce",
    "clarify",
    "unstick",
    "completion",
]


class Context:
    def __init__(
        self,
        user_id: str,
        tasks: list[str],
        last_plan: list[str],
        memory: dict,
        focus_attempts: int = 0,
        is_stuck_loop: bool = False,
        user_preferences: dict | None = None,
        memory_note_count: int = 0,
    ) -> None:
        self.user_id = user_id
        self.tasks = tasks
        self.last_plan = last_plan
        self.memory = memory
        self.focus_attempts = focus_attempts
        self.is_stuck_loop = is_stuck_loop
        self.user_preferences = user_preferences or {}
        self.memory_note_count = int(memory_note_count)

    @property
    def has_active_plan(self) -> bool:
        return bool(self.last_plan)

    @property
    def focus_task(self) -> str | None:
        if self.last_plan:
            return self.last_plan[0]
        return None


def build_context(
    db: Session,
    user_id: str,
    memory_service: MemoryService,
    orchestrator: OrchestratorService,
) -> Context:
    from app.services.loop_tracking_service import detect_stuck_loop, touch_user_interaction

    prefs = memory_service.get_preferences(db, user_id)
    learned = memory_service.get_learned_preferences(db, user_id)
    notes = memory_service.list_notes(db, user_id)
    memory = {
        "planning_style": prefs.planning_style,
        "user_preferences": learned,
        "memory_enabled": True,
        "memory_note_count": len(notes),
    }
    today = date.today()
    rows = orchestrator.tasks.list_today(db, user_id, today)
    tasks = [t.title for t in rows]
    plan_data = orchestrator.get_today_plan(db, user_id)
    last_plan = [t.title for t in plan_data["tasks"]] if plan_data else []
    user_row = orchestrator.users.get(db, user_id)
    focus = last_plan[0] if last_plan else None
    is_loop = bool(user_row) and detect_stuck_loop(user_row, focus)
    att = int(user_row.focus_attempts) if user_row else 0
    if user_row:
        touch_user_interaction(db, user_row)
    return Context(
        user_id=user_id,
        tasks=tasks,
        last_plan=last_plan,
        memory=memory,
        focus_attempts=att,
        is_stuck_loop=is_loop,
        user_preferences=learned,
        memory_note_count=len(notes),
    )


def map_intent_to_behavior(intent: str, _context: Context) -> str:
    if intent == "create_custom_agent":
        return "clarify"
    if intent in ("orchestrate_system", "external_investigation", "external_execution", "external_execution_continue"):
        return "assist"
    if intent == "brain_dump":
        return "reduce"
    if intent == "stuck_dev":
        return "unstick"
    if intent == "analysis":
        return "assist"
    if intent == "stuck":
        return "unstick"
    if intent == "status_update":
        return "completion"
    if intent == "help_request":
        return "assist"
    if intent == "followup_reply":
        return "nudge"
    if intent == "capability_question":
        return "clarify"
    if intent == "correction":
        return "clarify"
    return "clarify"


def generate_microstep(task: str) -> str:
    task_lower = task.lower()

    if any(x in task_lower for x in ["report", "project", "write", "doc"]):
        return f"Open the document for '{task}' and write one sentence."

    if any(x in task_lower for x in ["email", "emails"]):
        return "Open your inbox and reply to just one email."

    if any(x in task_lower for x in ["call", "phone"]):
        return f"Open your contacts and find the number for '{task}'."

    if any(x in task_lower for x in ["flight", "book", "travel"]):
        return "Open a flight search site and check prices once."

    if any(x in task_lower for x in ["groceries", "shopping"]):
        return "Write down the first 3 items you need."

    if any(x in task_lower for x in ["gym", "workout"]):
        return "Put on your workout clothes. You don't need to exercise yet."

    return f"Give yourself five minutes on ‘{task}’ — you can stop after that."


def no_tasks_response() -> str:
    return (
        "I need a little more context.\n\n"
        "Send me everything that feels like it's on your mind, and I'll simplify it."
    )


def reduce_behavior(plan_result: dict) -> str:
    tasks = plan_result["plan"]["tasks"]
    titles = [t.title for t in tasks]
    if not titles:
        return no_tasks_response()

    response = "Narrowing it down, I’d start with this:\n\n"
    response += f"1. {titles[0]}\n\n"

    if len(titles) > 1:
        response += f"2. {titles[1]}\n\n"
    if len(titles) > 2:
        response += f"3. {titles[2]}\n\n"

    for note in plan_result.get("deferred_lines") or []:
        response += f"{note}\n\n"

    response += "You don't need to handle everything today."
    return response


def unstick_behavior(context: Context) -> str:
    task = context.focus_task
    if not task:
        return (
            "Let's start simple.\n\n"
            "Tell me what you're trying to work on, "
            "and I'll help you break it down."
        )
    step = generate_microstep(task)
    return (
        "That's okay. You don't need to push through.\n\n"
        f"{step}\n"
        "You don't need to do more than that."
    )


def assist_behavior(context: Context) -> str:
    if context.has_active_plan:
        task = context.focus_task or "your task"
        step = generate_microstep(task)
        return f"Here’s a concrete nudge:\n\n{step}\n\nWant an even smaller step than that?"
    return (
        "List what’s on your mind when you can — I’ll help you turn that into 1–3 next steps you can stand."
    )


def nudge_behavior(context: Context) -> str:
    task = context.focus_task or "your task"
    step = generate_microstep(task)
    return f"{step}\nYou can stop right after."


def fallback_response() -> str:
    return clarify_general_response()


def handle_message(
    _text: str,
    intent: str,
    context: Context,
    plan_result: dict | None = None,
    behavior: str | None = None,
) -> str:
    b = behavior or map_intent_to_behavior(intent, context)

    if b == "reduce":
        if plan_result is None:
            raise ValueError("reduce behavior requires plan_result")
        return reduce_behavior(plan_result)

    if b == "unstick":
        return unstick_behavior(context)

    if b == "assist":
        return assist_behavior(context)

    if b == "nudge":
        return nudge_behavior(context)

    if b == "clarify":
        if intent == "capability_question":
            if is_research_capability_question(_text):
                return format_research_capability_message()
            return capability_response()
        return clarify_general_response()

    return fallback_response()


def add_question_back(response: str, behavior: str, context: Context) -> str:
    logger.info(
        "add_question_back behavior=%s has_active_plan=%s",
        behavior,
        context.has_active_plan,
    )
    if behavior == "reduce" and context.has_active_plan:
        logger.info("add_question_back appended=true reason=reduce")
        return response + QUESTION_BACK_SUFFIX
    if behavior == "assist" and context.has_active_plan:
        logger.info("add_question_back appended=true reason=assist")
        return response + QUESTION_BACK_SUFFIX
    logger.info("add_question_back appended=false")
    return response


def apply_tone(text: str, memory: dict) -> str:
    """Gentle vs direct planning preference (no hardcoded "Start here" rewrites)."""
    _ = memory  # style may be used for future tone tweaks; keep param for callers
    return text


def _plan_result_fields(plan_result: dict | None) -> tuple[list[str], list[str], str | None]:
    if not plan_result:
        return [], [], None
    plan = plan_result.get("plan")
    tasks = (plan or {}).get("tasks") if plan else None
    titles: list[str] = []
    if tasks:
        titles = [getattr(t, "title", str(t)) for t in tasks]
    deferred = list(plan_result.get("deferred_lines") or [])
    detected = plan_result.get("detected_state")
    return titles, deferred, detected


def build_response(
    text: str,
    intent: str,
    context: Context,
    plan_result: dict | None = None,
    db: Session | None = None,
    app_user_id: str | None = None,
    *,
    conversation_snapshot: dict | None = None,
    routing_agent_key: str | None = None,
    response_kind: str | None = None,
) -> str:
    from app.services.execution_truth_state import reset_execution_truth_counters

    reset_execution_truth_counters()

    from app.services.copilot_next_steps import (
        format_next_steps_block,
        should_append_next_steps,
    )
    from app.services.owner_identity_faq import (
        try_canned_nexa_product_faq,
        try_canned_owner_identity_faq,
    )
    from app.services.prompt_budget import classify_prompt_budget_tier
    from app.services.response_composer import (
        ResponseContext,
        append_microstep_if_useful,
        compose_response,
        resolve_voice_style,
    )
    from app.services.response_formatter import finalize_user_facing_text

    uprefs = context.user_preferences

    from app.services.response_sanitizer import sanitize_execution_and_assignment_reply

    def _out(s: str) -> str:
        s2 = sanitize_execution_and_assignment_reply(
            s,
            user_text=(text or "").strip(),
            related_job_ids=[],
            permission_required=None,
        )
        return finalize_user_facing_text(s2, user_preferences=uprefs)

    snap = conversation_snapshot or {}
    behavior = map_intent_to_behavior(intent, context)
    logger.info(
        "build_response intent=%s behavior=%s has_active_plan=%s",
        intent,
        behavior,
        context.has_active_plan,
    )
    if is_command_question(text):
        r = apply_tone(format_command_help_response(), context.memory)
        return _out(r)
    if intent == "orchestrate_system" and db is not None and (app_user_id or "").strip():
        from app.services.orchestrator_status_reply import format_orchestrator_mc_snapshot

        return _out(format_orchestrator_mc_snapshot(db, str(app_user_id).strip()))
    if intent == "orchestrate_system":
        return _out(
            "Open **Mission Control** in the web app for live mission, task, and dev-run status. "
            "When you’re signed in through chat, I can pull the same snapshot for your user id."
        )
    if intent == "external_execution_continue":
        return _out(
            "Recorded — say **retry external execution** or paste logs/output when you want me to pick up "
            "the Railway/repo investigation again."
        )
    if intent == "external_execution":
        from app.services.external_execution_access import (
            assess_external_execution_access,
            format_external_execution_access_reply,
            should_gate_external_execution,
        )
        from app.services.external_execution_session import mark_external_execution_awaiting_followup

        access = assess_external_execution_access(db, app_user_id)
        gated = should_gate_external_execution(text, access)
        if gated:
            body = format_external_execution_access_reply(access, user_text=text)
        else:
            ready = (
                "Access signals look sufficient on this worker for coordinated repo work and scripted deploy checks. "
                "I will only report deploy or health outcomes **after** real commands succeed — nothing is finished "
                "until verification runs.\n\n"
            )
            if db is not None and (app_user_id or "").strip():
                from app.services.orchestrator_status_reply import format_orchestrator_mc_snapshot

                body = ready + format_orchestrator_mc_snapshot(db, str(app_user_id).strip())
            else:
                body = ready.strip()
        out = _out(body)
        mark_external_execution_awaiting_followup(db, app_user_id, None, gated=gated)
        return out
    if intent == "external_investigation" and db is not None and (app_user_id or "").strip():
        from app.services.orchestrator_status_reply import format_orchestrator_mc_snapshot

        intro = (
            "I can’t log into your cloud provider (e.g. Railway) from this session unless you’ve "
            "connected API/CLI access. Below is **Nexa-side** activity (missions/dev runs) — it may not "
            "reflect the host dashboard if nothing was recorded.\n\n"
        )
        return _out(intro + format_orchestrator_mc_snapshot(db, str(app_user_id).strip()))
    if intent == "external_investigation":
        return _out(
            "I don’t have your hosted service credentials here. Share the error text, deploy id, or "
            "what the provider UI shows, and I’ll help you triage—or connect access safely if you want "
            "hands-on runs."
        )
    if is_multi_agent_capability_question((text or "").strip()):
        return _out(reply_multi_agent_capability_clarification())
    if intent == "create_custom_agent" and db is not None and (app_user_id or "").strip():
        from app.services.custom_agent_creation import parse_creation_spec, run_create_custom_agent_flow
        from app.services.custom_agent_routing import is_create_custom_agent_request
        from app.services.custom_agents import (
            create_custom_agent_from_prompt,
            try_conversational_create_custom_agents,
        )

        uid = str(app_user_id).strip()
        if is_create_custom_agent_request(text):
            return _out(create_custom_agent_from_prompt(db, user_id=uid, prompt=text))
        if parse_creation_spec(text) is not None:
            r = run_create_custom_agent_flow(db, uid, text)
            return _out(r)
        conv = try_conversational_create_custom_agents(db, uid, text)
        if conv is not None:
            return _out(conv)
        r = run_create_custom_agent_flow(db, uid, text)
        return _out(r)
    if should_emit_active_agent_projection(intent, text):
        agents = infer_active_agents_from_text(text)
        at = (snap.get("active_topic") or None) or None
        projection = format_active_agent_projection(agents, active_topic=at)
        follow = (
            "\n\nTell me what you want to move forward and I'll expand this into a full workflow."
        )
        r = apply_tone(projection + follow, context.memory)
        return _out(r)
    canned_prod = try_canned_nexa_product_faq((text or "").strip())
    if canned_prod is not None:
        return _out(canned_prod)
    canned = try_canned_owner_identity_faq(
        (text or "").strip(), user_preferences=uprefs
    )
    if canned is not None:
        return _out(canned)
    selected_tasks, deferred_lines, detected_state = _plan_result_fields(plan_result)
    voice = resolve_voice_style(routing_agent_key, intent, conversation_snapshot)
    rk: str | None = None
    if response_kind is not None and str(response_kind).strip():
        rk = str(response_kind).strip()
    elif snap and snap.get("response_kind") is not None and str(snap.get("response_kind", "")).strip():
        rk = str(snap.get("response_kind")).strip()
    _tier = classify_prompt_budget_tier((text or "").strip(), intent=intent)
    response_ctx = ResponseContext(
        user_message=text,
        intent=intent,
        behavior=behavior,
        has_active_plan=context.has_active_plan,
        focus_task=context.focus_task,
        selected_tasks=selected_tasks,
        deferred_lines=deferred_lines,
        planning_style=context.memory.get("planning_style", "gentle"),
        detected_state=detected_state,
        voice_style=voice,
        focus_attempts=context.focus_attempts,
        is_stuck_loop=context.is_stuck_loop,
        user_preferences=context.user_preferences,
        memory_enabled=context.memory.get("memory_enabled", True),
        memory_note_count=context.memory.get("memory_note_count", 0),
        conversation_summary=(snap.get("summary") if snap else None),
        active_topic=(snap.get("active_topic") if snap else None),
        active_topic_confidence=(float(snap.get("active_topic_confidence", 0.5)) if snap else 0.5),
        manual_topic_override=bool(snap.get("manual_topic_override")) if snap else False,
        recent_messages=(snap.get("recent_messages") or [] if snap else []),
        routing_agent_key=routing_agent_key,
        response_kind=rk,
        prompt_budget_tier=_tier,
    )
    composed = compose_response(response_ctx)
    base = composed["message"]
    base = append_microstep_if_useful(base, composed)
    if composed["should_ask_followup"] and composed["followup_question"]:
        base += "\n\n" + composed["followup_question"]
    elif (
        behavior in ("reduce", "assist")
        and context.has_active_plan
        and not _decisive_skip_plan_followup(intent)
    ):
        base += QUESTION_BACK_SUFFIX
    base = apply_tone(base, context.memory)
    nxt = composed.get("next_steps")
    if should_append_next_steps(
        behavior,
        (text or "").strip(),
        nxt,
        assistant_text=base,
        intent=intent,
    ):
        block = format_next_steps_block(nxt or [])
        if block:
            base = f"{base}\n\n{block}"
        if db and app_user_id and nxt:
            from app.services.suggested_action_storage import save_suggested_actions_if_shown

            save_suggested_actions_if_shown(
                db, app_user_id, nxt, user_message=(text or "").strip() or None
            )
    if db and app_user_id and behavior in ("nudge", "unstick") and context.focus_task:
        from app.repositories.user_repo import UserRepository
        from app.services.loop_tracking_service import update_focus_after_nudge_or_unstick

        u = UserRepository().get(db, app_user_id)
        if u is not None:
            update_focus_after_nudge_or_unstick(db, u, context.focus_task)
    return _out(base)
