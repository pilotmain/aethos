import asyncio
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes

from app.bot.typing import typing_indicator
from app.core.config import get_settings, print_llm_debug_banner
from app.core.db import SessionLocal, ensure_schema
from app.schemas.agent_job import AgentJobCreate
from app.services import user_api_keys as user_api_key_service
from app.services.agent_job_service import AgentJobService
from app.services.agent_orchestrator import handle_agent_mention
from app.services.agent_router import route_agent
from app.services.agent_status_text import format_agents_status
from app.services.agent_telegram_copy import format_agents_list, format_command_center
from app.services.behavior_engine import (
    apply_tone,
    build_context,
    build_response,
    map_intent_to_behavior,
    no_tasks_response,
)
from app.services.channel_gateway.telegram_adapter import (
    get_telegram_adapter,
    register_telegram_handlers,
)
from app.services.checkin_service import CheckInService
from app.services.command_help import format_command_help_response
from app.services.conversation_context_service import (
    apply_topic_intent_to_context,
    build_context_snapshot,
    get_last_assistant_text,
    get_last_decision_from_context,
    get_or_create_context,
    set_pending_project,
    short_reply_for_topic_intent,
    update_context_after_turn,
)
from app.services.dev_orchestrator.dev_job_planner import (
    create_planned_dev_job,
    format_planned_dev_reply,
)
from app.services.dev_task_service import (
    build_cursor_instruction,
    is_cursor_request,
    is_dev_task_message,
    parse_dev_task,
)
from app.services.general_answer_service import answer_general_question
from app.services.general_response import (
    casual_capability_reply,
    is_casual_capability_question,
    is_simple_greeting,
    looks_like_general_question,
    simple_greeting_reply,
    strip_correction_prefix,
)
from app.services.handoff_tracking_service import HandoffTrackingService
from app.services.idea_intake import (
    build_pending_project_payload,
    extract_idea_summary,
    format_idea_draft_reply,
    is_create_project_confirmation,
    looks_like_new_idea,
    match_create_repo_request,
)
from app.services.idea_project_service import (
    commit_pending_idea_as_project,
    queue_create_repo_approval,
)
from app.services.idea_workflow_routing import (
    try_dev_scope_workflow,
    try_marketing_workflow,
    try_strategy_workflow,
)
from app.services.intent_classifier import get_intent, is_command_question
from app.services.learning_event_service import (
    approve as learning_approve,
)
from app.services.learning_event_service import (
    list_pending as learning_list_pending,
)
from app.services.learning_event_service import (
    reject as learning_reject,
)
from app.services.llm_request_context import (
    bind_llm_telegram,
    llm_telegram_context,
    unbind_llm_telegram,
)
from app.services.llm_usage_context import bind_llm_usage_telegram, unbind_llm_usage
from app.services.local_action_parser import parse_local_action
from app.services.loop_tracking_service import reset_focus_after_completion
from app.services.memory_aware_routing import apply_memory_aware_route_adjustment
from app.services.memory_service import MemoryService
from app.services.mention_control import map_catalog_key_to_internal, parse_mention
from app.services.ops_approval import process_ops_job_decision
from app.services.ops_handler import handle_nexa_ops_mention
from app.services.orchestrator_service import OrchestratorService
from app.services.startup_config_log import log_sanitized_nexa_config, maybe_log_llm_key_hint
from app.services.telegram_access_audit import log_access_denied
from app.services.telegram_memory_commands import handle_memory_command
from app.services.telegram_onboarding import (
    first_time_nexa_start_text,
    help_message,
    is_weak_input,
    start_message,
    start_message_for_role,
    weak_input_response,
)
from app.services.telegram_service import TelegramService
from app.services.user_capabilities import (
    ACCESS_RESTRICTED,
    BLOCKED_MSG,
    DEV_EXECUTION_RESTRICTED,
    can_list_dev_jobs_commands,
    can_memory_working_remember_forget,
    can_project_admin,
    can_read_dev_stack_commands,
    can_run_dev_agent_jobs,
    can_use_dev_doctor_or_git,
    can_write_global_memory_file,
    format_access_command_text,
    get_telegram_role,
    is_owner_role,
    is_trusted_or_owner,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _deny(
    db,
    *,
    telegram_id: int,
    app_user: str | None,
    uname: str | None,
    family: str,
    reason: str,
    preview: str | None = None,
) -> None:
    log_access_denied(
        db,
        app_user_id=app_user,
        telegram_id=telegram_id,
        username=uname,
        command_family=family,
        reason=reason,
        preview=preview,
    )


def _persist_conversation_turn(
    db,
    app_user_id: str,
    cctx,
    user_text: str,
    assistant_text: str,
    intent: str | None,
    agent_key: str,
    *,
    decision_extras: dict | None = None,
) -> None:
    from app.services.decision_summary import build_decision_for_telegram_turn

    try:
        dec = build_decision_for_telegram_turn(
            user_text=user_text,
            intent=intent,
            agent_key=agent_key or "nexa",
            extras=decision_extras or {},
        )
        update_context_after_turn(
            db,
            cctx,
            user_text=user_text,
            assistant_text=assistant_text,
            intent=intent,
            agent_key=agent_key,
            decision_summary=dec,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("conversation persist: %s", exc)

settings = get_settings()
telegram_service = TelegramService()
orchestrator = OrchestratorService()
checkin_service = CheckInService()
memory_service = MemoryService()
job_service = AgentJobService()
handoff_service = HandoffTrackingService()


def _extract_memory_command(text: str) -> tuple[str, str] | None:
    stripped = (text or "").strip()
    lowered = stripped.lower()

    remember_patterns = [
        r"^remember that\s+(.+)$",
        r"^remember\s+(.+)$",
        r"^save this\s+(.+)$",
    ]
    forget_patterns = [
        r"^forget about\s+(.+)$",
        r"^forget\s+(.+)$",
        r"^remove\s+(.+?)\s+from memory$",
        r"^delete\s+(.+?)\s+from memory$",
        r"^stop reminding me about\s+(.+)$",
    ]
    soul_patterns = [
        r"^update soul\s*:\s*(.+)$",
        r"^soul\s*:\s*(.+)$",
    ]

    for pattern in remember_patterns:
        match = re.match(pattern, lowered, re.IGNORECASE)
        if match:
            return ("remember", stripped[match.start(1) : match.end(1)].strip())

    for pattern in forget_patterns:
        match = re.match(pattern, lowered, re.IGNORECASE)
        if match:
            return ("forget", stripped[match.start(1) : match.end(1)].strip())

    for pattern in soul_patterns:
        match = re.match(pattern, lowered, re.IGNORECASE)
        if match:
            return ("soul", stripped[match.start(1) : match.end(1)].strip())

    return None


def _link_dev_loop_agent_run(db, app_user_id: str, job, ac: AgentJobCreate) -> None:
    from app.services.agent_run_service import create_run_for_dev_job

    try:
        create_run_for_dev_job(
            db,
            app_user_id=app_user_id,
            job=job,
            input_text=f"{ac.title}\n{ac.instruction}".strip(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("dev agent run link failed: %s", exc)


async def _reply_dev_job_queued_or_blocked(update, job) -> bool:
    """If blocked or needs_risk_approval, reply and return True (caller should return)."""
    st = job.status or ""
    if st == "blocked":
        await update.message.reply_text(
            f"I blocked this dev job for safety:\n{job.error_message or 'Policy blocked'}"
        )
        return True
    if st == "needs_risk_approval":
        await update.message.reply_text(
            f"Job #{job.id} may touch high-risk areas (see policy).\n\n"
            f"Reply: `approve high risk job #{job.id}`\n"
            f"Then: `approve job #{job.id}` to run the worker."
        )
        return True
    return False


def _git_job_diff_summary(job) -> str:
    import subprocess

    from app.services.handoff_paths import PROJECT_ROOT

    plj = dict(getattr(job, "payload_json", None) or {})
    bl = (plj.get("aider_baseline_for_diff") or plj.get("aider_baseline_head") or "").strip() or "HEAD^"
    root = str(PROJECT_ROOT)
    lines: list[str] = []
    for args in (
        ["git", "diff", "--stat", f"{bl}..HEAD"],
        ["git", "diff", "--name-only", f"{bl}..HEAD"],
    ):
        p = subprocess.run(
            args,
            cwd=root,
            text=True,
            capture_output=True,
        )
        if p.returncode == 0 and (p.stdout or "").strip():
            lines.append(" ".join(args) + ":\n" + (p.stdout or "")[:2500])
    if not lines:
        p2 = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=root,
            text=True,
            capture_output=True,
        )
        if p2.returncode == 0 and (p2.stdout or "").strip():
            lines.append("git diff --stat:\n" + (p2.stdout or "")[:2500])
    return "\n\n---\n\n".join(lines) if lines else "(no diff on this host / not a git checkout)"


def _split_telegram_text(body: str, max_len: int = 4000) -> list[str]:
    """Telegram max message length ~4096; split into fixed-size chunks."""
    if not body:
        return [""]
    return [body[i : i + max_len] for i in range(0, len(body), max_len)]


def _title_from_instruction(instruction: str, fallback: str = "Dev job") -> str:
    line = (instruction or "").split("\n", 1)[0].strip()
    return (line[:120] or fallback).strip() or fallback


# Commands that should use the dev executor (Codex / dev_job_*.md) — not the local .md-only tool path.
_DEV_EXECUTOR_COMMANDS = frozenset({"create-cursor-task", "prepare-fix"})

_AMBIGUOUS_STATUS_QUERY_RE = re.compile(
    r"(?i).*\b("
    r"is\s+(this|that|it|the)\b.+\b(done|ready|finished|over)\b|"
    r"done (already|yet)\??$|"
    r"finished yet\??$|"
    r"status\s+of(\s+this)?\s*(\b(update|it)\b|job)|"
    r"any\s+update|"
    r"what.*\b(happen(ing|ed)\b|status|state|progress)\b|"
    r"^(update|how)\b.+\b(job|task)\b"
    r")"
)
_JOB_INQUISY_RE = re.compile(
    r"(?i).*\b("
    r"status|update|progress|stuck|where|how|ask(ing|ed)\b|"
    r"done\??|failed|result|answer|happen(ing|ed)\b|any\b.+\b(update|status)|\bno\b.+\brecord|"
    r"what.+(happen|go(ing|ne)|on|state)|record\b|cursor.+\b(said|answer|output|result)\b"
    r")"
)


def _is_job_status_followup(
    tlow: str, text: str, *, is_new_dev_request: bool
) -> bool:
    """Heuristic: user is asking about a dev job, not queuing new work (which takes priority)."""
    if is_new_dev_request:
        return False
    if re.search(r"(?i)job\s*#\s*(\d+)", text) and _JOB_INQUISY_RE.search(tlow):
        return True
    if re.search(r"(?i)job\s*#\s*(\d+)", text) and len(tlow) < 140:
        return True
    return bool(_AMBIGUOUS_STATUS_QUERY_RE.search(tlow))


def _first_agent_job_id_in_text(text: str) -> int | None:
    m = re.search(r"(?i)job\s*#(\d+)", text)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(?i)for\s+job\s*(\d+)\b", text)
    if m2:
        return int(m2.group(1))
    return None


def _format_job_line(job) -> str:
    wtype = getattr(job, "worker_type", None) or ""
    st = job.status or ""
    if wtype == "dev_executor" and st in {
        "queued",
        "needs_approval",
        "approved",
        "in_progress",
        "agent_running",
        "changes_ready",
        "waiting_for_cursor",
    }:
        pl = dict(getattr(job, "payload_json", None) or {})
        ed = pl.get("execution_decision") or {}
        tool = ed.get("tool_key") or pl.get("preferred_dev_tool") or "—"
        mode = ed.get("mode") or pl.get("dev_execution_mode") or "—"
        extra = (
            "\n\n(With DEV_AGENT_AUTO_RUN, the worker will run the CLI agent, then ask for `approve` / `reject`.)"
            if st in {"in_progress", "agent_running", "changes_ready", "approved"}
            else ""
        )
        return (
            f"Dev job #{job.id} is in progress.\n\n"
            f"Status: {st}\n"
            f"Tool: {tool}\n"
            f"Mode: {mode}\n"
            f"Title: {job.title}\n\n"
            "The host worker runs the Nexa dev pipeline (autonomous CLI, IDE handoff, or manual review). "
            f"I can notify this chat on milestones.{extra}"
        )
    if wtype == "dev_executor" and st == "waiting_approval":
        r = (job.result or "")[:2000] + ("" if len(job.result or "") < 2000 else "…")
        return (
            f"Job #{job.id} needs your approval to commit (Aider / autonomous run).\n\n"
            f"{r or '(no summary in DB yet)'}\n\n"
            "Reply exactly: `approve` to commit, or `reject` to revert the branch, or `show diff` to see the diff."
        )
    if wtype == "dev_executor" and st == "approved_to_commit":
        return (
            f"Job #{job.id} is approved to commit. The next worker run will `git add` + `git commit` on the feature branch.\n\n"
            f"Title: {job.title}"
        )
    if wtype == "dev_executor" and st in {"rejected",}:
        return (
            f"Job #{job.id} was rejected. Review text / revert notes:\n\n"
            f"{(job.result or '—')[:3500]}"
        )
    if wtype == "dev_executor" and st == "failed":
        from app.services.dev_orchestrator.retry_advisor import advise_retry

        body = (
            f"Dev Agent job #{job.id} failed.\n\n"
            f"{job.error_message or 'No error details available.'}\n\n"
            f"Retry advice:\n{advise_retry(job)}"
        )
        return body[:4000]
    if wtype == "dev_executor" and st in {"ready_for_review", "needs_commit_approval", "review_approved", "commit_approved", "completed"}:
        res = (job.result or "").strip() or "No review text yet."
        head = f"Dev Agent job #{job.id} — {st}.\n\n" if st != "completed" else f"Dev Agent job #{job.id} (complete):\n\n"
        tail = ""
        if st == "ready_for_review":
            tail = f"\n\nReply: approve review job #{job.id}"
        elif st == "needs_commit_approval":
            tail = f"\n\nReply: approve commit job #{job.id}"
        block = head + res + tail
        return block[:5000] + ("" if len(block) <= 5000 else "…")
    wtype_l = (getattr(job, "worker_type", None) or "").lower()
    ct_l = (getattr(job, "command_type", None) or "").lower()
    if (
        wtype_l == "local_tool"
        and ct_l == "host-executor"
        and st in {"completed", "failed"}
    ):
        from app.services.host_executor_visibility import format_host_completion_message

        pl = dict(getattr(job, "payload_json", None) or {})
        title = str(pl.get("chat_pending_title") or job.title or "Host action")
        ok = st == "completed"
        block = format_host_completion_message(
            job_id=job.id,
            title=title,
            success=ok,
            body=(job.result or "") if ok else None,
            err=(job.error_message or "") if not ok else None,
        )
        return block[:4500] + ("" if len(block) <= 4500 else "…")

    label = job.command_type or job.kind
    line = f"#{job.id} {label} — {job.status}"
    if job.title and job.title != label:
        line += f"\nTitle: {job.title}"
    if job.approval_required and job.status == "needs_approval":
        line += f"\nWaiting for approval. Reply: approve job #{job.id}"
    if job.status == "approved":
        line += (
            "\n\nNo worker reply in Telegram yet: the job is approved but the dev executor "
            f"has not run (or cannot reach the same database). It must run to create dev_job_{job.id}.md "
            "under .agent_tasks/ and move status past approved. If this persists: docker compose "
            "restart api bot, or on Mac set DEV_EXECUTOR_ON_HOST=1 and use ./run_everything.sh start. "
            "See docs/DEV_JOB_FLOW.md."
        )
    if job.status == "waiting_for_cursor":
        line += (
            "\nThe task is on the machine running the dev executor. Open the task file in your IDE (host path: "
            f"`.agent_tasks/dev_job_{job.id}.md` next to the repo, not only `/app/...` inside Docker). "
            "Status stays `waiting_for_cursor` until you create the completion file "
            f"`.agent_tasks/dev_job_{job.id}.done.md` with a short summary (then the job moves to review). "
            "Codex / `DEV_AGENT_COMMAND` can create that file if you use them."
        )
    if job.status == "ready_for_review":
        line += f"\nReady for validation. Reply: approve review job #{job.id}"
    if job.status == "needs_commit_approval":
        line += f"\nReady to commit. Reply: approve commit job #{job.id}"
    if job.cursor_task_path:
        line += f"\nTask file: {job.cursor_task_path}"
    if job.result:
        line += f"\n{job.result[:1000]}"
    if job.error_message:
        line += f"\nError: {job.error_message[:1000]}"
    return line


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat:
        return
    db = SessionLocal()
    try:
        app_user_id = get_telegram_adapter().resolve_app_user_id(db, update)
        orchestrator.users.get_or_create(db, app_user_id)
        tr = get_telegram_role(update.effective_user.id, db)
        if tr == "blocked" and update.message:
            await update.message.reply_text(BLOCKED_MSG)
            return
        if update.message:
            from app.core.config import get_settings
            from app.services import user_api_keys as uak2

            s = get_settings()
            has_system_key = bool(
                (s.anthropic_api_key or "").strip() or (s.openai_api_key or "").strip()
            )
            if uak2.count_all_user_api_key_rows(db) == 0 and not (has_system_key and s.use_real_llm):
                await update.message.reply_text(first_time_nexa_start_text())
            else:
                await update.message.reply_text(start_message_for_role(tr))
    finally:
        db.close()


async def updates_cmd(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    from app.services.release_updates import format_release_updates_for_chat

    await update.message.reply_text(format_release_updates_for_chat())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if link:
            ctx = build_context(db, link.app_user_id, memory_service, orchestrator)
            body = help_message(ctx.has_active_plan, ctx.focus_task)
        else:
            body = help_message(False, None)
        await update.message.reply_text(
            body
            + "\n\n"
            + format_command_help_response().strip()
            + "\n\n"
            + "_Describe what you want in plain language first._\n"
            + "_Optional Telegram shortcuts (operators): `/command` — roster, memory, keys, approvals, dev tools._"
        )
    finally:
        db.close()


async def usage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.effective_chat:
        return
    from app.services.llm_usage_recorder import build_llm_usage_summary, get_recent_llm_usage
    from app.services.user_capabilities import get_telegram_role, is_owner_role

    sub = (context.args[0] or "").lower() if (context and context.args) else ""
    db = SessionLocal()
    try:
        app_user_id = get_telegram_adapter().resolve_app_user_id(db, update)
        r = get_telegram_role(int(update.effective_user.id), db)
        owner = is_owner_role(r)
        if sub in ("recent", "last"):
            rec = get_recent_llm_usage(db, 15, app_user_id, is_owner=owner)
            lines: list[str] = [
                "Nexa Usage (recent, estimates; provider billing is the source of truth):"
            ]
            for row in rec:
                al = (row.get("at") or "")[:19] or "—"
                pr = (row.get("provider") or "?")
                m = (str(row.get("model") or "") or "?")[:24]
                tok = int(row.get("total_tokens") or 0)
                cst = row.get("estimated_cost_usd")
                c_s = f"${cst:.4f}" if cst is not None else "n/a"
                klab = "BYOK" if row.get("used_user_key") else "System"
                act = (str(row.get("action") or "") or "?")[:20]
                lines.append(f"• {al} {pr} · {m} · {tok} tok · {c_s} · {klab} · {act}")
            if len(lines) == 1:
                lines.append("— No recorded calls in this view yet.")
        else:
            s = build_llm_usage_summary("today", db, app_user_id, is_owner=owner)
            sc = float(s.get("system_key_cost_usd") or 0)
            uc = float(s.get("user_key_cost_usd") or 0)
            est = float(s.get("estimated_cost_usd") or 0)
            top = s.get("by_action") or []
            top3 = [x for x in (top or []) if isinstance(x, dict)][:6]
            lines = [
                "Nexa Usage (today, estimates — provider billing is source of truth)",
                f"LLM calls: {s.get('total_calls', 0)}",
                f"Tokens: {int(s.get('total_tokens') or 0):,}",
                f"Estimated cost: ${est:.4f}",
                f"System-key cost: ${sc:.4f}",
                f"BYOK usage: ${uc:.4f}",
            ]
            if top3:
                lines.append("Top actions:")
            for r in top3:
                a = (r.get("action") or "—") or "—"
                c = int((r or {}).get("calls") or 0)
                lines.append(f"• {a}: {c} call(s)")
            lines.append(
                "Why Nexa: routing, tools, and local execution reduce unnecessary LLM calls."
            )
        text = "\n".join((ln for ln in lines if ln is not None))[:3900]
        await update.message.reply_text(text)
    finally:
        db.close()


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        result = orchestrator.get_today_plan(db, link.app_user_id)
        if not result:
            await update.message.reply_text("No plan yet. Send me a brain dump first.")
            return
        plan = result["plan"]
        tasks = result["tasks"]
        lines = [f"{plan.summary}", ""]
        for idx, task in enumerate(tasks, start=1):
            lines.append(f"{idx}. {task.title} [{task.status}]")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def overwhelmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat or not update.message:
        return
    db = SessionLocal()
    try:
        with llm_telegram_context(db, int(update.effective_user.id)):
            app_user_id = get_telegram_adapter().resolve_app_user_id(db, update)
            orchestrator.users.get_or_create(db, app_user_id)
            msg = "I feel overwhelmed"
            logger.info("incoming_text=%s", msg[:120])
            cctx = get_or_create_context(db, app_user_id)
            snap = build_context_snapshot(cctx, db)
            rt = route_agent(msg, context_snapshot=snap)
            rkey = str(rt.get("agent_key") or "nexa")
            intent = get_intent(msg, conversation_snapshot=snap)
            logger.info("classified_intent=%s", intent)
            logger.info("plan_triggered=%s", intent == "brain_dump")
            logger.info("llm_classifier_used=%s", settings.use_real_llm)
            if intent == "brain_dump":
                logger.warning("PLAN_GENERATION_TRIGGERED intent=%s text_preview=%s", intent, msg[:100])
                result = orchestrator.generate_plan_from_text(
                    db, app_user_id, msg, input_source="telegram", intent="brain_dump"
                )
                ctx_after = build_context(db, app_user_id, memory_service, orchestrator)
                if result.get("needs_more_context"):
                    o = apply_tone(no_tasks_response(), ctx_after.memory)
                    await update.message.reply_text(o)
                    _persist_conversation_turn(db, app_user_id, cctx, msg, o, intent, rkey)
                    return
                orchestrator.users.mark_user_onboarded(db, app_user_id)
                body = build_response(
                    msg,
                    intent,
                    ctx_after,
                    plan_result=result,
                    db=db,
                    app_user_id=app_user_id,
                    conversation_snapshot=snap,
                    routing_agent_key=rkey,
                )
                tail = "\n\nReply with your real brain dump next, and I will organize that too."
                full = body + tail
                await update.message.reply_text(full)
                _persist_conversation_turn(db, app_user_id, cctx, msg, full, intent, rkey)
            else:
                ctx = build_context(db, app_user_id, memory_service, orchestrator)
                body = build_response(
                    msg,
                    intent,
                    ctx,
                    plan_result=None,
                    db=db,
                    app_user_id=app_user_id,
                    conversation_snapshot=snap,
                    routing_agent_key=rkey,
                )
                o = apply_tone(body, ctx.memory)
                await update.message.reply_text(o)
                _persist_conversation_turn(db, app_user_id, cctx, msg, o, intent, rkey)
    finally:
        db.close()


async def prefs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        p = memory_service.get_preferences(db, link.app_user_id)
        await update.message.reply_text(
            f"Planning style: {p.planning_style}\nMax daily tasks: {p.max_daily_tasks}\nGym days: {', '.join(p.typical_gym_days) or 'none'}"
        )
    finally:
        db.close()


async def doc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    from telegram import InputFile

    from app.services.document_generation import (
        DocumentGenerationError,
        generate_document,
        get_document_path_for_owner,
        list_document_artifacts_for_user,
    )

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        app_uid = link.app_user_id
        args = [str(a).lower() for a in (context.args or [])]
        if not args or args[0] in ("help", "h", "-h"):
            await update.message.reply_text(
                "Documents — /doc\n"
                "• /doc create pdf|docx|md|txt [title] — last assistant message → file (attached)\n"
                "• /doc recent — list recent export ids\n"
                "Or: “export as PDF” in chat right after I reply."
            )
            return
        if args[0] == "recent":
            items = list_document_artifacts_for_user(db, app_uid, limit=8)
            if not items:
                await update.message.reply_text(
                    "No exports yet. After I reply, try: /doc create pdf"
                )
                return
            lines = ["Recent document exports:"]
            for it in items:
                lines.append(f"• #{it.id} {it.format.upper()} — {it.title[:60]}")
            await update.message.reply_text("\n".join(lines)[:3800])
            return
        if args[0] == "create" and len(args) >= 2 and args[1] in ("pdf", "docx", "md", "txt"):
            fmt = args[1]
            title = " ".join((context.args or [])[2:]).strip() or "Nexa export"
            last = get_last_assistant_text(db, app_uid)
            if not last:
                await update.message.reply_text(
                    "No assistant message to export yet. Ask me something, then: /doc create pdf"
                )
                return
            try:
                art = generate_document(
                    db,
                    title=title,
                    body_markdown=last,
                    format=fmt,
                    user_id=app_uid,
                    source_type="chat",
                    source_ref="doc_cmd",
                )
            except DocumentGenerationError as e:
                await update.message.reply_text(str(e)[:2000])
                return
            path = get_document_path_for_owner(db, art.id, app_uid)
            if not path or not path.is_file():
                await update.message.reply_text("Could not read the generated file. Try again.")
                return
            with path.open("rb") as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=path.name),
                    caption=f"Done — I created your {fmt.upper()}. (document #{art.id})",
                )
            return
        await update.message.reply_text("Use: /doc  |  /doc create pdf  |  /doc recent")
    finally:
        db.close()


async def command_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    sub = (context.args[0] or "").lower() if (context and context.args) else ""
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if sub == "status":
            cctx = get_or_create_context(db, link.app_user_id)
            out = format_agents_status(db, link.app_user_id, active_topic=cctx.active_topic)[:12_000]
            for piece in _split_telegram_text(out, max_len=4000):
                await update.message.reply_text(piece)
            return
        await update.message.reply_text(format_command_center()[:12_000])
    finally:
        db.close()


async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Repo-root soul.md / memory.md plus optional DB note count for bare /memory."""
    if not update.message or not update.effective_user:
        return
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        raw = (update.message.text or "/memory").strip()
        norm = re.sub(r"^/memory@\S+\b", "/memory", raw.strip(), flags=re.IGNORECASE).strip()
        nlow = (norm or "").lower().strip()
        if nlow == "/memory":
            pass
        elif tr == "guest":
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="memory", reason="guest_file", preview=norm[:40],
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        elif nlow.startswith("/memory add") and not can_write_global_memory_file(tr):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="memory", reason="memory_add", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        reply = handle_memory_command(raw)
        if nlow == "/memory":
            state = memory_service.get_state(db, link.app_user_id)
            reply = f"{reply}\n\n—\n\nDatabase notes on your account: {len(state.notes)}."
        for piece in _split_telegram_text(reply[:12_000], max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if not can_memory_working_remember_forget(tr):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="forget", reason=tr, preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        if not context.args:
            await update.message.reply_text("Use /forget <task, topic, or task id>")
            return
        query = " ".join(context.args).strip()
        result = memory_service.forget(db, link.app_user_id, query)
        lines = [f"I removed what I found for '{result.query}'."]
        lines.append(f"Notes removed: {result.deleted_notes}")
        lines.append(f"Tasks removed: {result.deleted_tasks}")
        lines.append(f"Check-ins cancelled: {result.cancelled_checkins}")
        if result.deleted_task_ids:
            lines.append(f"Task ids: {', '.join(str(x) for x in result.deleted_task_ids)}")
        if result.cancelled_checkin_ids:
            lines.append(f"Check-in ids: {', '.join(str(x) for x in result.cancelled_checkin_ids)}")
        if result.deleted_task_titles:
            lines.append("Titles: " + ", ".join(result.deleted_task_titles[:5]))
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def soul_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if context.args:
            if not can_write_global_memory_file(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                    uname=update.effective_user.username, family="soul", reason="soul_write", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
        if not context.args and (tr or "") == "guest":
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="soul", reason="soul_read", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        if context.args:
            content = memory_service.get_soul_markdown(db, link.app_user_id)
            updated = memory_service.update_soul_markdown(
                db,
                link.app_user_id,
                content + "\n- " + " ".join(context.args).strip(),
                source="telegram",
            )
            await update.message.reply_text("I updated my soul rules.\n\n" + "\n".join(updated.splitlines()[:12]))
            return
        await update.message.reply_text(memory_service.get_soul_markdown(db, link.app_user_id))
    finally:
        db.close()


async def host_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Host executor visibility: enabled flag, allowlists, how to ask (no execution here)."""
    if not update.message:
        return
    from app.services.host_executor_visibility import telegram_host_command_text

    await update.message.reply_text(telegram_host_command_text())


async def permissions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List or grant/revoke access permission rows (scoped local host tools)."""
    if not update.effective_user or not update.message:
        return
    from app.services.access_permissions import (
        STATUS_PENDING,
        grant_permission,
        list_permissions,
        reason_for_scope,
        revoke_permission,
    )

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        uid = link.app_user_id
        args = list(context.args or [])
        if len(args) >= 2 and args[0].lower() == "revoke":
            try:
                pid = int(args[1])
            except ValueError:
                await update.message.reply_text("Usage: /permissions revoke <id>")
                return
            row = revoke_permission(db, uid, pid)
            if not row:
                await update.message.reply_text("Could not revoke (unknown id or not pending/granted).")
                return
            await update.message.reply_text(f"Revoked permission #{pid}.")
            return
        if len(args) >= 2 and args[0].lower() in ("grant", "approve"):
            try:
                pid = int(args[1])
            except ValueError:
                await update.message.reply_text("Usage: /permissions grant <id>")
                return
            row = grant_permission(db, uid, pid, granted_by_user_id=uid)
            if not row:
                await update.message.reply_text("Could not grant (unknown id or not pending).")
                return
            tgt = (row.target or "")[:160] + ("…" if len(row.target or "") > 160 else "")
            await update.message.reply_text(f"Granted permission #{row.id}: {row.scope} → {tgt}")
            return
        rows = list_permissions(db, uid, limit=40)
        if not rows:
            await update.message.reply_text(
                "No permission rows yet. When Nexa needs local access through Nexa's local system, "
                "it can create a pending request — see System → Permissions in the web UI."
            )
            return
        lines = ["Nexa — local access permissions:", ""]
        for r in rows[:25]:
            st = (r.status or "").strip()
            t = (r.target or "")[:100] + ("…" if len(r.target or "") > 100 else "")
            lines.append(f"#{r.id}  {r.scope}  risk={r.risk_level}  {st}\n    {t}")
        lines.append("")
        lines.append("Grant pending: /permissions grant <id>  ·  Revoke: /permissions revoke <id>")
        body = "\n".join(lines)[:9000]
        for piece in _split_telegram_text(body, max_len=4000):
            await update.message.reply_text(piece)

        pending = [r for r in rows if (r.status or "").strip() == STATUS_PENDING]
        for r in pending[:12]:
            tgt = (r.target or "").strip()
            rs = (r.reason or "").strip() or reason_for_scope(r.scope)
            card = (
                "Permission request:\n"
                f"- Scope: {r.scope}\n"
                f"- Target: {tgt[:360]}{'…' if len(tgt) > 360 else ''}\n"
                f"- Risk: {r.risk_level}\n"
                f"- Reason: {rs[:400]}"
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Approve", callback_data=f"perm:grant:{r.id}"),
                        InlineKeyboardButton("Reject", callback_data=f"perm:deny:{r.id}"),
                    ]
                ]
            )
            await update.message.reply_text(card[:3900], reply_markup=kb)
    finally:
        db.close()


async def workspace_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register safe directory roots for the host executor (owner add/revoke)."""
    if not update.effective_user or not update.message:
        return
    from app.services.workspace_registry import add_root, list_roots, revoke_root

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        uid = link.app_user_id
        args = list(context.args or [])
        sub = (args[0] or "list").strip().lower() if args else "list"

        if sub == "list":
            rows = list_roots(db, uid, active_only=True)
            if not rows:
                await update.message.reply_text(
                    "No active workspace roots. Owner: /workspace add /absolute/path"
                )
                return
            lines = ["Nexa — workspace roots (host executor boundaries):", ""]
            for r in rows[:30]:
                lab = (r.label or "").strip()
                lines.append(f"#{r.id}  {r.path_normalized}" + (f"  ({lab})" if lab else ""))
            await update.message.reply_text("\n".join(lines)[:9000])
            return

        if not is_owner_role(tr):
            await update.message.reply_text("Workspace add/revoke is owner-only. You can still use /workspace list.")
            return

        if sub == "add":
            path_raw = " ".join(args[1:]).strip()
            if not path_raw:
                await update.message.reply_text("Usage: /workspace add /absolute/path/to/folder")
                return
            try:
                row = add_root(db, uid, path_raw)
            except ValueError as e:
                await update.message.reply_text(str(e)[:3500])
                return
            await update.message.reply_text(f"Registered workspace root #{row.id}: {row.path_normalized}")
            return

        if sub == "revoke":
            if len(args) < 2:
                await update.message.reply_text("Usage: /workspace revoke <id>")
                return
            try:
                rid = int(args[1])
            except ValueError:
                await update.message.reply_text("Usage: /workspace revoke <id>")
                return
            row = revoke_root(db, uid, rid)
            if not row:
                await update.message.reply_text("Could not revoke (unknown id).")
                return
            await update.message.reply_text(f"Revoked workspace root #{rid}.")
            return

        await update.message.reply_text(
            "Usage:\n/workspace list\n/workspace add /path\n/workspace revoke <id>"
        )
    finally:
        db.close()


async def nexa_projects_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List Nexa workspace projects (named folders) and active id for this chat."""
    if not update.effective_user or not update.message:
        return
    from app.services.conversation_context_service import get_or_create_context
    from app.services.nexa_workspace_project_registry import list_workspace_projects

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if (get_telegram_role(update.effective_user.id, db) or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        uid = link.app_user_id
        cctx = get_or_create_context(db, uid, web_session_id="default")
        rows = list_workspace_projects(db, uid, limit=50)
        if not rows:
            await update.message.reply_text(
                "No Nexa projects yet. Owner: /project add /absolute/path Name — path must be under "
                "registered /workspace roots and HOST_EXECUTOR_WORK_ROOT."
            )
            return
        head = ""
        if getattr(cctx, "active_project_id", None):
            head = f"Active in this chat: #{cctx.active_project_id}\n\n"
        lines = [head + "Nexa — workspace projects:", ""]
        for r in rows[:40]:
            mark = "  ← active" if cctx.active_project_id == r.id else ""
            lines.append(f"#{r.id}  {r.name}{mark}\n    {r.path_normalized[:280]}")
        lines.append("")
        lines.append("Switch: /project use <id>  ·  Add (owner): /project add <path> <name>")
        await update.message.reply_text("\n".join(lines)[:9000])
    finally:
        db.close()


async def nexa_project_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set active project or add a labeled folder (owner)."""
    if not update.effective_user or not update.message:
        return
    from app.services.conversation_context_service import get_or_create_context
    from app.services.nexa_workspace_project_registry import (
        add_workspace_project,
        get_workspace_project,
        set_active_workspace_project,
    )

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        uid = link.app_user_id
        args = list(context.args or [])
        cctx = get_or_create_context(db, uid, web_session_id="default")
        if not args:
            await update.message.reply_text(
                "Usage:\n"
                "/project use <id> — active project for this chat (default file paths)\n"
                "/project add <path> <name> — register a project (owner)\n"
                "/project clear — clear active project\n"
                "/projects — list all projects"
            )
            return
        sub = (args[0] or "").strip().lower()
        if sub in ("clear", "none", "off"):
            set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=None)
            await update.message.reply_text("Cleared active Nexa project for this chat.")
            return
        if sub in ("use", "switch"):
            if len(args) < 2:
                await update.message.reply_text("Usage: /project use <id>")
                return
            try:
                pid = int(args[1])
            except ValueError:
                await update.message.reply_text("Usage: /project use <id>")
                return
            pr = get_workspace_project(db, uid, pid)
            if not pr:
                await update.message.reply_text("Unknown project id (or not yours).")
                return
            set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=pid)
            await update.message.reply_text(
                f"Active project: {pr.name}\n{pr.path_normalized[:1200]}"
            )
            return
        if sub == "add":
            if not is_owner_role(tr):
                await update.message.reply_text("Only the owner can add Nexa workspace projects.")
                return
            if len(args) < 3:
                await update.message.reply_text("Usage: /project add /absolute/path Project name")
                return
            path_raw = args[1].strip()
            name = " ".join(args[2:]).strip()
            if not name:
                await update.message.reply_text("Usage: /project add /path <name>")
                return
            try:
                row = add_workspace_project(db, uid, path_raw, name)
            except ValueError as e:
                await update.message.reply_text(str(e)[:3500])
                return
            await update.message.reply_text(
                f"Added project #{row.id} — “{name}”. Use /project use {row.id}"
            )
            return
        await update.message.reply_text("Unknown subcommand. Send /project for help.")
    finally:
        db.close()


async def projects_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.services.telegram_project_commands import format_projects_list_for_user

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        for piece in _split_telegram_text(
            format_projects_list_for_user(db, tr), max_len=4000
        ):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def project_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.services.telegram_project_commands import (
        format_one_project,
        format_project_workflow_cmd,
        run_project_add,
        run_set_default,
        set_project_dev_mode,
        set_project_dev_tool,
    )

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        args = [a.strip() for a in (context.args or []) if a.strip()]
        if not args:
            await update.message.reply_text(
                "Usage: `/project <key>`  ·  `/project workflow <key>`  ·  "
                "`/project set-default <key>`  ·  "
                "`/project set-tool <key> <tool>`  ·  `/project set-mode <key> <mode>`  ·  "
                "`/project add <key> <provider> <repo_path>`",
            )
            return
        a0 = args[0].lower()
        if a0 == "set-tool" and len(args) >= 3:
            if not can_project_admin(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                    uname=update.effective_user.username, family="project", reason="set_tool", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            await update.message.reply_text(
                set_project_dev_tool(db, args[1].lower().strip(), args[2].lower().strip())[
                    :4000
                ]
            )
            return
        if a0 == "set-mode" and len(args) >= 3:
            if not can_project_admin(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                    uname=update.effective_user.username, family="project", reason="set_mode", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            await update.message.reply_text(
                set_project_dev_mode(db, args[1].lower().strip(), args[2].lower().strip())[
                    :4000
                ]
            )
            return
        if a0 == "workflow" and len(args) >= 2:
            if (tr or "") == "guest":
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            await update.message.reply_text(
                format_project_workflow_cmd(db, args[1].lower().strip())[:10_000]
            )
            return
        if a0 == "set-default" and len(args) >= 2:
            if not can_project_admin(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                    uname=update.effective_user.username, family="project", reason="set_default", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            await update.message.reply_text(
                run_set_default(db, args[1].lower().strip())[:4000]
            )
            return
        if a0 == "add" and len(args) >= 4:
            if not can_project_admin(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                    uname=update.effective_user.username, family="project", reason="add", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            r = run_project_add(
                db,
                args[1].lower().strip(),
                args[2].lower().strip(),
                " ".join(args[3:]).strip(),
            )
            await update.message.reply_text(r[:4000])
            return
        if len(args) == 1:
            for piece in _split_telegram_text(
                format_one_project(db, args[0].lower(), role=tr), max_len=4000
            ):
                await update.message.reply_text(piece)
            return
        await update.message.reply_text(
            "I did not understand that. Try `/project` with no args for help."
        )
    finally:
        db.close()


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if not is_owner_role(get_telegram_role(update.effective_user.id, db)):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="approve", reason="not_owner", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        if not context.args:
            await update.message.reply_text("Use /approve <job_id>, /approve review <job_id>, or /approve commit <job_id>")
            return
        if len(context.args) >= 2 and context.args[0].lower() == "review":
            job = job_service.approve_review(db, link.app_user_id, int(context.args[1].strip().lstrip("#")))
        elif len(context.args) >= 2 and context.args[0].lower() == "commit":
            job = job_service.approve_commit(db, link.app_user_id, int(context.args[1].strip().lstrip("#")))
        else:
            jid0 = int(context.args[0].strip().lstrip("#"))
            ops_m = process_ops_job_decision(
                db, job_service, link.app_user_id, jid0, "approve"
            )
            if ops_m is not None:
                await update.message.reply_text(ops_m)
                return
            job = job_service.decide(db, link.app_user_id, jid0, "approve")
        await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
    finally:
        db.close()


async def deny_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if not is_owner_role(get_telegram_role(update.effective_user.id, db)):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="deny", reason="not_owner", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        if not context.args:
            await update.message.reply_text("Use /deny <job_id>")
            return
        d_jid = int(context.args[0].strip().lstrip("#"))
        d_ops = process_ops_job_decision(db, job_service, link.app_user_id, d_jid, "deny")
        if d_ops is not None:
            await update.message.reply_text(d_ops)
            return
        job = job_service.decide(db, link.app_user_id, d_jid, "deny")
        await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
    finally:
        db.close()


async def agents_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    sub = (context.args[0] or "").lower() if (context and context.args) else ""
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if sub == "status":
            cctx = get_or_create_context(db, link.app_user_id)
            out = format_agents_status(
                db, link.app_user_id, active_topic=cctx.active_topic
            )[:12_000]
            for piece in _split_telegram_text(out, max_len=4000):
                await update.message.reply_text(piece)
            return
        if sub == "mine":
            from app.services.custom_agents import list_active_custom_agents

            custom = list_active_custom_agents(db, link.app_user_id)
            if not custom:
                await update.message.reply_text(
                    "You don’t have custom agents yet. Try: “Create me a custom agent: financial advisor”"
                )
                return
            lines = ["**Your custom agents** (Nexa, LLM-only):", ""]
            for a in custom:
                lines.append(f"· `@{a.agent_key}` — {a.display_name}\n  {a.description[:200] + ('…' if len(a.description) > 200 else '') if a.description else '—'}")
            for piece in _split_telegram_text("\n".join(lines)[:10_000], max_len=4000):
                await update.message.reply_text(piece)
            return
        out2 = format_agents_list()[:10_000]
        from app.services.custom_agents import list_active_custom_agents

        cu = list_active_custom_agents(db, link.app_user_id)
        if cu:
            out2 += "\n\n**Custom** (yours, LLM-only):\n" + "\n".join(
                f"· `@{a.agent_key}`" for a in cu[:20]
            )
        out2 += "\n\n**Custom agents** — your list above. Use “create agent: …” in chat to add more."
        for piece in _split_telegram_text(out2[:12_000], max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def user_agent_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    from app.services.custom_agents import (
        can_user_create_custom_agents,
        create_custom_agent,
        delete_custom_agent,
        get_custom_agent,
        list_active_custom_agents,
    )

    args = list(context.args or [])
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        uid = link.app_user_id
        if not args:
            await update.message.reply_text(
                "Usage:\n"
                "· `/agent delete <key>`\n"
                "· `/agent describe <key>`\n"
                "· `/agent create <key> <description...>`\n"
                "Or just chat: “Create me a few agents: …”"
            )
            return
        op = (args[0] or "").lower()
        if op in ("list", "mine"):
            custom = list_active_custom_agents(db, uid)
            if not custom:
                await update.message.reply_text(
                    "You don’t have custom agents yet. Try: “Create me a custom agent: financial advisor”"
                )
                return
            lines = ["**Your custom agents** (Nexa, LLM-only):", ""]
            for a in custom:
                lines.append(
                    f"· `@{a.agent_key}` — {a.display_name}\n  {a.description[:200] + ('…' if len(a.description) > 200 else '') if a.description else '—'}"
                )
            for piece in _split_telegram_text("\n".join(lines)[:10_000], max_len=4000):
                await update.message.reply_text(piece)
            return
        if op == "delete" and len(args) >= 2:
            k = (args[1] or "").strip().lstrip("@")
            if delete_custom_agent(db, uid, k):
                await update.message.reply_text(
                    f"Deactivated `@{k}`. (It won’t appear in your custom list.)"
                )
            else:
                await update.message.reply_text("No custom agent with that key.")
            return
        if op == "describe" and len(args) >= 2:
            k = (args[1] or "").strip().lstrip("@")
            a = get_custom_agent(db, uid, k)
            if a and a.is_active:
                await update.message.reply_text(
                    f"`@{a.agent_key}`\n**{a.display_name}**\n\n{a.description}\n\n(Ask it with `@{a.agent_key} <message>`.)"
                )
            else:
                await update.message.reply_text("Not found (or inactive).")
            return
        if op == "create" and len(args) >= 2:
            ok, err = can_user_create_custom_agents(db, uid)
            if not ok:
                await update.message.reply_text(err or "Not allowed here.")
                return
            k = (args[1] or "").strip().lstrip("@")
            rest = " ".join(args[2:]).strip() or f"{k} assistant"
            a = create_custom_agent(
                db, uid, rest, description=rest, force_agent_key=k
            )
            await update.message.reply_text(
                f"Created `@{a.agent_key}` — {a.display_name}.\nTry: `@{a.agent_key} hello`"
            )
            return
        await update.message.reply_text("Use `/agent` for help.")
    finally:
        db.close()


async def learning_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    args = (context and context.args) or []
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        u = link.app_user_id
        tr = get_telegram_role(update.effective_user.id, db)
        if len(args) >= 2 and (args[0] or "").lower() in ("approve", "reject"):
            if not is_owner_role(tr):
                _deny(
                    db, telegram_id=update.effective_user.id, app_user=u,
                    uname=update.effective_user.username, family="learning", reason="approve_reject", preview=None,
                )
                await update.message.reply_text(ACCESS_RESTRICTED)
                return
            act = (args[0] or "").lower()
            try:
                eid = int(str(args[1]).strip().lstrip("#"))
            except ValueError:
                await update.message.reply_text("Use: /learning approve 8  or  /learning reject 8")
                return
            if act == "approve":
                m = learning_approve(
                    db,
                    u,
                    eid,
                    apply_to_memory=True,
                    memory_service=memory_service,
                )
            else:
                m = learning_reject(db, u, eid)
            await update.message.reply_text(
                m or "Not found, already decided, or not on your account."
            )
            return
        if args:
            await update.message.reply_text("Use: /learning  or  /learning approve <id>  or  /learning reject <id>")
            return
        if not is_trusted_or_owner(tr):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=u,
                uname=update.effective_user.username, family="learning", reason="list", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        pending = learning_list_pending(db, u, limit=20)
        if not pending:
            await update.message.reply_text("No pending learning items.")
            return
        lines: list[str] = [
            "Pending learning (Nexa):",
            "Reply: /learning approve <id>  or  /learning reject <id>",
            "",
        ]
        for p in pending[:15]:
            obs = p.observation[:400] + ("…" if len(p.observation) > 400 else "")
            pr = p.proposed_rule or "—"
            pr2 = pr[:300] + ("…" if len(pr) > 300 else "")
            lines.append(
                f"**#{p.id}**  Agent: {p.agent_key}\n"
                f"Observation: {obs}\n"
                f"Proposed rule: {pr2}\n"
                f"— Reply: `/learning approve {p.id}`  or  `/learning reject {p.id}`"
            )
        body = "\n\n".join(lines)[:10_000]
        for piece in _split_telegram_text(body, max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def access_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tr = get_telegram_role(update.effective_user.id, db)
        if (tr or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        await update.message.reply_text(format_access_command_text(tr))
    finally:
        db.close()


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if not is_owner_role(get_telegram_role(update.effective_user.id, db)):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="users", reason="not_owner", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        rows = telegram_service.repo.list_recent(db, limit=30)
        lines: list[str] = ["Nexa — recent Telegram user links (this instance):", ""]
        for r in rows:
            role = get_telegram_role(int(r.telegram_user_id), db)
            u = (r.username or "—")[:40]
            lines.append(
                (f"• id `{r.telegram_user_id}`  @{u}  first: {r.created_at}  updated: {r.updated_at}  role: {role}")[
                    :2000
                ]
            )
        for piece in _split_telegram_text("\n".join(lines)[:10_000], max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def keys_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if (get_telegram_role(update.effective_user.id, db) or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        t = user_api_key_service.format_key_list_telegram(db, int(update.effective_user.id))
        for piece in _split_telegram_text(t[:12_000], max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


KEY_HELP = (
    "Nexa /key (bring your own API key)\n\n"
    "• /keys  or  /key list — which providers you have set\n"
    "• /key status — resolved LLM (your keys vs server env)\n"
    "• /key set openai <key>  or  /key set anthropic <key>\n"
    "• /key delete openai  or  /key delete anthropic\n\n"
    "Keys are encrypted; the owner does not need to share their env keys. "
    "A key does not unlock Dev/Ops (roles are separate)."
)


async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    args = (context.args or [])
    if not args:
        for piece in _split_telegram_text(KEY_HELP, max_len=4000):
            await update.message.reply_text(piece)
        return
    sub = (args[0] or "").strip().lower()
    if sub in ("help", "?"):
        for piece in _split_telegram_text(KEY_HELP, max_len=4000):
            await update.message.reply_text(piece)
        return
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        tid = int(update.effective_user.id)
        if (get_telegram_role(tid, db) or "") == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return
        if sub == "list" or (sub == "ls" and len(args) < 2):
            t = user_api_key_service.format_key_list_telegram(db, tid)
            for piece in _split_telegram_text(t[:12_000], max_len=4000):
                await update.message.reply_text(piece)
            return
        if sub in ("status", "st"):
            from app.services.llm_key_resolution import resolve_llm_for_user

            r = resolve_llm_for_user(db, link.app_user_id)
            if r.available:
                src = "**your BYOK**" if r.source == "user" else "**server env**"
                body = (
                    f"**LLM:** usable — provider **{r.provider}** via {src}.\n\n"
                    "This is what custom agents and chat use when merging keys."
                )
            else:
                body = (
                    "**LLM:** not resolved for this account.\n\n"
                    f"{r.reason or 'No keys'}\n\n"
                    "Add `/key set anthropic …` or ask the owner to set ANTHROPIC_API_KEY / OPENAI_API_KEY."
                )
            for piece in _split_telegram_text(body.strip(), max_len=4000):
                await update.message.reply_text(piece)
            return
        if sub == "set":
            if len(args) < 3:
                await update.message.reply_text(
                    "Use: `/key set openai <key>`  or  `/key set anthropic <key>`",
                )
                return
            prov = (args[1] or "").strip()
            key_part = " ".join(args[2:]).strip()
            ok, msg = user_api_key_service.set_user_api_key(db, tid, prov, key_part)
            await update.message.reply_text(msg if ok else f"Not saved. {msg}")
            return
        if sub in ("delete", "rm", "remove", "clear"):
            if len(args) < 2:
                await update.message.reply_text("Use: /key delete openai  (or anthropic)")
                return
            prov = (args[1] or "").strip()
            if user_api_key_service.delete_user_api_key(db, tid, prov):
                p = user_api_key_service.normalize_provider(prov) or prov
                await update.message.reply_text(
                    f"Removed your {p} key (if it was set).",
                )
            else:
                await update.message.reply_text(
                    f"Unknown provider. Use: {', '.join(user_api_key_service.PROVIDERS)}",
                )
            return
        for piece in _split_telegram_text(KEY_HELP, max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def why_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Last Nexa decision (transparency, not private reasoning)."""
    if not update.effective_user or not update.message:
        return
    from app.services.decision_summary import format_decision_for_telegram_why

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        cctx = get_or_create_context(db, link.app_user_id)
        d = get_last_decision_from_context(cctx)
        t = format_decision_for_telegram_why(d)
        for piece in _split_telegram_text(t, max_len=4000):
            await update.message.reply_text(piece)
    finally:
        db.close()


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Use /start first.")
            return
        if not is_owner_role(get_telegram_role(update.effective_user.id, db)):
            _deny(
                db, telegram_id=update.effective_user.id, app_user=link.app_user_id,
                uname=update.effective_user.username, family="cancel", reason="not_owner", preview=None,
            )
            await update.message.reply_text(ACCESS_RESTRICTED)
            return
        if not context.args:
            await update.message.reply_text("Use /cancel <job_id>")
            return
        job = job_service.cancel(db, link.app_user_id, int(context.args[0].strip().lstrip("#")))
        await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
    finally:
        db.close()


async def handle_incoming_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.text:
        return
    async with typing_indicator(
        update, context, interval_seconds=3.0, min_visible_seconds=0.8
    ):
        await _handle_incoming_text_impl(update, context)


async def _handle_incoming_text_impl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info("incoming_text=%s", text[:120])
    db = SessionLocal()
    try:
        _tg_ad = get_telegram_adapter()
        app_user_id = _tg_ad.resolve_app_user_id(db, update)
        _norm = _tg_ad.normalize_message(update, app_user_id=app_user_id)
        logger.debug(
            "telegram_normalized channel=%s update_id=%s",
            _norm.get("channel"),
            _norm.get("metadata", {}).get("update_id"),
        )
        user_row = orchestrator.users.get_or_create(db, app_user_id)
        telegram_chat_id = str(update.effective_chat.id) if update.effective_chat else None
        effu = update.effective_user
        if not effu:
            return
        tg_role = get_telegram_role(effu.id, db)
        if tg_role == "blocked" and update.message:
            await update.message.reply_text(BLOCKED_MSG)
            return

        from app.services.channel_gateway.metadata import build_channel_origin
        from app.services.channel_gateway.origin_context import bind_channel_origin

        _llm_tok = bind_llm_telegram(db, int(effu.id))
        _u_tok = bind_llm_usage_telegram(db, app_user_id, int(effu.id))
        with bind_channel_origin(build_channel_origin(_norm)):
            try:
                tstrip = (text or "").strip()
                tlow = tstrip.lower()
                tlow = re.sub(r"^(/[a-z0-9_]+)@[A-Za-z0-9_]+", r"\1", tlow, count=1)
                tnorm = tlow.rstrip("!?. ")
    
                # Natural-language "why" (optional; not every turn)
                _ASK_WHY_PHRASES = frozenset(
                    {
                        "why",
                        "why did you do that",
                        "why this agent",
                        "why did you choose dev",
                    }
                )
                if tnorm in _ASK_WHY_PHRASES or tnorm in {p + "?" for p in _ASK_WHY_PHRASES if p != "why"}:
                    from app.services.decision_summary import format_decision_for_telegram_why
    
                    cctx_w = get_or_create_context(db, app_user_id)
                    twhy = format_decision_for_telegram_why(
                        get_last_decision_from_context(cctx_w)
                    )
                    for piece in _split_telegram_text(twhy, max_len=4000):
                        await update.message.reply_text(piece)
                    return
                udata = (context.user_data or {}) if context and context.user_data is not None else {}
                if not tstrip.startswith("/") and tstrip:
                    from app.services.custom_agents import (
                        try_conversational_create_custom_agents,
                        try_custom_agent_capability_guidance,
                    )
    
                    cg = try_custom_agent_capability_guidance(db, app_user_id, tstrip)
                    if cg is not None:
                        cctx_g = get_or_create_context(db, app_user_id)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx_g,
                            tstrip,
                            cg,
                            "custom_agent_guidance",
                            "nexa",
                        )
                        for gp in _split_telegram_text(cg, max_len=4000):
                            await update.message.reply_text(gp)
                        return
                    cr = try_conversational_create_custom_agents(
                        db, app_user_id, tstrip
                    )
                    if cr is not None:
                        cctx_c = get_or_create_context(db, app_user_id)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx_c,
                            tstrip,
                            cr,
                            "custom_agent_create",
                            "nexa",
                        )
                        for cp in _split_telegram_text(cr, max_len=4000):
                            await update.message.reply_text(cp)
                        return
                if not tstrip.startswith("/") and tstrip:
                    from telegram import InputFile

                    from app.services.document_generation import (
                        DocumentGenerationError,
                        generate_document,
                        get_document_path_for_owner,
                    )
                    from app.services.document_template_intent import (
                        is_template_document_intent,
                        parse_template_document_request,
                    )
    
                    if is_template_document_intent(tstrip):
                        tr, t_body, t_clarify = parse_template_document_request(
                            tstrip, get_last_assistant_text(db, app_user_id)
                        )
                        if t_clarify:
                            await update.message.reply_text(t_clarify[:2000])
                            cctx = get_or_create_context(db, app_user_id)
                            _persist_conversation_turn(
                                db, app_user_id, cctx, tstrip, t_clarify, "document_clarify", "nexa"
                            )
                            return
                        if tr and t_body:
                            try:
                                art = generate_document(
                                    db,
                                    title=tr.label,
                                    body_markdown=t_body,
                                    format=tr.format,
                                    user_id=app_user_id,
                                    source_type=tr.source_type,
                                    source_ref="template_intent_tg",
                                )
                            except DocumentGenerationError as e:
                                await update.message.reply_text(str(e)[:2000])
                                return
                            path = get_document_path_for_owner(db, art.id, app_user_id)
                            if path and path.is_file():
                                with path.open("rb") as f:
                                    await update.message.reply_document(
                                        document=InputFile(f, filename=path.name),
                                        caption=f"{tr.label} — created as {tr.format.upper()} in Nexa (document #{art.id})",
                                    )
                            else:
                                await update.message.reply_text(
                                    f"Created {tr.label} (document #{art.id}), but the file was not on disk. Try /doc or export again."
                                )
                            cctx = get_or_create_context(db, app_user_id)
                            _persist_conversation_turn(
                                db,
                                app_user_id,
                                cctx,
                                tstrip,
                                f"Created {tr.label} as {tr.format} (id {art.id}).",
                                "document_create",
                                "nexa",
                            )
                            return
                if not tstrip.startswith("/") and tstrip:
                    from telegram import InputFile
    
                    from app.services.document_export_intent import detect_natural_export_format
                    from app.services.document_generation import (
                        DocumentGenerationError,
                        generate_document,
                        get_document_path_for_owner,
                    )
    
                    nfmt = detect_natural_export_format(tstrip)
                    if nfmt:
                        last = get_last_assistant_text(db, app_user_id)
                        if not last:
                            await update.message.reply_text(
                                "What should I put in the file? Ask me something first, or paste the text you want exported."
                            )
                            return
                        try:
                            art = generate_document(
                                db,
                                title="Nexa export",
                                body_markdown=last,
                                format=nfmt,
                                user_id=app_user_id,
                                source_type="chat",
                                source_ref="nl_export",
                            )
                        except DocumentGenerationError as e:
                            await update.message.reply_text(str(e)[:2000])
                            return
                        path = get_document_path_for_owner(db, art.id, app_user_id)
                        if not path or not path.is_file():
                            await update.message.reply_text("Could not read the generated file. Try /doc create pdf")
                            return
                        with path.open("rb") as f:
                            await update.message.reply_document(
                                document=InputFile(f, filename=path.name),
                                caption=f"Done — exported your last reply as {nfmt.upper()}. (document #{art.id})",
                            )
                        return
                p_rev = udata.get("pending_dev_revision_job_id")
                if p_rev and not tstrip.startswith("/"):
                    ar = job_service.apply_revision_and_requeue(
                        db, app_user_id, int(p_rev), tstrip
                    )
                    if ar:
                        if context.user_data is not None:
                            context.user_data["pending_dev_revision_job_id"] = None
                        nrev = (dict(ar.payload_json or {}) or {}).get("revision_count", 1)
                        await update.message.reply_text(
                            f"Saved revision #{nrev} and re-queued job #{ar.id} (approved). "
                            f"The host worker will run the agent on the same branch. Track job #{ar.id} in chat or on the web app."
                        )
                        return
                    if context.user_data is not None:
                        context.user_data["pending_dev_revision_job_id"] = None
                    await update.message.reply_text(
                        "I could not save that revision (state changed or the job is not open for changes). "
                        "Try **Request changes** again on the last approval message, or ask to list recent jobs."
                    )
                    return
    
                if not tstrip.startswith("/") and tstrip:
                    from app.services.agent_runtime.boss_chat import try_spawn_lifecycle_chat_turn

                    _spawn_turn = try_spawn_lifecycle_chat_turn(db, app_user_id, tstrip)
                    if _spawn_turn is not None:
                        cctx_sp = get_or_create_context(db, app_user_id)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx_sp,
                            tstrip,
                            _spawn_turn,
                            "boss_spawn_lifecycle",
                            "boss",
                        )
                        for _sp in _split_telegram_text(_spawn_turn, max_len=4000):
                            await update.message.reply_text(_sp)
                        return

                mr = parse_mention(tstrip)
                if mr.is_explicit and mr.error:
                    from app.services.custom_agents import (
                        format_unknown_with_custom,
                        get_custom_agent,
                        normalize_agent_key,
                        run_custom_user_agent,
                    )
                    from app.services.mention_control import format_unknown_mention_message
    
                    raws = (mr.raw_mention or "unknown").strip()
                    k0 = normalize_agent_key(raws)
                    uag = get_custom_agent(db, app_user_id, k0)
                    m_body0 = (mr.text or "").strip()
                    if uag and not uag.is_active:
                        await update.message.reply_text(
                            f"`@{k0}` is **disabled**. Say **enable @{k0}** to turn it back on."
                        )
                        return
                    if uag and uag.is_active and m_body0:
                        from app.services.agent_runtime.boss_chat import (
                            is_boss_agent_key,
                            try_boss_runtime_chat_turn,
                        )
                        from app.services.custom_agent_routing import (
                            reply_for_custom_agent_path_clarification,
                        )
                        from app.services.local_file_intent import infer_local_file_request

                        rep0: str | None = None
                        if is_boss_agent_key(uag.agent_key):
                            rep0 = try_boss_runtime_chat_turn(
                                db, app_user_id, m_body0
                            )
                        if rep0 is None:
                            lf_tg = infer_local_file_request(
                                m_body0, default_relative_base="."
                            )
                            if lf_tg.matched and lf_tg.error_message:
                                rep0 = lf_tg.error_message
                            elif lf_tg.matched and lf_tg.clarification_message:
                                rep0 = reply_for_custom_agent_path_clarification(
                                    uag.agent_key, lf_tg
                                )
                            else:
                                rep0 = run_custom_user_agent(
                                    db,
                                    app_user_id,
                                    uag,
                                    m_body0,
                                    source="telegram_mention",
                                )
                        cctx0 = get_or_create_context(db, app_user_id)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx0,
                            tstrip,
                            rep0,
                            "custom_user_agent",
                            uag.agent_key,
                        )
                        for piece0 in _split_telegram_text(rep0, max_len=4000):
                            await update.message.reply_text(piece0)
                        return
                    if uag and uag.is_active and not m_body0:
                        await update.message.reply_text(
                            f"Add a message after `@{k0}` (your custom agent)."
                        )
                        return
                    ntxt = format_unknown_with_custom(
                        format_unknown_mention_message(raws),
                        db,
                        app_user_id,
                    )
                    for un_p in _split_telegram_text(ntxt, max_len=4000):
                        await update.message.reply_text(un_p)
                    return
                if mr.is_explicit and not mr.error and mr.agent_key:
                    cctx_m = get_or_create_context(db, app_user_id)
                    snap_m = build_context_snapshot(cctx_m, db)
                    m_key = map_catalog_key_to_internal(mr.agent_key)
                    m_body = (mr.text or "").strip()
                    if not m_body:
                        await update.message.reply_text(
                            "Add a message after your @mention — e.g. `@nexa hello` or `run dev: fix the tests`."
                        )
                        return
                    if m_key == "strategy":
                        sb = try_strategy_workflow(m_body, db=db, cctx=cctx_m)
                        if sb is not None:
                            await update.message.reply_text(sb)
                            _persist_conversation_turn(
                                db, app_user_id, cctx_m, tstrip, sb, "idea_workflow", m_key
                            )
                            return
                    if m_key == "marketing":
                        mb = try_marketing_workflow(m_body, db=db, cctx=cctx_m)
                        if mb is not None:
                            await update.message.reply_text(mb)
                            _persist_conversation_turn(
                                db, app_user_id, cctx_m, tstrip, mb, "idea_workflow", m_key
                            )
                            return
                    if m_key == "ops":
                        from app.services.telegram_dev_ux import format_job_row_short
    
                        ops_b = handle_nexa_ops_mention(
                            db,
                            app_user_id,
                            m_body,
                            telegram_chat_id=telegram_chat_id,
                            cctx=cctx_m,
                            list_jobs=job_service.list_jobs,
                            format_job_row_short=format_job_row_short,
                            requester_role=tg_role,
                        )
                        for piece in _split_telegram_text(ops_b[:12_000], max_len=4000):
                            await update.message.reply_text(piece)
                        _persist_conversation_turn(
                            db, app_user_id, cctx_m, tstrip, ops_b, "ops_mention", "ops"
                        )
                        return
                    if m_key == "developer":
                        is_st = bool(
                            re.match(r"^status\.?$", m_body.strip(), re.IGNORECASE)
                        )
                        if (tg_role or "") == "guest":
                            _deny(
                                db,
                                telegram_id=effu.id,
                                app_user=app_user_id,
                                uname=effu.username,
                                family="at_dev",
                                reason="guest",
                                preview=(m_body or "")[:50],
                            )
                            await update.message.reply_text(DEV_EXECUTION_RESTRICTED)
                            return
                        if is_st and is_trusted_or_owner(tg_role):
                            from app.services.telegram_dev_ux import format_dev_agent_status_telegram
    
                            smsg = format_dev_agent_status_telegram(db, app_user_id)
                            await update.message.reply_text(smsg)
                            _persist_conversation_turn(
                                db, app_user_id, cctx_m, tstrip, smsg, "dev_status", "developer"
                            )
                            return
                        if not is_owner_role(tg_role):
                            _deny(
                                db,
                                telegram_id=effu.id,
                                app_user=app_user_id,
                                uname=effu.username,
                                family="at_dev",
                                reason="not_owner",
                                preview=(m_body or "")[:50],
                            )
                            await update.message.reply_text(DEV_EXECUTION_RESTRICTED)
                            return
                        scp = try_dev_scope_workflow(m_body, db=db, cctx=cctx_m)
                        if scp is not None:
                            await update.message.reply_text(scp)
                            _persist_conversation_turn(
                                db, app_user_id, cctx_m, tstrip, scp, "idea_workflow", "developer"
                            )
                            return
                        m_dev_create = re.match(
                            r"(?i)^create\s+project\s+([a-z0-9][a-z0-9_\-]*)\s*$",
                            m_body.strip(),
                        )
                        if m_dev_create:
                            from app.services.idea_project_service import queue_dev_workspace_scaffold
    
                            cmsg = queue_dev_workspace_scaffold(
                                db,
                                app_user_id,
                                m_dev_create.group(1).strip().lower(),
                                telegram_chat_id=telegram_chat_id,
                            )
                            await update.message.reply_text(cmsg)
                            _persist_conversation_turn(
                                db, app_user_id, cctx_m, tstrip, cmsg, "dev_create_project", "developer"
                            )
                            return
                        from pathlib import Path
    
                        from app.services.project_parser import parse_dev_project_phrase
                        from app.services.project_registry import (
                            get_default_project,
                            get_project_by_key,
                            list_project_keys,
                        )
    
                        if is_dev_task_message(m_body):
                            title, description = parse_dev_task(m_body)
                        else:
                            title = _title_from_instruction(
                                m_body, fallback="Dev @mention"
                            )
                            description = m_body
                        _keys = list_project_keys(db)
                        _pkey, _in_inst = parse_dev_project_phrase(
                            m_body, known_project_keys=_keys
                        )
                        if _pkey and _in_inst.strip() and _in_inst.strip() != m_body.strip():
                            description = _in_inst.strip()
                            title = _title_from_instruction(
                                description, fallback="Dev @mention"
                            )
                        _proj = get_project_by_key(db, _pkey) if _pkey else get_default_project(
                            db
                        )
                        if _pkey and _proj is None:
                            await update.message.reply_text(
                                f"Unknown project `{_pkey}`. Use /projects to see keys or `/project add`."
                            )
                            return
                        if _proj is None:
                            await update.message.reply_text("No project configured. Run migrations / seed or /project add.")
                            return
                        _repo = (getattr(_proj, "repo_path", None) or "").strip()
                        if _pkey and _repo:
                            _rp = Path(_repo).expanduser().resolve()
                            if not _rp.is_dir() or not ( (_rp / ".git").is_dir() or (_rp/".git").is_file() ):
                                await update.message.reply_text(
                                    f"Project `{_proj.key}` does not have a valid git `repo_path` on this host: `{_repo}`"
                                )
                                return
                        _task_body = f"{title}\n{description}".strip()
                        try:
                            _result = create_planned_dev_job(
                                db,
                                user_id=app_user_id,
                                telegram_chat_id=telegram_chat_id,
                                task_text=_task_body,
                                project_key=_proj.key,
                                source="telegram_mention",
                                title=title,
                                instruction=description,
                                extra_payload={"source": "developer_mention", "via": "mention_control"},
                                job_service=job_service,
                            )
                        except ValueError as e:
                            await update.message.reply_text(str(e)[:2000])
                            return
                        djob = _result["job"]
                        _dec = _result["plan"]["decision"]
                        _ac = _result["agent_job_create"]
                        _link_dev_loop_agent_run(db, app_user_id, djob, _ac)
                        if await _reply_dev_job_queued_or_blocked(update, djob):
                            return
                        msg = format_planned_dev_reply(
                            plan_message=_result["message"],
                            job_id=djob.id,
                            decision=_dec,
                            repo_line=_repo or None,
                        )
                        await update.message.reply_text(msg)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx_m,
                            tstrip,
                            msg,
                            "dev_command",
                            "developer",
                            decision_extras={"job": djob},
                        )
                        return
                    body = handle_agent_mention(
                        db,
                        app_user_id,
                        m_key,
                        m_body,
                        memory_service=memory_service,
                        orchestrator=orchestrator,
                        conversation_snapshot=snap_m,
                    )
                    await update.message.reply_text(body)
                    _persist_conversation_turn(
                        db, app_user_id, cctx_m, tstrip, body, "general_chat", m_key
                    )
                    return
    
                if tlow == "approve despite failed tests":
                    if not is_owner_role(tg_role):
                        _deny(
                            db,
                            telegram_id=effu.id,
                            app_user=app_user_id,
                            uname=effu.username,
                            family="approve",
                            reason="not_owner",
                            preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    rows = job_service.list_jobs(db, app_user_id, limit=40)
                    j_ov = next(
                        (
                            r
                            for r in rows
                            if (r.worker_type or "") == "dev_executor"
                            and (r.status or "") == "failed"
                            and (r.tests_status or "") == "failed"
                        ),
                        None,
                    )
                    if not j_ov:
                        await update.message.reply_text(
                            "No `failed` dev job with failed tests found. List recent jobs first, or use this after the worker "
                            "reports a test failure."
                        )
                        return
                    o = job_service.mark_waiting_approval_despite_failed_tests(
                        db, app_user_id, j_ov.id
                    )
                    if not o:
                        await update.message.reply_text("Could not open approval for that job (check ownership).")
                        return
                    from app.services.aider_autonomous_loop import (
                        approval_inline_markup,
                        format_approval_message,
                    )
                    from app.services.telegram_outbound import send_telegram_message
    
                    rtxt = (o.result or "")[:12_000]
                    chat = str(update.effective_chat.id)
                    send_telegram_message(
                        chat,
                        (format_approval_message(o, rtxt) or "")[:3900],
                        max_len=4000,
                        reply_markup=approval_inline_markup(o.id),
                    )
                    await update.message.reply_text(
                        "Okay — I will allow approval despite failed tests. Review the branch and diff on the host before you tap Approve."
                    )
                    return
    
                if re.match(r"^/dev\s+health", tlow):
                    if not can_read_dev_stack_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="read_stack", preview=tlow[:50],
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.worker_heartbeat import build_dev_health_report
    
                    for piece in _split_telegram_text(
                        build_dev_health_report()[:12_000], max_len=4000
                    ):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^/dev\s+status\s*$", tlow, re.IGNORECASE):
                    if not can_read_dev_stack_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="read_stack", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.telegram_dev_ux import format_dev_agent_status_telegram
    
                    for piece in _split_telegram_text(
                        format_dev_agent_status_telegram(db, app_user_id)[:12_000], max_len=4000
                    ):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^/dev\s+tools\s*$", tlow, re.IGNORECASE):
                    if not can_read_dev_stack_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="read_stack", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.dev_tools.formatting import format_dev_tools
    
                    for piece in _split_telegram_text(format_dev_tools()[:12_000], max_len=4000):
                        await update.message.reply_text(piece)
                    return
                m_dev_open = re.match(r"^/dev\s+open(?:\s+(\S+))?\s*$", tlow, re.IGNORECASE)
                if m_dev_open:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_open", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.dev_tools.project_open import open_project_with_tool
    
                    key = (m_dev_open.group(1) or "").strip().lower() or None
                    out = open_project_with_tool(db, key)
                    for piece in _split_telegram_text(out[:12_000], max_len=4000):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^/dev\s+workspace\s*$", tlow, re.IGNORECASE):
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_workspace", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.telegram_project_commands import format_dev_workspace
    
                    for piece in _split_telegram_text(
                        format_dev_workspace(db)[:12_000], max_len=4000
                    ):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^(/dev|/system)\s+doctor", tlow):
                    if not can_use_dev_doctor_or_git(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_doctor", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.nexa_doctor import build_nexa_doctor_text
    
                    body = build_nexa_doctor_text(
                        db, app_user_id, telegram_user_id=effu.id
                    )[:12_000]
                    for piece in _split_telegram_text(body, max_len=4000):
                        await update.message.reply_text(piece)
                    return
                m_dev_git = re.match(r"^/dev\s+git", tlow)
                if m_dev_git or re.match(r"^/git(\s+status)?\s*$", tlow, re.IGNORECASE):
                    if not can_use_dev_doctor_or_git(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_git", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.nexa_doctor import format_git_brief
    
                    body = format_git_brief()[:12_000]
                    for piece in _split_telegram_text(body, max_len=4000):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^/dev\s+queue", tlow):
                    if not can_list_dev_jobs_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_queue", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.telegram_dev_ux import format_grouped_dev_queue
    
                    rows = job_service.list_jobs(db, app_user_id, limit=40)
                    de = [j for j in rows if (j.worker_type or "") == "dev_executor"]
                    if not de:
                        await update.message.reply_text("No dev jobs in your recent list.")
                        return
                    block = format_grouped_dev_queue(rows)[:12_000]
                    for piece in _split_telegram_text(block, max_len=4000):
                        await update.message.reply_text(piece)
                    return
                if re.match(r"^/dev\s+pause", tlow):
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_pause", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.worker_state import set_worker_paused
    
                    set_worker_paused()
                    await update.message.reply_text("Pause set. The host worker will not start new `approved` jobs until `/dev resume`.")
                    return
                if re.match(r"^/dev\s+resume", tlow):
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_resume", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.worker_state import clear_worker_paused
    
                    clear_worker_paused()
                    await update.message.reply_text("Resume: pause flag cleared.")
                    return
                if re.match(r"^/dev\s+stop", tlow):
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_stop", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.worker_state import set_stop_after_current
    
                    set_stop_after_current()
                    await update.message.reply_text(
                        "Stop-after-current: new `approved` work will be skipped on the host until you delete "
                        "`.runtime/dev_worker_stop_after_current` or we add a clear command next."
                    )
                    return
                mhr = re.match(r"^approve high risk job\s*#?(\d+)\s*$", tlow)
                if mhr:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="job", reason="high_risk", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    j = job_service.approve_high_risk(db, app_user_id, int(mhr.group(1)))
                    await update.message.reply_text(
                        f"Job #{j.id} is now `{j.status}`. Reply: `approve job #{j.id}` to run the dev worker."
                    )
                    return
    
                # Aider autonomous loop: latest job in waiting_approval (one word, no job id)
                if tlow in {"approve", "yes"} and tstrip.count(" ") == 0:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="approve", reason="one_word_approve", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    j_approve = job_service.mark_autonomous_approved(db, app_user_id)
                    if j_approve:
                        await update.message.reply_text(
                            f"Approved job #{j_approve.id} for commit. "
                            "The next `dev_agent_executor` run will commit on the feature branch (status: approved_to_commit)."
                        )
                        return
                if tlow == "reject" and tstrip.count(" ") == 0:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="reject", reason="one_word", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    j_rej = job_service.mark_autonomous_rejected(db, app_user_id)
                    if j_rej:
                        await update.message.reply_text(
                            f"Job #{j_rej.id} rejected. Working tree was reset to the pre-agent snapshot where possible. "
                            f"Status: {j_rej.status}."
                        )
                        return
                if tlow in {"show diff", "showdiff"} or tlow == "diff":
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="git", reason="host_diff", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    from app.services.aider_autonomous_loop import get_git_diff_capped
    
                    body = get_git_diff_capped(3500) or "[empty diff]"
                    for piece in _split_telegram_text(
                        "Git diff (host repo, current branch; best-effort on this process):\n\n" + body
                    ):
                        await update.message.reply_text(piece)
                    return
    
                if tlow == "/dev-status":
                    if not can_list_dev_jobs_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_status", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    rows = job_service.list_jobs(db, app_user_id, limit=5)
                    if not rows:
                        await update.message.reply_text("No queued or recent jobs yet.")
                        return
                    out = "\n\n---\n\n".join(_format_job_line(job) for job in rows)
                    for piece in _split_telegram_text(out):
                        await update.message.reply_text(piece)
                    return
    
                approve_match = re.match(r"^(approve|deny)\s+job\s*#?(\d+)$", tlow)
                if approve_match:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="approve", reason="job_line", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    decision = "approve" if approve_match.group(1) == "approve" else "deny"
                    job_id = int(approve_match.group(2))
                    a_ops = process_ops_job_decision(
                        db, job_service, app_user_id, job_id, decision
                    )
                    if a_ops is not None:
                        await update.message.reply_text(a_ops)
                        return
                    job = job_service.decide(db, app_user_id, job_id, decision)
                    if decision == "approve" and (getattr(job, "worker_type", None) or "") == "dev_executor":
                        pl = dict(getattr(job, "payload_json", None) or {})
                        ed = pl.get("execution_decision") or {}
                        tool = ed.get("tool_key") or pl.get("preferred_dev_tool") or "—"
                        mode = ed.get("mode") or pl.get("dev_execution_mode") or "—"
                        pk = (pl.get("project_key") or "nexa") or "nexa"
                        await update.message.reply_text(
                            f"Dev Agent accepted job #{job.id}.\n\n"
                            f"Project: `{pk}`\n"
                            f"Tool: `{tool}`\n"
                            f"Mode: `{mode}`\n"
                            f"Status: queued for worker.\n"
                        )
                    else:
                        await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
                    return
    
                approve_review_match = re.match(r"^approve\s+review\s+job\s*#?(\d+)$", tlow)
                if approve_review_match:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="approve", reason="review", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    job = job_service.approve_review(db, app_user_id, int(approve_review_match.group(1)))
                    await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
                    return
    
                approve_commit_match = re.match(r"^approve\s+commit\s+job\s*#?(\d+)$", tlow)
                if approve_commit_match:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="approve", reason="commit", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    job = job_service.approve_commit(db, app_user_id, int(approve_commit_match.group(1)))
                    await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
                    return
    
                cancel_match = re.match(r"^cancel\s+job\s*#?(\d+)$", tlow)
                if cancel_match:
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="cancel", reason="job", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    job = job_service.cancel(db, app_user_id, int(cancel_match.group(1)))
                    await update.message.reply_text(f"Job #{job.id} is now {job.status}.")
                    return
    
                if tlow in {"latest job", "show latest job", "job latest"}:
                    if not can_list_dev_jobs_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="job", reason="text_latest", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    job = job_service.get_latest(db, app_user_id)
                    if not job:
                        await update.message.reply_text("No jobs yet.")
                        return
                    await update.message.reply_text(_format_job_line(job))
                    return
    
                job_match = re.match(r"^job\s*#?(\d+)$", tlow)
                if job_match:
                    if not can_list_dev_jobs_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="job", reason="text_jobid", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    job = job_service.get_job(db, app_user_id, int(job_match.group(1)))
                    await update.message.reply_text(_format_job_line(job))
                    return
    
                is_new_dev_request = is_dev_task_message(text) or is_cursor_request(text)
                if _is_job_status_followup(tlow, tstrip, is_new_dev_request=is_new_dev_request):
                    if not can_list_dev_jobs_commands(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="job", reason="status_followup", preview=tlow[:50],
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    jid = _first_agent_job_id_in_text(tstrip)
                    if jid is not None:
                        row = job_service.repo.get(db, jid, user_id=app_user_id)
                        if row:
                            await update.message.reply_text(
                                f"Autonomous / dev job (this is the job queue, not saved chat memory):\n\n{_format_job_line(row)}"
                            )
                        else:
                            await update.message.reply_text(
                                f"Job #{jid} not found for you (wrong id or different account). "
                                "Ask to list recent job numbers or say **recent jobs**."
                            )
                    else:
                        j = job_service.get_latest(db, app_user_id)
                        if j:
                            await update.message.reply_text(
                                f"No job # in that message. Your most recent autonomous / dev job is below — "
                                f"for a specific id, say job #{j.id} or ask about job {j.id}. (Daily tasks/notes are separate.)\n\n"
                                f"{_format_job_line(j)}"
                            )
                        else:
                            await update.message.reply_text(
                                "No job # in that text and you have no dev jobs in the list yet. "
                                "Start one with /improve … or describe the coding task (`run dev:` on web). Ask for your jobs list anytime. "
                                "I do not store these jobs in the same memory as your plan/task notes."
                            )
                    return
    
                if tlow.startswith("/dev") and tlow != "/dev-status":
                    if not is_owner_role(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="dev_parsed", preview=tlow[:50],
                        )
                        await update.message.reply_text(DEV_EXECUTION_RESTRICTED)
                        return
                    try:
                        parsed = parse_local_action(text)
                        cmd = parsed["command_type"]
                        inst = parsed["instruction"]
                        if cmd in _DEV_EXECUTOR_COMMANDS:
                            tit_cmd = _title_from_instruction(
                                inst, fallback=cmd.replace("-", " ")
                            )
                            task_body_cmd = f"{tit_cmd}\n{inst}".strip()
                            try:
                                res_cmd = create_planned_dev_job(
                                    db,
                                    user_id=app_user_id,
                                    telegram_chat_id=telegram_chat_id,
                                    task_text=task_body_cmd,
                                    project_key=None,
                                    source="telegram",
                                    title=tit_cmd,
                                    instruction=inst,
                                    extra_payload={"source_dev_command": cmd},
                                    job_service=job_service,
                                )
                            except ValueError as e:
                                await update.message.reply_text(str(e)[:2000])
                                return
                            job = res_cmd["job"]
                            ac = res_cmd["agent_job_create"]
                            _link_dev_loop_agent_run(db, app_user_id, job, ac)
                            if await _reply_dev_job_queued_or_blocked(update, job):
                                return
                            msg_cmd = format_planned_dev_reply(
                                plan_message=res_cmd["message"],
                                job_id=job.id,
                                decision=res_cmd["plan"]["decision"],
                                repo_line=None,
                            )
                            await update.message.reply_text(
                                f"{msg_cmd}\n\n(`{cmd}` — same Dev Agent job queue as /improve.)"
                            )
                        else:
                            job = job_service.create_job(
                                db,
                                app_user_id,
                                AgentJobCreate(
                                    kind="local_action",
                                    worker_type="local_tool",
                                    title=cmd,
                                    instruction=inst,
                                    command_type=cmd,
                                    payload_json={},
                                    source="telegram",
                                    telegram_chat_id=telegram_chat_id,
                                ),
                            )
                            await update.message.reply_text(
                                f"Queued job #{job.id}: {cmd}\n\n"
                                + (
                                    "This one needs approval first. Reply `approve job #{}` to run it.".format(
                                        job.id
                                    )
                                    if job.status == "needs_approval"
                                    else "Run: python scripts/local_tool_worker.py"
                                )
                            )
                        return
                    except ValueError as exc:
                        err = str(exc)
                        if "Missing dev command" in err or "Not a dev command" in err:
                            await update.message.reply_text(
                                f"{err}\n\n"
                                "Examples: /dev run-tests  |  /dev create-cursor-task <instruction>  |  /dev-status"
                            )
                            return
                        if "needs an instruction" in err.lower():
                            await update.message.reply_text(err)
                            return
                        if "Unsupported command" in err:
                            if is_dev_task_message(text):
                                from app.services.project_parser import parse_dev_project_phrase
                                from app.services.project_registry import list_project_keys
    
                                title, description = parse_dev_task(text)
                                _keys_u = list_project_keys(db)
                                pk_u, _ = parse_dev_project_phrase(
                                    text, known_project_keys=_keys_u
                                )
                                tb_u = f"{title}\n{description}".strip()
                                try:
                                    res_u = create_planned_dev_job(
                                        db,
                                        user_id=app_user_id,
                                        telegram_chat_id=telegram_chat_id,
                                        task_text=tb_u,
                                        project_key=pk_u,
                                        source="telegram",
                                        title=title,
                                        instruction=description,
                                        extra_payload={},
                                        job_service=job_service,
                                    )
                                except ValueError as e:
                                    await update.message.reply_text(str(e)[:2000])
                                    return
                                job = res_u["job"]
                                _link_dev_loop_agent_run(db, app_user_id, job, res_u["agent_job_create"])
                                if await _reply_dev_job_queued_or_blocked(update, job):
                                    return
                                await update.message.reply_text(
                                    format_planned_dev_reply(
                                        plan_message=res_u["message"],
                                        job_id=job.id,
                                        decision=res_u["plan"]["decision"],
                                        repo_line=None,
                                    )
                                )
                            else:
                                await update.message.reply_text(err)
                            return
                        await update.message.reply_text(f"Could not queue dev action: {err}")
                        return
    
                if is_dev_task_message(text):
                    if not can_run_dev_agent_jobs(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="improve_verb", preview=text[:50],
                        )
                        await update.message.reply_text(DEV_EXECUTION_RESTRICTED)
                        return
                    from app.services.project_parser import parse_dev_project_phrase
                    from app.services.project_registry import list_project_keys
    
                    title, description = parse_dev_task(text)
                    _keys_i = list_project_keys(db)
                    pk_i, _ = parse_dev_project_phrase(text, known_project_keys=_keys_i)
                    tb_i = f"{title}\n{description}".strip()
                    try:
                        res_i = create_planned_dev_job(
                            db,
                            user_id=app_user_id,
                            telegram_chat_id=telegram_chat_id,
                            task_text=tb_i,
                            project_key=pk_i,
                            source="telegram",
                            title=title,
                            instruction=description,
                            extra_payload={},
                            job_service=job_service,
                        )
                    except ValueError as e:
                        await update.message.reply_text(str(e)[:2000])
                        return
                    job = res_i["job"]
                    _link_dev_loop_agent_run(db, app_user_id, job, res_i["agent_job_create"])
                    if await _reply_dev_job_queued_or_blocked(update, job):
                        return
                    await update.message.reply_text(
                        format_planned_dev_reply(
                            plan_message=res_i["message"],
                            job_id=job.id,
                            decision=res_i["plan"]["decision"],
                            repo_line=None,
                        )
                    )
                    return
    
                if is_cursor_request(text):
                    if not can_run_dev_agent_jobs(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="dev", reason="cursor_nl", preview=text[:50],
                        )
                        await update.message.reply_text(DEV_EXECUTION_RESTRICTED)
                        return
                    from app.services.project_parser import parse_dev_project_phrase
                    from app.services.project_registry import list_project_keys
    
                    replied_text = None
                    if update.message.reply_to_message and update.message.reply_to_message.text:
                        replied_text = update.message.reply_to_message.text
                    instruction, needs_more_detail = build_cursor_instruction(text, replied_text=replied_text)
                    if needs_more_detail:
                        await update.message.reply_text(
                            "I can queue a Dev Agent job, but I need one more sentence with the actual task."
                        )
                        return
                    tit = _title_from_instruction(
                        instruction, fallback="Dev Agent request from chat"
                    )
                    _keys_nl = list_project_keys(db)
                    pk_nl, inst_core = parse_dev_project_phrase(
                        instruction, known_project_keys=_keys_nl
                    )
                    instr_final = (inst_core or "").strip() or instruction.strip()
                    task_body_nl = f"{tit}\n{instr_final}".strip()
                    try:
                        res_nl = create_planned_dev_job(
                            db,
                            user_id=app_user_id,
                            telegram_chat_id=telegram_chat_id,
                            task_text=task_body_nl,
                            project_key=pk_nl,
                            source="telegram",
                            title=tit,
                            instruction=instr_final,
                            extra_payload={
                                "source": "cursor_natural_language",
                                "autonomous_handoff": True,
                            },
                            job_service=job_service,
                        )
                    except ValueError as e:
                        await update.message.reply_text(str(e)[:2000])
                        return
                    job = res_nl["job"]
                    _link_dev_loop_agent_run(db, app_user_id, job, res_nl["agent_job_create"])
                    if await _reply_dev_job_queued_or_blocked(update, job):
                        return
                    await update.message.reply_text(
                        format_planned_dev_reply(
                            plan_message=res_nl["message"],
                            job_id=job.id,
                            decision=res_nl["plan"]["decision"],
                            repo_line=None,
                        )
                    )
                    return
    
                cctx = get_or_create_context(db, app_user_id)
                topic_i = apply_topic_intent_to_context(cctx, tstrip)
                if topic_i is not None:
                    short = short_reply_for_topic_intent(topic_i)
                    db.add(cctx)
                    db.flush()
                    snap_topic = build_context_snapshot(cctx, db)
                    rt_topic = route_agent(tstrip, context_snapshot=snap_topic)
                    rt_topic = apply_memory_aware_route_adjustment(
                        rt_topic, tstrip, snap_topic, db
                    )
                    rkey_topic = str(rt_topic.get("agent_key") or "nexa")
                    await update.message.reply_text(short)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, short, "topic_control", rkey_topic
                    )
                    return
    
                memory_command = _extract_memory_command(text)
                if memory_command:
                    kind, payload = memory_command
                    if kind in ("remember", "forget") and not can_memory_working_remember_forget(
                        tg_role
                    ):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="memory_nl", reason=kind, preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    if kind == "soul" and not can_write_global_memory_file(tg_role):
                        _deny(
                            db, telegram_id=effu.id, app_user=app_user_id, uname=effu.username,
                            family="soul_nl", reason="soul", preview=None,
                        )
                        await update.message.reply_text(ACCESS_RESTRICTED)
                        return
                    if kind == "remember":
                        note = memory_service.remember_note(db, app_user_id, payload, category="user_note", source="telegram")
                        await update.message.reply_text(f"I saved that to memory: {note.summary}")
                        return
                    if kind == "forget":
                        result = memory_service.forget(db, app_user_id, payload)
                        await update.message.reply_text(
                            "I removed that from working memory."
                            f"\nNotes removed: {result.deleted_notes}"
                            f"\nTasks removed: {result.deleted_tasks}"
                            f"\nFollow-ups cancelled: {result.cancelled_checkins}"
                        )
                        return
                    if kind == "soul":
                        content = memory_service.get_soul_markdown(db, app_user_id)
                        updated = memory_service.update_soul_markdown(
                            db,
                            app_user_id,
                            content + "\n- " + payload.strip(),
                            source="telegram",
                        )
                        await update.message.reply_text("I updated my soul rules for you.")
                        logger.info("soul_updated chars=%s", len(updated))
                        return
    
                snap = build_context_snapshot(cctx, db)
                rt = route_agent(tstrip, context_snapshot=snap)
                rt = apply_memory_aware_route_adjustment(rt, tstrip, snap, db)
                routed_key = str(rt.get("agent_key") or "nexa")
    
                from app.services.custom_agent_routing import try_deterministic_custom_agent_turn
                from app.services.multi_agent_routing import (
                    is_multi_agent_capability_question,
                    reply_multi_agent_capability_clarification,
                )

                if is_multi_agent_capability_question(tstrip):
                    ma_txt = reply_multi_agent_capability_clarification()
                    await update.message.reply_text(ma_txt)
                    _persist_conversation_turn(
                        db,
                        app_user_id,
                        cctx,
                        tstrip,
                        ma_txt,
                        "capability_question",
                        routed_key,
                    )
                    return

                _ca_dm = try_deterministic_custom_agent_turn(db, app_user_id, tstrip)
                if _ca_dm is not None:
                    await update.message.reply_text(_ca_dm)
                    _persist_conversation_turn(
                        db,
                        app_user_id,
                        cctx,
                        tstrip,
                        _ca_dm,
                        "custom_agent",
                        routed_key,
                    )
                    return

                from app.services.agent_team import try_agent_team_chat_turn

                _team_dm = try_agent_team_chat_turn(
                    db, app_user_id, tstrip, web_session_id=None
                )
                if _team_dm is not None:
                    await update.message.reply_text(_team_dm.reply)
                    _persist_conversation_turn(
                        db,
                        app_user_id,
                        cctx,
                        tstrip,
                        _team_dm.reply,
                        "agent_team",
                        routed_key,
                    )
                    return

                from app.services.next_action_apply import apply_next_action_to_user_text
    
                _na = apply_next_action_to_user_text(
                    db, cctx, tstrip, web_session_id=getattr(cctx, "session_id", None)
                )
                if _na.early_assistant is not None:
                    await update.message.reply_text(_na.early_assistant)
                    _persist_conversation_turn(
                        db,
                        app_user_id,
                        cctx,
                        tstrip,
                        _na.early_assistant,
                        "next_action",
                        routed_key,
                    )
                    return
                tstrip = (_na.user_text_for_pipeline or tstrip or "").strip()
                text = tstrip
    
                if is_simple_greeting(tstrip):
                    gr = simple_greeting_reply(tstrip)
                    await update.message.reply_text(gr)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, gr, "general_chat", routed_key
                    )
                    return
                if is_casual_capability_question(tstrip):
                    cr = casual_capability_reply()
                    await update.message.reply_text(cr)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, cr, "general_chat", routed_key
                    )
                    return
                if is_command_question(tstrip):
                    ch = format_command_help_response()
                    await update.message.reply_text(ch)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, ch, "general_chat", routed_key
                    )
                    return
    
                if is_weak_input(tstrip):
                    ctx_weak = build_context(db, app_user_id, memory_service, orchestrator)
                    logger.info("incoming weak_input text_preview=%r", tstrip[:120])
                    reply = weak_input_response()
                    out = apply_tone(reply, ctx_weak.memory)
                    await update.message.reply_text(out)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, out, "general_chat", routed_key
                    )
                    return
    
                if is_create_project_confirmation(tstrip):
                    cpc = commit_pending_idea_as_project(db, app_user_id, cctx)
                    await update.message.reply_text(cpc)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, cpc, "idea_create", routed_key
                    )
                    return
                cr_key = match_create_repo_request(tstrip)
                if cr_key:
                    crr = queue_create_repo_approval(
                        db,
                        app_user_id,
                        cr_key,
                        telegram_chat_id=telegram_chat_id,
                    )
                    await update.message.reply_text(crr)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, crr, "create_repo_approval", routed_key
                    )
                    return
                if looks_like_new_idea(tstrip):
                    ex = extract_idea_summary(tstrip)
                    pl = build_pending_project_payload(ex)
                    set_pending_project(cctx, pl)
                    db.add(cctx)
                    db.commit()
                    idr = format_idea_draft_reply(pl)
                    await update.message.reply_text(idr)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, idr, "idea_intake", routed_key
                    )
                    return
    
                async with typing_indicator(
                    update, context, interval_seconds=3.0, min_visible_seconds=1.2
                ):
                    _ack_pre: list[str | None] = [_na.inject_ack]
    
                    def _wrap_tg_inject_ack(m: str) -> str:
                        a = _ack_pre[0]
                        if a and a.strip():
                            _ack_pre[0] = None
                            return f"{a.rstrip()}\n\n{m}"
                        return m
    
                    intent = get_intent(text, conversation_snapshot=snap)
                    logger.info("classified_intent=%s", intent)
                    logger.info("plan_triggered=%s", intent == "brain_dump")
                    logger.info("llm_classifier_used=%s", settings.use_real_llm)
    
                    if intent == "status_update":
                        u = orchestrator.users.get(db, app_user_id)
                        if u is not None:
                            plan_data = orchestrator.get_today_plan(db, app_user_id)
                            titles = [t.title for t in plan_data["tasks"]] if plan_data else []
                            focus_title = titles[0] if titles else u.last_focus_task
                            reset_focus_after_completion(db, u, focus_title)
    
                    ctx = build_context(db, app_user_id, memory_service, orchestrator)
    
                    logger.info(
                        "incoming behavior=%s has_active_plan=%s is_new=%s text_preview=%r",
                        map_intent_to_behavior(intent, ctx),
                        ctx.has_active_plan,
                        user_row.is_new,
                        text[:120],
                    )
    
                    if user_row.is_new and intent == "general_chat" and is_weak_input(text):
                        sm = start_message()
                        await update.message.reply_text(sm)
                        _persist_conversation_turn(
                            db, app_user_id, cctx, tstrip, sm, intent, routed_key
                        )
                        return
    
                    if intent == "brain_dump":
                        logger.warning(
                            "PLAN_GENERATION_TRIGGERED intent=%s text_preview=%s",
                            intent,
                            text[:100],
                        )
                        result = orchestrator.generate_plan_from_text(
                            db, app_user_id, text, input_source="telegram", intent="brain_dump"
                        )
                        if result.get("needs_more_context"):
                            logger.info("brain_dump needs_more_context=true")
                            reply = apply_tone(no_tasks_response(), ctx.memory)
                            wn = _wrap_tg_inject_ack(reply)
                            await update.message.reply_text(wn)
                            _persist_conversation_turn(
                                db, app_user_id, cctx, tstrip, wn, intent, routed_key
                            )
                            return
                        orchestrator.users.mark_user_onboarded(db, app_user_id)
                        ctx_after = build_context(
                            db, app_user_id, memory_service, orchestrator
                        )
                        reply = build_response(
                            text,
                            intent,
                            ctx_after,
                            plan_result=result,
                            db=db,
                            app_user_id=app_user_id,
                            conversation_snapshot=snap,
                            routing_agent_key=routed_key,
                        )
                        wn = _wrap_tg_inject_ack(reply)
                        await update.message.reply_text(wn)
                        _persist_conversation_turn(
                            db, app_user_id, cctx, tstrip, wn, intent, routed_key
                        )
                        return
    
                    t_clean = strip_correction_prefix(text)
                    stripped = (text or "").strip()
                    correction_used = t_clean != stripped and len(t_clean.strip()) > 2
                    if (
                        looks_like_general_question(t_clean)
                        or correction_used
                    ):
                        gq = answer_general_question(
                            t_clean.strip() or stripped,
                            conversation_snapshot=snap,
                        )
                        wq = _wrap_tg_inject_ack(gq)
                        await update.message.reply_text(wq)
                        _persist_conversation_turn(
                            db,
                            app_user_id,
                            cctx,
                            tstrip,
                            wq,
                            "general_answer",
                            routed_key,
                        )
                        return
    
                    reply = build_response(
                        text,
                        intent,
                        ctx,
                        plan_result=None,
                        db=db,
                        app_user_id=app_user_id,
                        conversation_snapshot=snap,
                        routing_agent_key=routed_key,
                    )
                    wf = _wrap_tg_inject_ack(reply)
                    await update.message.reply_text(wf)
                    _persist_conversation_turn(
                        db, app_user_id, cctx, tstrip, wf, intent, routed_key
                    )
            finally:
                try:
                    from app.services.llm_usage_context import get_llm_usage_context
                    from app.services.llm_usage_recorder import (
                        build_usage_summary_for_request,
                        count_llm_events_for_request,
                        format_usage_subline,
                        record_response_turn,
                    )
    
                    uctx = get_llm_usage_context()
                    req_id = uctx.request_id
                    n_llm = count_llm_events_for_request(db, req_id)
                    us = build_usage_summary_for_request(db, req_id)
                    if uctx.user_id and (req_id or "").strip():
                        record_response_turn(
                            db,
                            user_id=uctx.user_id,
                            session_id=(uctx.session_id or "default").strip() or "default",
                            request_id=req_id or "unknown",
                            had_llm=n_llm > 0,
                        )
                    if (
                        is_owner_role(get_telegram_role(int(effu.id), db))
                        and update.message
                        and (req_id or "").strip()
                    ):
                        line = format_usage_subline(us)
                        if line and len(line) < 500:
                            await update.message.reply_text(f"— {line}")
                except Exception:  # noqa: BLE001
                    pass
                unbind_llm_telegram(_llm_tok)
                unbind_llm_usage(_u_tok)
    finally:
        db.close()


async def poll_due_checkins(app: Application) -> None:
    while True:
        db = SessionLocal()
        try:
            due = checkin_service.process_due(db)
            for row in due:
                link = telegram_service.repo.get_by_app_user(db, row.user_id)
                if link:
                    await app.bot.send_message(chat_id=link.chat_id, text=f"Check-in #{row.id}: {row.prompt_text}")
            handoff_updates = handoff_service.process_waiting_handoffs(db)
            for job in handoff_updates:
                link = telegram_service.repo.get_by_app_user(db, job.user_id)
                if link:
                    await app.bot.send_message(
                        chat_id=link.chat_id,
                        text=f"Job #{job.id} moved to {job.status}.\n\n{_format_job_line(job)}",
                    )
                job_service.mark_notified(db, job)
            notifiable_jobs = job_service.jobs_needing_notification(db)
            for job in notifiable_jobs:
                link = telegram_service.repo.get_by_app_user(db, job.user_id)
                if link:
                    await app.bot.send_message(
                        chat_id=link.chat_id,
                        text=f"Job #{job.id} update.\n\n{_format_job_line(job)}",
                    )
                job_service.mark_notified(db, job)
        except Exception as exc:
            logger.exception("Error processing due checkins: %s", exc)
        finally:
            db.close()
        await asyncio.sleep(settings.followup_poll_seconds)


async def permission_inline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    m = re.match(r"^perm:(grant|deny):(\d+)$", (q.data or ""))
    if not m:
        return
    action, pid_s = m.group(1), m.group(2)
    pid = int(pid_s)
    from app.services.access_permissions import deny_permission, grant_permission

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, q.from_user.id)
        if not link:
            if q.message:
                await q.message.reply_text("Link your account with /start first.")
            return
        uid = link.app_user_id
        tr = get_telegram_role(q.from_user.id, db)
        if (tr or "").strip() == "blocked":
            if q.message:
                await q.message.reply_text(BLOCKED_MSG)
            return
        if action == "grant":
            row = grant_permission(db, uid, pid, granted_by_user_id=uid)
            msg = (
                f"Approved permission #{pid}."
                if row
                else "Could not approve (not pending or not yours)."
            )
        else:
            row = deny_permission(db, uid, pid)
            msg = (
                f"Rejected permission #{pid}."
                if row
                else "Could not reject (not pending or not yours)."
            )
        if q.message:
            await q.message.reply_text(msg)
    finally:
        db.close()


async def job_inline_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    m = re.match(
        r"^job:(\d+):(approve|reject|diff|request_changes|changes)$", (q.data or "")
    )
    if not m:
        return
    jid, action = int(m.group(1)), m.group(2)
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, q.from_user.id)
        if not link:
            if q.message:
                await q.message.reply_text("Link your account with /start first.")
            return
        app_user_id = link.app_user_id
        ir = get_telegram_role(q.from_user.id, db)
        if not is_owner_role(ir):
            if q.message:
                _deny(
                    db,
                    telegram_id=q.from_user.id,
                    app_user=app_user_id,
                    uname=getattr(q.from_user, "username", None),
                    family="inline_job",
                    reason=action,
                    preview=None,
                )
                await q.message.reply_text(ACCESS_RESTRICTED)
            return
        if action == "approve":
            j = job_service.mark_autonomous_approved(db, app_user_id, job_id=jid)
            if j and q.message:
                await q.message.reply_text(
                    f"Approved job #{j.id} for commit. Next `dev_agent_executor` run will commit on the feature branch."
                )
            elif q.message:
                await q.message.reply_text("Could not approve (wrong job, status, or not yours).")
        elif action == "reject":
            j = job_service.mark_autonomous_rejected(db, app_user_id, job_id=jid)
            if j and q.message:
                await q.message.reply_text(
                    f"Job #{j.id} rejected; branch reset to baseline where possible. Status: {j.status}."
                )
            elif q.message:
                await q.message.reply_text("Could not reject (check job id and status).")
        elif action == "diff":
            job = job_service.get_job(db, app_user_id, jid)
            if not job or not q.message:
                return
            for piece in _split_telegram_text(
                _git_job_diff_summary(job)[:12_000], max_len=4000
            ):
                await q.message.reply_text(piece)
        elif action in ("request_changes", "changes") and q.message:
            j = job_service.set_changes_requested(db, app_user_id, jid)
            if not j:
                await q.message.reply_text(
                    "Could not start revision (job must be `waiting_approval` on a dev job you own)."
                )
                return
            if context:
                context.user_data = context.user_data or {}
                context.user_data["pending_dev_revision_job_id"] = jid
            await q.message.reply_text("What should I tell the agent to change? (Reply in one message.)")
    finally:
        db.close()


async def post_init(app: Application) -> None:
    app.create_task(poll_due_checkins(app))


def main() -> None:
    from app.core.config import get_settings as get_settings_fresh
    from app.services.startup_ensure import (
        ensure_nexa_secret_key,
        maybe_warn_missing_venv,
        print_env_validation_at_startup,
        print_missing_python_modules_hint,
    )

    global settings
    ensure_nexa_secret_key()
    get_settings_fresh.cache_clear()
    settings = get_settings_fresh()
    maybe_warn_missing_venv()
    if not settings.telegram_bot_token:
        print(
            "Nexa: set TELEGRAM_BOT_TOKEN in .env (or run python scripts/nexa_bootstrap.py). The bot will not start without it.\n",
            flush=True,
        )
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the bot")
    log_sanitized_nexa_config("bot")
    print_env_validation_at_startup("bot")
    print_missing_python_modules_hint()
    print_llm_debug_banner()
    maybe_log_llm_key_hint()
    ensure_schema()
    application = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()
    register_telegram_handlers(application)
    application.run_polling()


if __name__ == "__main__":
    main()
