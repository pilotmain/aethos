"""
Synchronous @mention path for the Web API (and other non-telegram transports).

Reuses the same business logic as the Telegram mention handler: workflows, dev job
queuing, and :func:`app.services.agent_orchestrator.handle_agent_mention` fallback.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.telegram_repo import TelegramRepository
from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService
from app.services.agent_orchestrator import handle_agent_mention
from app.services.dev_orchestrator.dev_job_planner import (
    create_planned_dev_job,
    format_planned_dev_reply,
)
from app.services.dev_task_service import is_dev_task_message, parse_dev_task
from app.services.idea_workflow_routing import (
    try_dev_scope_workflow,
    try_marketing_workflow,
    try_strategy_workflow,
)
from app.services.memory_service import MemoryService
from app.services.mention_control import map_catalog_key_to_internal, parse_mention
from app.services.ops_handler import handle_nexa_ops_mention
from app.services.orchestrator_service import OrchestratorService
from app.services.project_parser import parse_dev_project_phrase
from app.services.project_registry import get_default_project, get_project_by_key, list_project_keys
from app.services.telegram_access_audit import log_access_denied
from app.services.telegram_dev_ux import format_job_row_short
from app.services.user_capabilities import (
    DEV_EXECUTION_RESTRICTED,
    get_telegram_role,
    is_owner_role,
    is_trusted_or_owner,
)

logger = logging.getLogger(__name__)

orchestrator = OrchestratorService()
memory_service = MemoryService()
job_service = AgentJobService()
telegram_repo = TelegramRepository()


def _deny_http(
    db: Session,
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


def _link_dev_run(db: Session, app_user_id: str, job: Any, ac: AgentJobCreate) -> None:
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


def _title_from_instruction(instruction: str, fallback: str = "Dev job") -> str:
    line = (instruction or "").split("\n", 1)[0].strip()
    return (line[:120] or fallback).strip() or fallback


def _blocked_or_approval_text(job: Any) -> str | None:
    st = job.status or ""
    if st == "blocked":
        return f"I blocked this dev job for safety:\n{job.error_message or 'Policy blocked'}"
    if st == "needs_risk_approval":
        return (
            f"Job #{job.id} may touch high-risk areas (see policy).\n\n"
            f"Use the Jobs page (or `approve high risk job #{job.id}` then `approve job #{job.id}` in Telegram).\n"
        )
    return None


@dataclass(frozen=True)
class ExplicitMentionResult:
    reply: str
    intent: str
    agent_key: str | None
    created_job_id: int | None = None


def run_explicit_mention(
    db: Session,
    app_user_id: str,
    tstrip: str,
    cctx: Any,
    snap: dict,
    *,
    telegram_user_id: int | None,
    telegram_chat_id: str | None = None,
    username: str | None = None,
) -> ExplicitMentionResult | None:
    """
    If the stripped message is an @mention, return a reply. Otherwise return None
    (caller should use the general :func:`handle_agent_request` path).
    """
    mr = parse_mention(tstrip)
    if not mr.is_explicit:
        return None
    from app.services.agent_runtime.boss_chat import try_spawn_lifecycle_chat_turn

    sl = try_spawn_lifecycle_chat_turn(db, app_user_id, tstrip)
    if sl is not None:
        return ExplicitMentionResult(sl, "boss_spawn_lifecycle", "boss")
    if mr.is_explicit and mr.error:
        from app.services.custom_agents import (
            display_agent_handle,
            format_unknown_with_custom,
            get_custom_agent,
            normalize_agent_key,
            run_custom_user_agent,
        )
        from app.services.mention_control import format_unknown_mention_message

        raws = (mr.raw_mention or "unknown").strip()
        k = normalize_agent_key(raws)
        uca = get_custom_agent(db, app_user_id, k)
        m_body0 = (mr.text or "").strip()
        if uca:
            dh_ua = display_agent_handle(uca.agent_key)
            if not uca.is_active:
                return ExplicitMentionResult(
                    f"{dh_ua} is **disabled**. Say **enable {dh_ua}** to turn it back on.",
                    "custom_agent_disabled",
                    uca.agent_key,
                )
            if not m_body0:
                return ExplicitMentionResult(
                    f"Add a message after {dh_ua} (custom agent).",
                    "mention_no_body",
                    uca.agent_key,
                )
            from app.services.agent_runtime.boss_chat import is_boss_agent_key, try_boss_runtime_chat_turn

            if is_boss_agent_key(uca.agent_key):
                boss_reply = try_boss_runtime_chat_turn(db, app_user_id, m_body0)
                if boss_reply is not None:
                    return ExplicitMentionResult(
                        boss_reply, "boss_runtime", uca.agent_key
                    )
            from app.services.custom_agent_routing import reply_for_custom_agent_path_clarification
            from app.services.local_file_intent import infer_local_file_request

            lf_web = infer_local_file_request(m_body0, default_relative_base=".")
            if lf_web.matched and lf_web.error_message:
                return ExplicitMentionResult(
                    lf_web.error_message,
                    "custom_agent_path_error",
                    uca.agent_key,
                )
            if lf_web.matched and lf_web.clarification_message:
                return ExplicitMentionResult(
                    reply_for_custom_agent_path_clarification(k, lf_web),
                    "custom_agent_path_clarify",
                    uca.agent_key,
                )
            rep0 = run_custom_user_agent(
                db, app_user_id, uca, m_body0, source="web_mention"
            )
            return ExplicitMentionResult(rep0, "custom_user_agent", uca.agent_key)
        return ExplicitMentionResult(
            format_unknown_with_custom(
                format_unknown_mention_message(raws),
                db,
                app_user_id,
            ),
            "mention_error",
            None,
        )
    if mr.is_explicit and (telegram_user_id is None or telegram_user_id < 1):
        return ExplicitMentionResult(
            "To use @mentions, dev jobs, and BYOK from the web, set `X-User-Id` to "
            "the same value as your Telegram account: `tg_<your_telegram_user_id>`.",
            "web_needs_tg",
            None,
        )
    tgu = int(telegram_user_id)  # checked above
    cctx_m = cctx
    snap_m = snap
    tg_role = get_telegram_role(tgu, db)

    m_key = map_catalog_key_to_internal(mr.agent_key or "")
    m_body = (mr.text or "").strip()
    if not m_body:
        return ExplicitMentionResult(
            "Add a message after your @mention — e.g. `@dev fix the tests` or `@ops status`.",
            "mention_no_body",
            None,
        )
    if m_key == "strategy":
        sb = try_strategy_workflow(m_body, db=db, cctx=cctx_m)
        if sb is not None:
            return ExplicitMentionResult(sb, "idea_workflow", m_key)
    if m_key == "marketing":
        mb = try_marketing_workflow(m_body, db=db, cctx=cctx_m)
        if mb is not None:
            return ExplicitMentionResult(mb, "idea_workflow", m_key)
    if m_key == "ops":
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
        return ExplicitMentionResult(ops_b, "ops_mention", "ops")
    if m_key == "developer":
        is_st = bool(re.match(r"^status\.?$", m_body.strip(), re.IGNORECASE))
        if (tg_role or "") == "guest":
            _deny_http(
                db,
                telegram_id=tgu,
                app_user=app_user_id,
                uname=username,
                family="at_dev",
                reason="guest",
                preview=(m_body or "")[:50],
            )
            return ExplicitMentionResult(DEV_EXECUTION_RESTRICTED, "at_dev", "developer")
        if is_st and is_trusted_or_owner(tg_role):
            from app.services.telegram_dev_ux import format_dev_agent_status_telegram

            smsg = format_dev_agent_status_telegram(db, app_user_id)
            return ExplicitMentionResult(smsg, "dev_status", "developer")
        if not is_owner_role(tg_role):
            _deny_http(
                db,
                telegram_id=tgu,
                app_user=app_user_id,
                uname=username,
                family="at_dev",
                reason="not_owner",
                preview=(m_body or "")[:50],
            )
            return ExplicitMentionResult(DEV_EXECUTION_RESTRICTED, "at_dev", "developer")
        scp = try_dev_scope_workflow(m_body, db=db, cctx=cctx_m)
        if scp is not None:
            return ExplicitMentionResult(scp, "idea_workflow", "developer")
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
            return ExplicitMentionResult(cmsg, "dev_create_project", "developer")
        if is_dev_task_message(m_body):
            title, description = parse_dev_task(m_body)
        else:
            title = _title_from_instruction(m_body, fallback="Dev @mention")
            description = m_body
        _keys = list_project_keys(db)
        _pkey, _in_inst = parse_dev_project_phrase(m_body, known_project_keys=_keys)
        if _pkey and _in_inst.strip() and _in_inst.strip() != m_body.strip():
            description = _in_inst.strip()
            title = _title_from_instruction(description, fallback="Dev @mention")
        _proj = get_project_by_key(db, _pkey) if _pkey else get_default_project(db)
        if _pkey and _proj is None:
            return ExplicitMentionResult(
                f"Unknown project `{_pkey}`. Use the Projects or CLI to see keys or add a project.",
                "dev_mention",
                "developer",
            )
        if _proj is None:
            return ExplicitMentionResult(
                "No project configured. Add a project in Nexa (or /project add in Telegram) first.",
                "dev_mention",
                "developer",
            )
        _repo = (getattr(_proj, "repo_path", None) or "").strip()
        if _pkey and _repo:
            _rp = Path(_repo).expanduser().resolve()
            if not _rp.is_dir() or not ((_rp / ".git").is_dir() or (_rp / ".git").is_file()):
                return ExplicitMentionResult(
                    f"Project `{_proj.key}` does not have a valid git `repo_path` on this host: `{_repo}`",
                    "dev_mention",
                    "developer",
                )
        _task_body = f"{title}\n{description}".strip()
        try:
            _result = create_planned_dev_job(
                db,
                user_id=app_user_id,
                telegram_chat_id=telegram_chat_id,
                task_text=_task_body,
                project_key=_proj.key,
                source="web_mention",
                title=title,
                instruction=description,
                extra_payload={"source": "developer_mention", "via": "mention_control"},
                job_service=job_service,
            )
        except ValueError as e:
            return ExplicitMentionResult(str(e)[:2000], "dev_error", "developer")
        djob = _result["job"]
        _dec = _result["plan"]["decision"]
        _ac = _result["agent_job_create"]
        _link_dev_run(db, app_user_id, djob, _ac)
        btxt = _blocked_or_approval_text(djob)
        if btxt:
            return ExplicitMentionResult(
                btxt, "dev_command", "developer", created_job_id=djob.id
            )
        msg = format_planned_dev_reply(
            plan_message=_result["message"],
            job_id=djob.id,
            decision=_dec,
            repo_line=_repo or None,
        )
        return ExplicitMentionResult(
            msg, "dev_command", "developer", created_job_id=djob.id
        )

    body = handle_agent_mention(
        db,
        app_user_id,
        m_key,
        m_body,
        memory_service=memory_service,
        orchestrator=orchestrator,
        conversation_snapshot=snap_m,
    )
    return ExplicitMentionResult(body, "general_chat", m_key)
