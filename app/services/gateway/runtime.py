"""Nexa Gateway runtime — single entry for channels → missions → agents → MC."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.logging.logger import get_logger
from app.services.metrics.runtime import record_mission_completed, record_mission_timeout

_log = get_logger("gateway")


def gateway_finalize_chat_reply(text: str, *, source: str = "gateway") -> str:
    """Normalize user-visible copy: log legacy markers, then scrub when needed (Phase 51)."""
    from app.services.identity.scrub import gateway_identity_needs_scrub, scrub_legacy_identity_text

    if gateway_identity_needs_scrub(text):
        _log.warning(
            "gateway.identity_scrub source=%s preview=%s",
            source,
            (text or "")[:240],
        )
        return scrub_legacy_identity_text(text)
    return text


def _merge_phase50_assist(reply: str, raw: str, intent: str) -> str:
    """Append deterministic dev appendix with context hints for action-first routing (Phase 50)."""
    from app.services.execution_trigger import should_merge_phase50_assist
    from app.services.instant_dev_assist import format_assist_appendix

    if not should_merge_phase50_assist(intent):
        return reply
    app = format_assist_appendix(user_text=raw, intent=intent)
    if not app:
        return reply
    return (reply.rstrip() + "\n\n" + app).strip()


def _finalize_gateway_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize user-visible strings on shallow gateway result dicts."""
    if not isinstance(payload, dict):
        return payload
    t = payload.get("text")
    if isinstance(t, str):
        return {**payload, "text": gateway_finalize_chat_reply(t, source="gateway_payload")}
    return payload

# Legacy constant — Phase 35 routes generic chat through :meth:`handle_full_chat` instead.
GATEWAY_CHAT_FALLBACK_TEXT = "No mission detected"


class NexaGateway:
    """
    Central gateway: owns admission for web, Telegram, and future channels.

    Channels must call :meth:`handle_message` with a :class:`GatewayContext` rather than
    invoking agents/tools directly.
    """

    def compose_llm_reply(self, *args: Any, **kwargs: Any) -> str:
        """Phase 36 / 51 — delegate to :func:`compose_nexa_response` (legacy ``build_response``)."""
        from app.services.response_engine import compose_nexa_response

        return compose_nexa_response(*args, **kwargs)

    def _maybe_auto_dev_investigation(
        self,
        gctx: GatewayContext,
        text: str,
        db: Session,
    ) -> dict[str, Any] | None:
        """Phase 52/53 — auto-run a dev mission when policy + single workspace allow."""
        from app.services.conversation_context_service import build_context_snapshot, get_or_create_context
        from app.services.dev_runtime.run_dev_gateway import format_dev_run_summary
        from app.services.dev_runtime.service import run_dev_mission
        from app.services.dev_runtime.workspace import list_workspaces
        from app.services.execution_policy import (
            assess_interaction_risk,
            should_prompt_for_dev_workspace_help,
        )
        from app.services.execution_trigger import compute_execution_confidence, should_auto_execute_dev
        from app.services.intent_classifier import get_intent

        uid = (gctx.user_id or "").strip()
        raw = (text or "").strip()
        if not uid or not raw:
            return None
        rows = list_workspaces(db, uid)
        cctx = get_or_create_context(db, uid)
        snap = build_context_snapshot(cctx, db)
        mem_sum = None
        if isinstance(gctx.memory, dict):
            mem_sum = str(gctx.memory.get("summary") or "").strip() or None
        intent = get_intent(raw, conversation_snapshot=snap, memory_summary=mem_sum)
        risk = assess_interaction_risk(raw)

        if should_prompt_for_dev_workspace_help(intent, risk, raw):
            if len(rows) == 0:
                return {
                    "mode": "chat",
                    "text": (
                        "I can investigate this once a workspace is connected in Mission Control "
                        "(register a repo path under Dev / workspace)."
                    ),
                    "intent": "dev_workspace_hint",
                }
            if len(rows) > 1:
                lines = "\n".join(
                    f"- {(getattr(r, 'name', None) or r.id or '?')}" for r in rows[:16]
                )
                return {
                    "mode": "chat",
                    "text": (
                        "Which workspace should I use?\n"
                        f"{lines}\n\n"
                        "Reply with the workspace name, or narrow to one workspace in Mission Control."
                    ),
                    "intent": "dev_workspace_pick",
                }

        if len(rows) != 1:
            return None

        conf = compute_execution_confidence(
            intent,
            raw,
            memory_summary=mem_sum,
            workspace_count=len(rows),
        )
        if conf == "low":
            return None

        settings = get_settings()
        if conf == "medium" and bool(getattr(settings, "nexa_execution_confirm_medium", True)):
            return {
                "mode": "chat",
                "text": (
                    "I'm not fully confident this should auto-run against your workspace yet. "
                    'Say "yes, investigate" to proceed, or paste the exact error output or traceback.'
                ),
                "intent": "execution_confirm",
            }

        if not should_auto_execute_dev(raw, intent, workspace_count=len(rows)):
            return None
        goal = raw[:8000]
        mem_notes = mem_sum[:4000] if mem_sum else None
        on_prog = gctx.extras.get("on_dev_progress")
        res = run_dev_mission(
            db,
            uid,
            rows[0].id,
            goal,
            memory_notes=mem_notes,
            on_progress=on_prog if callable(on_prog) else None,
        )
        body = format_dev_run_summary(res)
        intro = "I'll investigate this against your workspace now.\n\n"
        return {
            "mode": "chat",
            "text": intro + body,
            "dev_run": res,
            "intent": "dev_mission",
        }

    def _try_structured_route(self, gctx: GatewayContext, text: str, db: Session) -> dict[str, Any] | None:
        """Dev runs, missions, and dev hints only — ``None`` means generic chat."""
        from app.services.dev_runtime.gateway_hint import maybe_dev_gateway_hint
        from app.services.dev_runtime.run_dev_gateway import handle_run_dev_gateway, try_scheduled_dev_mission
        from app.services.memory.context_injection import build_memory_context_for_turn
        from app.services.missions.parser import parse_mission

        _uid = (gctx.user_id or "").strip()
        raw_t = (text or "").strip()
        if _uid and raw_t:
            turn = build_memory_context_for_turn(_uid, raw_t, purpose="gateway_structured")
            if turn.get("used"):
                if gctx.memory is None:
                    gctx.memory = {}
                gctx.memory.update(turn)

        uid = gctx.user_id
        sched_out = try_scheduled_dev_mission(gctx, text, db)
        if sched_out is not None:
            return sched_out
        dev_out = handle_run_dev_gateway(text, uid, db)
        if dev_out is not None:
            return dev_out

        from app.services.hosted_service_mission_gate import hosted_service_mission_blocked

        if hosted_service_mission_blocked(raw_t):
            return None

        mission = parse_mission(text)
        if mission:
            return self._run_mission(mission, uid, db, source_text=text)

        auto_dev = self._maybe_auto_dev_investigation(gctx, text, db)
        if auto_dev is not None:
            return auto_dev

        hint = maybe_dev_gateway_hint(text, uid, db)
        if hint is not None:
            return hint
        return None

    def try_structured_turn(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session,
    ) -> dict[str, Any] | None:
        """Telegram runs this before feature-specific handlers so missions/dev stay first."""
        return self._try_structured_route(gctx, text, db)

    def try_approval_only(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session,
    ) -> dict[str, Any] | None:
        """NL job approvals — Telegram calls this after structured turn; web uses :meth:`handle_message`."""
        return self._try_approval_route(gctx, text, db)

    def _try_approval_route(self, gctx: GatewayContext, text: str, db: Session) -> dict[str, Any] | None:
        from app.services.gateway.approval_flow import try_gateway_approval_route

        return try_gateway_approval_route(gctx, text, db)

    def continue_after_structured(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session,
    ) -> dict[str, Any]:
        """Telegram: structured routing already ran; run approval NL + full chat."""
        approval = self._try_approval_route(gctx, text, db)
        if approval is not None:
            return approval
        return self.handle_full_chat(gctx, text, db=db)

    def handle_full_chat(self, gctx: GatewayContext, text: str, *, db: Session) -> dict[str, Any]:
        """
        LLM / behavior chat path (formerly Telegram-only ``behavior_engine`` fall-through).

        Loads conversation snapshot, classifies intent, and delegates to
        :meth:`compose_llm_reply` (legacy ``build_response``) for the composed reply.
        """
        from app.services.agent_router import route_agent
        from app.services.legacy_behavior_utils import (
            apply_tone,
            build_context,
            no_tasks_response,
        )
        from app.services.conversation_context_service import (
            build_context_snapshot,
            get_or_create_context,
        )
        from app.services.general_answer_service import answer_general_question
        from app.services.general_response import looks_like_general_question, strip_correction_prefix
        from app.services.intent_classifier import get_intent
        from app.services.loop_tracking_service import reset_focus_after_completion
        from app.services.memory_aware_routing import apply_memory_aware_route_adjustment
        from app.services.memory.memory_index import MemoryIndex
        from app.services.memory_service import MemoryService
        from app.services.orchestrator_service import OrchestratorService
        from app.services.telegram_onboarding import (
            is_weak_input,
            onboarding_deterministic_reply,
            weak_input_response,
        )

        uid = gctx.user_id
        channel = gctx.channel
        raw = (text or "").strip()
        from app.services.external_execution_credentials import maybe_handle_external_credential_chat_turn
        from app.services.memory.context_injection import build_memory_context_for_turn

        cred_full = maybe_handle_external_credential_chat_turn(db, user_id=(uid or "").strip(), user_text=raw)
        if cred_full is not None:
            return cred_full

        if not gctx.extras.get("gateway_structured_ran"):
            auto_early = self._maybe_auto_dev_investigation(gctx, text, db)
            if auto_early is not None:
                return auto_early

        if not (isinstance(gctx.memory, dict) and gctx.memory.get("used")):
            turn_mem = build_memory_context_for_turn(uid, raw, purpose="chat")
            if turn_mem.get("used"):
                if gctx.memory is None:
                    gctx.memory = {}
                gctx.memory.update(turn_mem)

        orchestrator = OrchestratorService()
        memory_service = MemoryService()
        settings = get_settings()

        def _attach_memory_brain(beh_ctx_inner: Any) -> None:
            if isinstance(beh_ctx_inner.memory, dict):
                turn_mc = None
                if isinstance(gctx.memory, dict):
                    turn_mc = gctx.memory.get("memory_context")
                if isinstance(turn_mc, str) and turn_mc.strip():
                    beh_ctx_inner.memory["memory_context"] = turn_mc.strip()[:5000]
                else:
                    beh_ctx_inner.memory["memory_context"] = MemoryIndex().recent_for_prompt(
                        uid, max_chars=3500
                    )
                if isinstance(gctx.memory, dict):
                    for _k, _v in gctx.memory.items():
                        if _k in ("via_gateway", "memory_context"):
                            continue
                        beh_ctx_inner.memory.setdefault(_k, _v)

        cctx = get_or_create_context(db, uid)
        snap = build_context_snapshot(cctx, db)

        from app.services.external_execution_session import (
            maybe_start_external_probe_from_turn,
            try_resume_external_execution_turn,
            try_retry_external_execution_turn,
        )

        _retry = try_retry_external_execution_turn(db, uid, raw, cctx)
        if _retry is not None:
            rt_text = str(_retry.get("text") or "").strip()
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(rt_text, source="external_execution_retry"),
                "intent": str(_retry.get("intent") or "external_execution_continue"),
            }

        _resume = try_resume_external_execution_turn(db, uid, raw, cctx)
        if _resume is not None:
            rt_text = str(_resume.get("text") or "").strip()
            if not rt_text:
                rt_text = (
                    "Got it — I’ve recorded your Railway/deploy preferences.\n\n"
                    "Send **retry external execution** to run read-only checks on this worker with fresh progress "
                    "and output—or describe the next error in one line."
                )
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(rt_text, source="external_execution_resume"),
                "intent": str(_resume.get("intent") or "external_execution_continue"),
            }

        _probe = maybe_start_external_probe_from_turn(
            db, uid, raw, cctx, conversation_snapshot=snap
        )
        if _probe is not None:
            pt = str(_probe.get("text") or "").strip()
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(pt, source="external_execution_probe"),
                "intent": str(_probe.get("intent") or "external_execution_continue"),
            }

        rt = route_agent(raw, context_snapshot=snap)
        rt = apply_memory_aware_route_adjustment(rt, raw, snap, db)
        routing_agent_key = str(gctx.extras.get("routing_agent_key") or rt.get("agent_key") or "nexa")

        _mem_for_intent = None
        if isinstance(gctx.memory, dict):
            _mem_for_intent = str(gctx.memory.get("summary") or "").strip() or None
        intent = get_intent(raw, conversation_snapshot=snap, memory_summary=_mem_for_intent)
        _log.info(
            "gateway.full_chat intent=%s llm_classifier_used=%s channel=%s",
            intent,
            settings.use_real_llm,
            channel,
        )

        user_row = orchestrator.users.get_or_create(db, uid)

        if intent == "status_update":
            u = orchestrator.users.get(db, uid)
            if u is not None:
                plan_data = orchestrator.get_today_plan(db, uid)
                titles = [t.title for t in plan_data["tasks"]] if plan_data else []
                focus_title = titles[0] if titles else u.last_focus_task
                reset_focus_after_completion(db, u, focus_title)

        beh_ctx = build_context(db, uid, memory_service, orchestrator)
        _attach_memory_brain(beh_ctx)

        if user_row.is_new and intent == "general_chat" and is_weak_input(raw):
            sm = onboarding_deterministic_reply(raw) or weak_input_response()
            return {"mode": "chat", "text": gateway_finalize_chat_reply(sm, source="onboarding_weak_reply"), "intent": intent}

        if intent == "brain_dump":
            _log.warning(
                "gateway brain_dump plan_generation text_preview=%s",
                raw[:100],
            )
            result = orchestrator.generate_plan_from_text(
                db,
                uid,
                raw,
                input_source=channel,
                intent="brain_dump",
            )
            if result.get("needs_more_context"):
                return {
                    "mode": "chat",
                    "text": gateway_finalize_chat_reply(
                        apply_tone(no_tasks_response(), beh_ctx.memory),
                        source="no_tasks_response",
                    ),
                    "intent": intent,
                }
            orchestrator.users.mark_user_onboarded(db, uid)
            beh_ctx_after = build_context(db, uid, memory_service, orchestrator)
            _attach_memory_brain(beh_ctx_after)
            reply = self.compose_llm_reply(
                raw,
                intent,
                beh_ctx_after,
                plan_result=result,
                db=db,
                app_user_id=uid,
                conversation_snapshot=snap,
                routing_agent_key=routing_agent_key,
            )
            return {"mode": "chat", "text": gateway_finalize_chat_reply(reply, source="brain_dump_reply"), "intent": intent}

        t_clean = strip_correction_prefix(raw)
        stripped = raw
        correction_used = t_clean != stripped and len((t_clean or "").strip()) > 2
        if looks_like_general_question(t_clean) or correction_used:
            mem_sum = ""
            if isinstance(gctx.memory, dict):
                mem_sum = str(gctx.memory.get("summary") or "").strip()
            gq = answer_general_question(
                (t_clean or "").strip() or stripped,
                conversation_snapshot=snap,
                turn_memory_summary=mem_sum or None,
            )
            return {"mode": "chat", "text": gateway_finalize_chat_reply(gq, source="general_answer"), "intent": "general_answer"}

        from app.services.external_execution_session import scrub_generic_login_refusal_when_local_auth_claimed

        reply = self.compose_llm_reply(
            raw,
            intent,
            beh_ctx,
            plan_result=None,
            db=db,
            app_user_id=uid,
            conversation_snapshot=snap,
            routing_agent_key=routing_agent_key,
        )
        reply = scrub_generic_login_refusal_when_local_auth_claimed(reply, raw)
        reply = _merge_phase50_assist(reply, raw, intent)
        return {"mode": "chat", "text": gateway_finalize_chat_reply(reply, source="full_chat_reply"), "intent": intent}

    def handle_message(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session | None = None,
    ) -> dict[str, Any]:
        gctx.extras.setdefault("via_gateway", True)
        _log.debug(
            "gateway admission channel=%s permission_keys=%s extra_keys=%s",
            gctx.channel,
            sorted(gctx.permissions.keys()),
            sorted(gctx.extras.keys()),
        )
        from app.core.db import SessionLocal
        from app.services.plugins.registry import load_plugins

        load_plugins()

        def _route(db_inner: Session) -> dict[str, Any]:
            from app.services.external_execution_credentials import maybe_handle_external_credential_chat_turn

            raw_gate = (text or "").strip()
            uid_gate = (gctx.user_id or "").strip()
            cred_gate = maybe_handle_external_credential_chat_turn(
                db_inner,
                user_id=uid_gate,
                user_text=raw_gate,
            )
            if cred_gate is not None:
                return cred_gate

            structured = self._try_structured_route(gctx, text, db_inner)
            if structured is not None:
                return structured
            approval = self._try_approval_route(gctx, text, db_inner)
            if approval is not None:
                return approval
            gctx.extras["gateway_structured_ran"] = True
            return self.handle_full_chat(gctx, text, db=db_inner)

        if db is not None:
            return _finalize_gateway_payload(_route(db))

        with SessionLocal() as session:
            return _finalize_gateway_payload(_route(session))

    def _run_mission(
        self,
        mission: dict[str, Any],
        user_id: str,
        db: Session,
        *,
        source_text: str | None = None,
    ) -> dict[str, Any]:
        from app.models.nexa_next_runtime import NexaMission, NexaMissionTask
        from app.services.events.envelope import emit_runtime_event
        from app.services.mission_control.nexa_next_state import update_state
        from app.services.runtime_agents.factory import create_runtime_agents
        from app.services.workers.loop import run_until_complete

        mission_id = str(uuid.uuid4())
        agents = create_runtime_agents(mission, user_id, mission_id=mission_id)

        title = str(mission.get("title") or "Untitled Mission")[:2000]
        raw_in = (source_text or "").strip()
        mem_input = ""
        if user_id and raw_in:
            from app.services.memory.context_injection import build_memory_context_for_turn

            turn = build_memory_context_for_turn(user_id, raw_in, purpose="mission_plan")
            if turn.get("used"):
                mem_input = str(turn.get("summary") or turn.get("memory_context") or "").strip()[:12000]
        input_text = raw_in[:50000] if raw_in else None
        if mem_input and raw_in:
            input_text = (f"[Memory context for planning]\n{mem_input}\n\n[Mission source]\n{raw_in}")[:50000]

        db.add(
            NexaMission(
                id=mission_id,
                user_id=user_id,
                title=title,
                status="running",
                input_text=input_text,
            )
        )
        for agent in agents:
            row = NexaMissionTask(
                mission_id=mission_id,
                agent_handle=agent["handle"],
                role=agent["role"],
                task=agent["task"],
                status="queued",
                depends_on=list(agent["depends_on"]),
            )
            db.add(row)
            db.flush()
            agent["task_pk"] = row.id
        db.commit()

        emit_runtime_event("mission.started", mission_id=mission_id, user_id=user_id)
        _log.info("mission.start mission_id=%s user_id=%s", mission_id, user_id)

        max_sec = get_settings().nexa_mission_max_runtime_seconds
        result, timed_out = run_until_complete(
            agents,
            mission,
            db,
            max_runtime_seconds=max_sec if max_sec and max_sec > 0 else None,
        )

        nm = db.get(NexaMission, mission_id)
        if nm is not None:
            nm.status = "timeout" if timed_out else "completed"
            db.commit()

        if timed_out:
            record_mission_timeout()
            _log.warning("mission.timeout mission_id=%s user_id=%s", mission_id, user_id)
        else:
            record_mission_completed()
            emit_runtime_event("mission.completed", mission_id=mission_id, user_id=user_id)
            _log.info("mission.completed mission_id=%s user_id=%s", mission_id, user_id)

        update_state(result)

        try:
            from app.services.memory.memory_writer import MemoryWriter

            MemoryWriter().write_mission_memory(
                user_id, mission_id, mission, result, timed_out=timed_out
            )
        except Exception:
            _log.warning("memory.persist_failed", exc_info=True)

        from app.services.mission_execution_truth import mission_agents_execution_verified

        execution_verified = bool(mission_agents_execution_verified(result))

        return {
            "status": "timeout" if timed_out else "completed",
            "mission": mission,
            "result": result,
            "timed_out": timed_out,
            "execution_verified": execution_verified,
        }

    def describe_capabilities(self) -> dict[str, bool]:
        """Return the application capability map (Phase 40 source of truth)."""
        from app.services.system_identity.capabilities import describe_capabilities as _caps

        return _caps()
