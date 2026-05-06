"""Web chat: reuse orchestration + context persistence, aligned with the Telegram path."""
from __future__ import annotations

import re
import uuid
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.web_ui import WebResponseSourceItem
from app.services.agent_job_service import AgentJobService
from app.services.agent_orchestrator import handle_agent_request
from app.services.agent_router import route_agent
from app.services.conversation_context_service import (
    build_context_snapshot,
    get_last_assistant_text,
    get_or_create_context,
    update_context_after_turn,
)
from app.services.custom_agents import (
    try_conversational_create_custom_agents,
    try_custom_agent_capability_guidance,
)
from app.services.decision_summary import (
    build_decision_summary,
    decision_for_web_explicit,
    infer_decision_for_web_main,
    merge_no_llm_path,
)
from app.services.document_generation import DocumentGenerationError, generate_document
from app.services.document_template_intent import parse_template_document_request
from app.services.intent_classifier import get_intent
from app.services.llm_request_context import llm_telegram_context
from app.services.llm_usage_context import bind_llm_usage_context
from app.services.llm_usage_recorder import (
    build_usage_summary_for_request,
    count_llm_events_for_request,
    record_response_turn,
)
from app.services.memory_aware_routing import apply_memory_aware_route_adjustment
from app.services.memory_service import MemoryService
from app.services.mention_incoming_for_http import run_explicit_mention
from app.services.orchestrator_service import OrchestratorService
from app.services.permission_reply_guard import patch_llm_reply_for_permission_execution_layer
from app.services.response_formatter import finalize_user_facing_text
from app.services.web_chat_metadata import WebMessageMetadata, compute_web_message_metadata
from app.services.web_request_context import bind_web_session_id
from app.services.web_turn_extras import take_web_turn_extra

orchestrator = OrchestratorService()
memory_service = MemoryService()
web_job_svc = AgentJobService()


def _text_from_gateway_payload(
    gw_out: dict[str, Any] | None, fallback_intent: str
) -> tuple[str | None, str]:
    """Map :meth:`NexaGateway.handle_message` dict to web reply text and intent."""
    if not isinstance(gw_out, dict):
        return None, fallback_intent
    t = (gw_out.get("text") or "").strip()
    if t:
        return t, str(gw_out.get("intent") or fallback_intent or "general_chat")
    if gw_out.get("mission") is not None:
        st = str(gw_out.get("status") or "completed")
        mdoc = gw_out.get("mission")
        title = ""
        if isinstance(mdoc, dict):
            title = str(mdoc.get("title") or "").strip()[:160]
        head = f"Mission {st.replace('_', ' ')}"
        if title:
            head = f"{head} — {title}"
        return (
            f"{head} — open Mission Control for full results and task output.",
            "run_mission",
        )
    return None, fallback_intent


def _response_kind_to_tool(rk: str | None) -> str:
    m = {
        "public_web": "public_web_reader",
        "web_search": "web_search",
        "browser_preview": "browser_preview",
        "marketing_web_analysis": "marketing_web_tools",
    }
    return m.get((rk or "").strip(), "local_state")


def _has_local_action_seed(base: WebChatResult) -> bool:
    for x in base.pending_system_events_seed or []:
        if str((x or {}).get("kind") or "").startswith("local_action"):
            return True
    return False


def _enrich_system_events(base: WebChatResult) -> list[dict[str, str]]:
    """Add small OS-style event lines; keeps chat rows informative without new UI chrome."""
    seed = [dict(x) for x in (base.pending_system_events_seed or []) if isinstance(x, dict)]
    out: list[dict[str, str]] = seed + [
        dict(x) for x in (base.system_events or []) if isinstance(x, dict)
    ]
    have = {str(x.get("kind") or "") for x in out}
    rk = (base.response_kind or "").strip()
    it = (base.intent or "").strip()

    if rk == "public_web" and "tool_web" not in have:
        out.append({"kind": "tool_web", "text": "Public web read completed."})
    elif rk == "web_search" and "tool_web" not in have:
        out.append({"kind": "tool_web", "text": "Web search completed."})
    elif rk == "browser_preview" and "tool_web" not in have:
        out.append({"kind": "tool_web", "text": "Browser preview read completed."})
    elif rk == "marketing_web_analysis" and "tool_line" not in have:
        tl = (base.web_tool_line or "Marketing web tools").strip()
        out.append(
            {
                "kind": "tool_line",
                "text": f"Used: {tl[:200]}",
            }
        )

    if (rk == "document_artifact" or it == "document_create") and "artifact_doc" not in have:
        out.append(
            {
                "kind": "artifact_doc",
                "text": "Document created — use Docs or Export to download.",
            }
        )

    if base.related_job_ids and "job" not in have and not _has_local_action_seed(base):
        jid = int(base.related_job_ids[0])
        st_hint = "queued"
        if (base.decision_summary or {}).get("approval_required"):
            st_hint = "waiting for approval"
        out.append(
            {
                "kind": "job",
                "text": f"Job #{jid} {st_hint} — use the card below or the Job tab.",
            }
        )

    return out


def _finalize_web_result(
    db: Session,
    app_user_id: str,
    req_id: str,
    base: WebChatResult,
    *,
    web_session_id: str = "default",
    user_text: str | None = None,
) -> WebChatResult:
    n = count_llm_events_for_request(db, req_id)
    us = build_usage_summary_for_request(db, req_id)
    had_llm = n > 0
    d_in = base.decision_summary
    d_out = merge_no_llm_path(
        d_in,
        had_llm=had_llm,
        tool_hint=_response_kind_to_tool(base.response_kind),
    )
    record_response_turn(
        db,
        user_id=app_user_id,
        session_id=(web_session_id or "default").strip()[:128] or "default",
        request_id=req_id,
        had_llm=had_llm,
    )
    se = _enrich_system_events(base)
    # All web user-visible replies go through this sink (see `response_formatter` module doc)
    up = None
    try:
        if base.reply and app_user_id:
            up = memory_service.get_learned_preferences(db, app_user_id)
    except Exception:  # noqa: BLE001
        up = None
    from app.services.response_sanitizer import sanitize_execution_and_assignment_reply

    reply_raw = base.reply or ""
    # Always sanitize; default user_text to "" if a caller omits it (defense in depth).
    ut = (user_text if user_text is not None else "") or ""
    reply_raw = sanitize_execution_and_assignment_reply(
        reply_raw,
        user_text=ut,
        related_job_ids=base.related_job_ids,
        permission_required=base.permission_required,
    )
    return WebChatResult(
        reply=finalize_user_facing_text(reply_raw, user_preferences=up),
        intent=base.intent,
        agent_key=base.agent_key,
        related_job_ids=list(base.related_job_ids),
        response_kind=base.response_kind,
        sources=list(base.sources),
        web_tool_line=base.web_tool_line,
        usage_summary=us,
        request_id=req_id,
        decision_summary=d_out,
        system_events=se,
        pending_system_events_seed=[],
        permission_required=base.permission_required,
    )


def _reply_metadata(
    user_text: str, agent_key: str | None, reply: str
) -> WebMessageMetadata:
    te = take_web_turn_extra()
    if (te.response_kind or "").strip():
        return WebMessageMetadata(
            (te.response_kind or "").strip(),
            list(te.sources) if te.sources is not None else [],
            tool_line=(te.tool_line or None),
        )
    return compute_web_message_metadata(user_text, agent_key, reply)


@dataclass
class WebChatResult:
    reply: str
    intent: str | None
    agent_key: str | None
    related_job_ids: list[int] = field(default_factory=list)
    response_kind: str | None = None
    sources: list[WebResponseSourceItem] = field(default_factory=list)
    web_tool_line: str | None = None
    # Per-turn efficiency (no prompts); optional for clients that ignore
    usage_summary: dict | None = None
    request_id: str | None = None
    # User-safe decision (no private reasoning)
    decision_summary: dict | None = None
    # OS-style chat rows (no LLM, tiny labels); Web UI may render as muted lines
    system_events: list[dict[str, str]] = field(default_factory=list)
    # Fed into _finalize_web_result merge before _enrich_system_events (host executor UX)
    pending_system_events_seed: list[dict[str, str]] = field(default_factory=list)
    permission_required: dict[str, Any] | None = None


def parse_telegram_id_from_app_user_id(app_user_id: str) -> int | None:
    m = re.match(r"^tg_(\d+)$", (app_user_id or "").strip())
    if not m:
        return None
    return int(m.group(1))


def process_web_message(
    db: Session,
    app_user_id: str,
    user_text: str,
    *,
    username: str | None = None,
    web_session_id: str = "default",
) -> WebChatResult:
    wid = (web_session_id or "default").strip()[:64] or "default"
    tid = parse_telegram_id_from_app_user_id(app_user_id)
    tstrip = (user_text or "").strip()
    with bind_web_session_id(wid):
        cctx = get_or_create_context(db, app_user_id, web_session_id=wid)
        snap = build_context_snapshot(cctx, db)

        if tid is not None:
            from app.repositories.telegram_repo import TelegramRepository

            link = TelegramRepository().get_by_app_user(db, app_user_id)
            tchat: str | None = str(link.chat_id) if link and link.chat_id is not None else None
        else:
            tchat = None

        req_id = str(uuid.uuid4())
        tctx = llm_telegram_context(db, tid) if tid is not None else nullcontext()
        with bind_llm_usage_context(
            source="web",
            user_id=app_user_id,
            telegram_user_id=str(tid) if tid is not None else None,
            session_id=wid,
            request_id=req_id,
            action_type="chat_response",
            agent_key="aethos",
            db=db,
        ), tctx:
            from app.services.host_executor_chat import drain_host_executor_web_notifications
            from app.services.next_action_apply import apply_next_action_to_user_text
            from app.services.web_host_job_followup import try_web_host_job_status_reply

            _host_job_note, _host_idle_events = drain_host_executor_web_notifications(
                db, app_user_id, wid
            )

            def _merge_idle_host_jobs(msg: str) -> str:
                n = (_host_job_note or "").strip()
                return f"{n}\n\n{msg}" if n else msg

            def _host_drain_seed() -> list[dict[str, str]]:
                return list(_host_idle_events or [])

            from app.services.agent_runtime.boss_chat import try_spawn_lifecycle_chat_turn
            from app.services.agent_team import try_agent_team_chat_turn
            from app.services.custom_agent_routing import try_deterministic_custom_agent_turn
            from app.services.multi_agent_routing import (
                is_multi_agent_capability_question,
                reply_multi_agent_capability_clarification,
            )

            _spawn_life = try_spawn_lifecycle_chat_turn(db, app_user_id, tstrip)
            if _spawn_life is not None:
                d_sp = build_decision_summary(
                    agent_key="boss",
                    action="boss_spawn_lifecycle",
                    tool="agent_runtime",
                    reason="Spawn group lookup/continue (deterministic, before other chat routing).",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(_spawn_life),
                        "boss_spawn_lifecycle",
                        "boss",
                        response_kind="boss_spawn_lifecycle",
                        decision_summary=d_sp,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(_spawn_life),
                    intent="boss_spawn_lifecycle",
                    agent_key="boss",
                    decision_summary=out.decision_summary,
                )
                return out

            if is_multi_agent_capability_question(tstrip):
                d_ma = build_decision_summary(
                    agent_key="aethos",
                    action="multi_agent_capability",
                    tool="local_state",
                    reason="Multi-agent capability question; route to agent-team guidance (no custom-agent create).",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(reply_multi_agent_capability_clarification()),
                        "multi_agent_capability",
                        "aethos",
                        response_kind="multi_agent_capability",
                        decision_summary=d_ma,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(reply_multi_agent_capability_clarification()),
                    intent="capability_question",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out

            _ca_turn = try_deterministic_custom_agent_turn(db, app_user_id, tstrip)
            if _ca_turn is not None:
                d_ca = build_decision_summary(
                    agent_key="aethos",
                    action="custom_agent_deterministic",
                    tool="local_state",
                    reason="Deterministic custom-agent lifecycle (runs before host/next-action).",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(_ca_turn),
                        "custom_agent",
                        "aethos",
                        response_kind="custom_agent",
                        decision_summary=d_ca,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(_ca_turn),
                    intent="custom_agent",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out

            _team_turn = try_agent_team_chat_turn(
                db, app_user_id, tstrip, web_session_id=wid
            )
            if _team_turn is not None:
                d_team = build_decision_summary(
                    agent_key="aethos",
                    action="agent_team",
                    tool="local_state",
                    reason="Deterministic agent organization / assignment turn.",
                    risk="low",
                )
                team_reply = _merge_idle_host_jobs(_team_turn.reply)
                team_jobs = list(_team_turn.related_job_ids)
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        team_reply,
                        "agent_team",
                        "aethos",
                        response_kind="agent_team",
                        decision_summary=d_team,
                        pending_system_events_seed=_host_drain_seed(),
                        related_job_ids=team_jobs,
                        permission_required=_team_turn.permission_required,
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=team_reply,
                    intent="agent_team",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out

            status_early = try_web_host_job_status_reply(
                db, app_user_id, tstrip, web_session_id=wid
            )
            if status_early is not None:
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(status_early.reply),
                        status_early.intent,
                        status_early.agent_key,
                        related_job_ids=list(status_early.related_job_ids),
                        response_kind=status_early.response_kind,
                        decision_summary=status_early.decision_summary,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=out.reply,
                    intent=out.intent or "host_job_status",
                    agent_key=out.agent_key or "aethos",
                    decision_summary=out.decision_summary,
                )
                return out

            na0 = apply_next_action_to_user_text(
                db, cctx, tstrip, web_session_id=wid
            )
            _ack_box: list[str | None] = [na0.inject_ack]

            def _prepend_inject_ack(msg: str) -> str:
                a = _ack_box[0]
                if a and (a or "").strip():
                    _ack_box[0] = None
                    return f"{a.rstrip()}\n\n{msg}"
                return msg

            if na0.early_assistant is not None:
                host_seed = _host_drain_seed()
                host_seed += [
                    {"kind": k, "text": t} for k, t in na0.pending_system_events
                ]
                d0 = build_decision_summary(
                    agent_key="aethos",
                    action="co_pilot_next",
                    tool="co_pilot",
                    reason="AethOS applied a co-pilot next-step confirmation (no new UI).",
                    risk="low",
                )
                rk_na: str | None = None
                if na0.permission_required:
                    rk_na = "permission_required"
                    pr = na0.permission_required
                    d0 = {
                        **d0,
                        "reason": str(pr.get("message") or "Scoped access approval required before AethOS can run this host action."),
                        "approval_required": True,
                        "tool": "host_executor",
                        "risk": str(pr.get("risk_level") or "medium"),
                        "intent": "permission_required",
                    }
                elif na0.related_job_ids:
                    d0 = {
                        **d0,
                        "reason": "Host executor local action queued (approval-gated job).",
                        "approval_required": True,
                        "tool": "host_executor",
                        "risk": "low",
                    }
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(na0.early_assistant),
                        "next_action",
                        "aethos",
                        related_job_ids=list(na0.related_job_ids),
                        response_kind=rk_na,
                        decision_summary=d0,
                        pending_system_events_seed=host_seed,
                        permission_required=na0.permission_required,
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(na0.early_assistant),
                    intent="next_action",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out
            tstrip = (na0.user_text_for_pipeline or tstrip or "").strip()

            from app.services.sub_agent_natural_creation import (
                prefers_registry_sub_agent,
                try_spawn_natural_sub_agents,
            )

            if prefers_registry_sub_agent(tstrip):
                web_scope = f"web:{app_user_id}:{wid}"
                ns_web = try_spawn_natural_sub_agents(db, app_user_id, tstrip, parent_chat_id=web_scope)
                if ns_web:
                    d0 = build_decision_summary(
                        agent_key="aethos",
                        action="sub_agent_create",
                        tool="local_state",
                        reason="Orchestration sub-agents created from natural language.",
                        risk="low",
                    )
                    out = _finalize_web_result(
                        db,
                        app_user_id,
                        req_id,
                        WebChatResult(
                            _merge_idle_host_jobs(ns_web),
                            "create_sub_agent",
                            "aethos",
                            response_kind="create_sub_agent",
                            decision_summary=d0,
                            pending_system_events_seed=_host_drain_seed(),
                        ),
                        web_session_id=wid,
                        user_text=user_text,
                    )
                    update_context_after_turn(
                        db,
                        cctx,
                        user_text=user_text,
                        assistant_text=_merge_idle_host_jobs(ns_web),
                        intent="create_sub_agent",
                        agent_key="aethos",
                        decision_summary=out.decision_summary,
                    )
                    return out

            cg_msg = try_custom_agent_capability_guidance(db, app_user_id, tstrip)
            if cg_msg is not None:
                d0 = build_decision_summary(
                    agent_key="aethos",
                    action="custom_agent_guidance",
                    tool="local_state",
                    reason="Deterministic custom-agent capability guidance.",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(cg_msg),
                        "custom_agent_guidance",
                        "aethos",
                        response_kind="custom_agent_guidance",
                        decision_summary=d0,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(cg_msg),
                    intent="custom_agent_guidance",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out
            c_msg = try_conversational_create_custom_agents(db, app_user_id, tstrip)
            if c_msg is not None:
                d0 = build_decision_summary(
                    agent_key="aethos",
                    action="custom_agent_create",
                    tool="local_state",
                    reason="AethOS added custom agents from your message (LLM-only, no special tools by default).",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(c_msg),
                        "custom_agent_create",
                        "aethos",
                        response_kind="custom_agent_create",
                        decision_summary=d0,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(c_msg),
                    intent="custom_agent_create",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out
            t_req, t_body, t_clarify = parse_template_document_request(
                tstrip, get_last_assistant_text(db, app_user_id, web_session_id=wid)
            )
            if t_clarify is not None:
                d0 = build_decision_summary(
                    agent_key="aethos",
                    action="document",
                    tool="clarify",
                    reason="AethOS needs more content before generating a templated document.",
                    risk="low",
                )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        _merge_idle_host_jobs(t_clarify),
                        "document_template_clarify",
                        "aethos",
                        decision_summary=d0,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=_merge_idle_host_jobs(t_clarify),
                    intent="document_template_clarify",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out
            if t_req is not None and t_body is not None:
                try:
                    art = generate_document(
                        db,
                        title=t_req.label,
                        body_markdown=t_body,
                        format=t_req.format,
                        user_id=app_user_id,
                        source_type=t_req.source_type,
                        source_ref="template_intent",
                    )
                except DocumentGenerationError as e:
                    err = str(e) or getattr(e, "code", "failed")
                    d0 = build_decision_summary(
                        agent_key="aethos",
                        action="document",
                        tool="document_export",
                        reason="Document generation failed for this request.",
                        risk="low",
                    )
                    out = _finalize_web_result(
                        db,
                        app_user_id,
                        req_id,
                        WebChatResult(
                            _merge_idle_host_jobs(err),
                            "document_error",
                            "aethos",
                            decision_summary=d0,
                            pending_system_events_seed=_host_drain_seed(),
                        ),
                        web_session_id=wid,
                        user_text=user_text,
                    )
                    update_context_after_turn(
                        db,
                        cctx,
                        user_text=user_text,
                        assistant_text=_merge_idle_host_jobs(err),
                        intent="document_error",
                        agent_key="aethos",
                        decision_summary=out.decision_summary,
                    )
                    return out
                d_ok = build_decision_summary(
                    agent_key="aethos",
                    action="document_create",
                    tool="document_export",
                    reason="AethOS created a document from a template-style request (Docs tab to download).",
                    risk="low",
                )
                success_msg = (
                    f"I created your {t_req.label} ({art.format.upper()}). Open the **Docs** tab to download, "
                    "or use **Export** under a message for a quick one-off file."
                )
                success_msg = _merge_idle_host_jobs(success_msg)
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        success_msg,
                        "document_create",
                        "aethos",
                        response_kind="document_artifact",
                        decision_summary=d_ok,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=success_msg,
                    intent="document_create",
                    agent_key="aethos",
                    decision_summary=out.decision_summary,
                )
                return out
            em = run_explicit_mention(
                db,
                app_user_id,
                tstrip,
                cctx,
                snap,
                telegram_user_id=tid,
                telegram_chat_id=tchat,
                username=username,
            )
            if em is not None:
                rj: list[int] = []
                if em.created_job_id is not None:
                    rj = [em.created_job_id]
                job_obj = None
                if em.created_job_id is not None:
                    try:
                        job_obj = web_job_svc.get_job(
                            db, app_user_id, int(em.created_job_id)
                        )
                    except Exception:  # noqa: BLE001
                        job_obj = None
                reply_em = _prepend_inject_ack(_merge_idle_host_jobs(em.reply))
                wm = _reply_metadata(
                    (user_text or "").strip(), em.agent_key, reply_em
                )
                if (wm.response_kind or "").strip() == "marketing_web_analysis":
                    pre = infer_decision_for_web_main(
                        user_text=(user_text or "").strip(),
                        routed_agent_key=em.agent_key or "marketing",
                        intent=em.intent,
                        response_kind=wm.response_kind,
                    )
                else:
                    pre = decision_for_web_explicit(
                        em.intent, em.agent_key, user_text, job_obj
                    )
                out = _finalize_web_result(
                    db,
                    app_user_id,
                    req_id,
                    WebChatResult(
                        reply_em,
                        em.intent,
                        em.agent_key,
                        related_job_ids=rj,
                        response_kind=wm.response_kind,
                        sources=list(wm.sources),
                        web_tool_line=wm.tool_line,
                        decision_summary=pre,
                        pending_system_events_seed=_host_drain_seed(),
                    ),
                    web_session_id=wid,
                    user_text=user_text,
                )
                update_context_after_turn(
                    db,
                    cctx,
                    user_text=user_text,
                    assistant_text=reply_em,
                    intent=em.intent,
                    agent_key=em.agent_key,
                    decision_summary=out.decision_summary,
                )
                return out

            intent = get_intent(tstrip, conversation_snapshot=snap)
            rt = route_agent(tstrip, context_snapshot=snap)
            rt = apply_memory_aware_route_adjustment(rt, tstrip, snap, db)
            rkey = str(rt.get("agent_key") or "aethos")

            from app.services.gateway.context import GatewayContext
            from app.services.gateway.runtime import NexaGateway
            from app.services.user_capabilities import (
                get_telegram_role_for_app_user,
                is_owner_role,
            )

            perms: dict[str, Any] = {}
            extras: dict[str, Any] = {
                "web_session_id": wid,
                "routing_agent_key": rkey,
                "via_gateway": True,
            }
            if username:
                extras["username"] = username
            if tid is not None:
                extras["telegram_user_id"] = str(tid)
                extras["telegram_chat_id"] = (tchat or "") or ""
                extras["telegram_username"] = username
                role = get_telegram_role_for_app_user(db, app_user_id)
                perms["telegram_role"] = role
                if is_owner_role(role):
                    perms["owner"] = True

            gctx = GatewayContext(
                user_id=app_user_id,
                channel="web",
                permissions=perms,
                extras=extras,
            )
            gw_out = NexaGateway().handle_message(gctx, tstrip, db=db)
            reply, intent_use = _text_from_gateway_payload(gw_out, intent)
            if reply is None:
                reply = handle_agent_request(
                    db,
                    app_user_id,
                    tstrip,
                    memory_service=memory_service,
                    orchestrator=orchestrator,
                    context_snapshot=snap,
                )
                intent_use = intent
            reply = _prepend_inject_ack(_merge_idle_host_jobs(reply))
            (
                reply,
                perm_guard,
                rk_guard,
                intent_guard,
            ) = patch_llm_reply_for_permission_execution_layer(
                db,
                cctx,
                web_session_id=wid,
                user_text=tstrip,
                reply=reply,
            )
            wm = _reply_metadata((user_text or "").strip(), rkey, reply)
            intent_use = intent_guard if intent_guard else intent_use
            rk_use = rk_guard if rk_guard else wm.response_kind
            pre = infer_decision_for_web_main(
                user_text=tstrip,
                routed_agent_key=rkey,
                intent=intent_use,
                response_kind=rk_use,
            )
            if perm_guard:
                pre = {
                    **pre,
                    "reason": str(
                        perm_guard.get("message")
                        or "Scoped access approval required before AethOS can run this host action."
                    ),
                    "approval_required": True,
                    "tool": "host_executor",
                    "risk": str(perm_guard.get("risk_level") or "medium"),
                    "intent": "permission_required",
                }
            elif intent_guard == "next_action":
                pre = {
                    **pre,
                    "reason": "Host executor confirmation or path check (deterministic flow).",
                    "approval_required": False,
                    "tool": "host_executor",
                    "risk": pre.get("risk") or "low",
                }
            out = _finalize_web_result(
                db,
                app_user_id,
                req_id,
                WebChatResult(
                    reply,
                    intent_use,
                    rkey,
                    related_job_ids=[],
                    response_kind=rk_use,
                    sources=list(wm.sources),
                    web_tool_line=wm.tool_line,
                    decision_summary=pre,
                    pending_system_events_seed=_host_drain_seed(),
                    permission_required=perm_guard,
                ),
                web_session_id=wid,
                user_text=user_text,
            )
            update_context_after_turn(
                db,
                cctx,
                user_text=user_text,
                assistant_text=reply,
                intent=intent_use,
                agent_key=rkey,
                decision_summary=out.decision_summary,
            )
        return out
