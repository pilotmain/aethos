"""
Telegram — Phase 76 Blue-Green safety simulation.

- ``/simulate <jobId>`` (bot command): preview one pending ``agent_jobs`` row + Approve & Execute.
- ``/simulate …`` in chat (plain text): dry-run the same NL → host payload path as a normal
  message; offers Approve & Execute to run the **stripped** line without ``/simulate``.

Wire-up: :func:`app.services.channel_gateway.telegram_adapter.register_telegram_handlers`.
"""

from __future__ import annotations

import json
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.agent_job import AgentJob
from app.services import job_service, telegram_service
from app.services.user_capabilities import (
    ACCESS_RESTRICTED,
    BLOCKED_MSG,
    get_telegram_role,
    is_owner_role,
)

logger = logging.getLogger(__name__)


_SIM_CALLBACK_RE = re.compile(r"^sim:(\d+):(approve|cancel)$")


def rows_to_inline_markup(
    rows: tuple[tuple[tuple[str, str], ...], ...] | None,
) -> InlineKeyboardMarkup | None:
    """Build PTB markup from ``NextActionApplicationResult.telegram_inline_keyboard_rows``."""
    if not rows:
        return None
    out_rows = []
    for row in rows:
        out_rows.append(
            [
                InlineKeyboardButton(text=a[:64], callback_data=b[:64])
                for a, b in row
            ]
        )
    return InlineKeyboardMarkup(out_rows)


def _simulation_disabled_message() -> str | None:
    s = get_settings()
    if not bool(getattr(s, "nexa_simulation_enabled", True)):
        return (
            "Simulation is disabled (set NEXA_SIMULATION_ENABLED=true to "
            "enable Blue-Green preview)."
        )
    return None


async def _gate_owner(update: Update) -> str | None:
    """Returns the linked ``app_user_id`` on success; ``None`` on denial.

    Sends the appropriate denial message inline so callers don't repeat it.
    """
    if not update.effective_user or not update.message:
        return None
    disabled = _simulation_disabled_message()
    if disabled:
        await update.message.reply_text(disabled)
        return None
    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, update.effective_user.id)
        if not link:
            await update.message.reply_text("Link your account with /start first.")
            return None
        role = get_telegram_role(update.effective_user.id, db)
    finally:
        db.close()
    if role == "blocked":
        await update.message.reply_text(BLOCKED_MSG)
        return None
    if not is_owner_role(role):
        await update.message.reply_text(ACCESS_RESTRICTED)
        return None
    return link.app_user_id


def _format_structured_summary(plan: dict) -> str:
    """Compact text summary of the structured plan (Telegram-friendly)."""
    if not isinstance(plan, dict):
        return ""
    lines: list[str] = []
    kind = plan.get("kind") or "unknown"
    action = plan.get("action") or "(missing)"
    lines.append(f"kind: {kind} · action: {action}")
    fields = plan.get("fields") if isinstance(plan.get("fields"), dict) else {}
    diff = plan.get("diff") if isinstance(plan.get("diff"), dict) else None

    if action == "file_write" and diff:
        lines.append(
            f"path: {fields.get('relative_path') or '?'} "
            f"({'new file' if diff.get('is_new_file') else 'modified'})"
        )
        if diff.get("binary"):
            lines.append("binary file — diff skipped")
        else:
            lines.append(
                f"+{diff.get('added', 0)} / -{diff.get('removed', 0)} lines"
                + (" (truncated)" if diff.get("truncated") else "")
            )
    elif action == "git_commit":
        cm = fields.get("commit_message") or "?"
        paths = fields.get("changed_files") or []
        lines.append(f"commit_message: {cm}")
        if isinstance(paths, list) and paths:
            lines.append(f"changed_files ({len(paths)}): " + ", ".join(str(p) for p in paths[:8]))
            if len(paths) > 8:
                lines.append(f"  … +{len(paths) - 8} more")
    elif action == "git_push":
        ab = fields.get("ahead_behind") if isinstance(fields.get("ahead_behind"), dict) else {}
        ahead = ab.get("ahead")
        behind = ab.get("behind")
        branch = ab.get("current_branch") or "?"
        lines.append(
            f"branch: {branch} · ahead: {ahead if ahead is not None else '?'} · "
            f"behind: {behind if behind is not None else '?'}"
        )
        cmd = fields.get("command_preview")
        if cmd:
            lines.append(f"would run: {cmd}")
    elif action == "run_command":
        cmd = fields.get("command_preview")
        lines.append(f"would run: {cmd or '(unknown — run_name not in allowlist)'}")
    elif action == "plugin_skill":
        lines.append(f"skill: {fields.get('skill_name') or '?'}")
    elif kind == "deploy":
        lines.append(
            f"provider: {fields.get('provider')} · env: {fields.get('environment')}"
        )
        affected = fields.get("would_affect") or []
        if affected:
            lines.append("would affect: " + ", ".join(affected))
    elif kind == "chain":
        steps = plan.get("steps") or []
        lines.append(f"chain · {len(steps)} step(s)")
        for s in steps[:5]:
            lines.append(
                f"  {s.get('index')}. {s.get('action')} ({s.get('kind')})"
            )
        if len(steps) > 5:
            lines.append(f"  … and {len(steps) - 5} more step(s)")
    return "\n".join(lines)


def _build_simulate_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Approve & Execute", callback_data=f"sim:{job_id}:approve"
                ),
                InlineKeyboardButton(
                    "✖ Cancel", callback_data=f"sim:{job_id}:cancel"
                ),
            ]
        ]
    )


async def simulate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/simulate <jobId>`` or plain-text ``/simulate …`` (handled in chat routing)."""
    if not update.message:
        return
    app_user_id = await _gate_owner(update)
    if not app_user_id:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Usage:\n"
            "· `/simulate <jobId>` — preview a pending approval by job number.\n"
            "· Send `/simulate` followed by a natural-language host request in one message "
            "(same as asking Nexa to run a host tool, but dry-run only).\n\n"
            "Find job ids with `/agent_status` or Mission Control → Pending approvals."
        )
        return
    raw = args[0].strip().lstrip("#")
    try:
        job_id = int(raw)
    except ValueError:
        await update.message.reply_text(f"Invalid job id: {raw!r}")
        return

    from app.services.host_executor import build_simulation_plan, execute_payload

    db = SessionLocal()
    try:
        job = db.get(AgentJob, job_id)
        if job is None or str(job.user_id) != str(app_user_id):
            await update.message.reply_text(
                f"Job #{job_id} not found (or not yours)."
            )
            return
        if not bool(job.awaiting_approval):
            await update.message.reply_text(
                f"Job #{job_id} is not awaiting approval (status={job.status!r})."
            )
            return
        payload = job.payload_json or {}
        if not isinstance(payload, dict):
            await update.message.reply_text(
                f"Job #{job_id} has no structured payload to simulate."
            )
            return

        plan_text = ""
        plan_text_error: str | None = None
        try:
            plan_text = execute_payload(payload, simulate=True)
        except ValueError as exc:
            plan_text_error = f"Validation rejected the payload: {exc}"
        except Exception as exc:  # noqa: BLE001
            plan_text_error = f"Simulation failed: {exc!s}"
            logger.warning("simulate_cmd execute_payload failed", exc_info=True)
        try:
            plan = build_simulation_plan(payload)
        except Exception as exc:  # noqa: BLE001
            plan = {
                "action": "(error)",
                "kind": "unknown",
                "fields": {"error": f"plan_build_failed: {exc!s}"[:200]},
            }
            logger.warning("simulate_cmd build_simulation_plan failed", exc_info=True)

        title = job.title or "Pending action"
        risk = (job.risk_level or "—")
        header = (
            f"🔍 Simulation for job #{job_id}\n"
            f"title: {title}\n"
            f"risk: {risk}\n"
        )
        summary = _format_structured_summary(plan)
        if plan_text_error:
            body = f"⚠️ {plan_text_error}\n\n{summary}".strip()
        else:
            # Telegram caps messages around 4096 chars; trim defensively.
            ptxt = plan_text or "(no plan text emitted)"
            if len(ptxt) > 2500:
                ptxt = ptxt[:2497] + "…"
            body = f"{ptxt}\n\n{summary}".strip()

        # If file_write produced a unified diff, append the first ~30 lines.
        diff = plan.get("diff") if isinstance(plan, dict) else None
        if isinstance(diff, dict) and diff.get("unified"):
            unified = diff["unified"]
            preview_lines = unified.splitlines()[:30]
            preview = "\n".join(preview_lines)
            if len(unified.splitlines()) > 30:
                preview += "\n…"
            body += f"\n\nDiff preview:\n```\n{preview}\n```"

        await update.message.reply_text(
            f"{header}\n{body}",
            reply_markup=_build_simulate_keyboard(job_id),
            parse_mode=None,
        )
    finally:
        db.close()


async def sim_txt_exec_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Run the stored NL line after Simulation → Approve & Execute (Phase 76)."""
    q = update.callback_query
    if not q or not q.data or q.data != "simtxt:exec":
        return
    await q.answer()
    if not q.from_user or not q.message:
        return

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, q.from_user.id)
        if not link:
            if q.message:
                await q.message.reply_text("Link your account with /start first.")
            return
        if not is_owner_role(get_telegram_role(q.from_user.id, db)):
            if q.message:
                await q.message.reply_text(ACCESS_RESTRICTED)
            return

        from app.services.conversation_context_service import get_or_create_context
        from app.services.next_action_apply import apply_next_action_to_user_text

        cctx = get_or_create_context(db, link.app_user_id, web_session_id="default")
        raw = (cctx.simulate_execute_pending_json or "").strip()
        if not raw:
            if q.message:
                await q.message.reply_text(
                    "Nothing to execute — ask for a new `/simulate …` preview first."
                )
            return
        try:
            o = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            if q.message:
                await q.message.reply_text("Could not read pending simulation — try `/simulate` again.")
            return
        execute_text = (o.get("execute_text") or "").strip()
        if not execute_text:
            if q.message:
                await q.message.reply_text("Pending simulation payload was empty.")
            return

        cctx.simulate_execute_pending_json = None
        db.add(cctx)
        db.commit()

        _na = apply_next_action_to_user_text(
            db,
            cctx,
            execute_text,
            web_session_id=getattr(cctx, "session_id", None),
        )
        if q.message:
            reply_markup = rows_to_inline_markup(_na.telegram_inline_keyboard_rows)
            text_out = _na.early_assistant
            if text_out:
                await q.message.reply_text(
                    text_out[:3900],
                    reply_markup=reply_markup,
                )
            elif not _na.had_match:
                await q.message.reply_text(
                    "Could not apply that action — try sending the same line as a normal message "
                    "(without `/simulate`)."
                )
            else:
                await q.message.reply_text(
                    "Queued — check the confirmation or job status messages above."
                )
    finally:
        db.close()


async def sim_inline_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the ``sim:<jobId>:(approve|cancel)`` inline buttons."""
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    m = _SIM_CALLBACK_RE.match(q.data or "")
    if not m:
        return
    job_id = int(m.group(1))
    action = m.group(2)

    db = SessionLocal()
    try:
        link = telegram_service.get_link(db, q.from_user.id)
        if not link:
            if q.message:
                await q.message.reply_text("Link your account with /start first.")
            return
        if not is_owner_role(get_telegram_role(q.from_user.id, db)):
            if q.message:
                await q.message.reply_text(ACCESS_RESTRICTED)
            return

        if action == "cancel":
            if q.message:
                await q.message.reply_text(
                    f"Cancelled simulation for job #{job_id}. "
                    f"Job remains pending; use /deny {job_id} to reject it."
                )
            return

        # action == "approve" → run the same path as /approve <jobId>.
        try:
            from app.services.ops_approval import process_ops_job_decision

            ops_m = process_ops_job_decision(
                db, job_service, link.app_user_id, job_id, "approve"
            )
            if ops_m is not None:
                if q.message:
                    await q.message.reply_text(ops_m)
                return
            job = job_service.decide(db, link.app_user_id, job_id, "approve")
            if q.message:
                await q.message.reply_text(
                    f"✅ Approved job #{job.id} — status: {job.status}."
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("sim_inline_callback approve failed", exc_info=True)
            if q.message:
                await q.message.reply_text(
                    f"Could not approve job #{job_id}: {exc!s}"
                )
    finally:
        db.close()
