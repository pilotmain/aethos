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

# Legacy constant — Phase 35 routes generic chat through :meth:`handle_full_chat` instead.
GATEWAY_CHAT_FALLBACK_TEXT = "No mission detected"


class NexaGateway:
    """
    Central gateway: owns admission for web, Telegram, and future channels.

    Channels must call :meth:`handle_message` with a :class:`GatewayContext` rather than
    invoking agents/tools directly.
    """

    def compose_llm_reply(self, *args: Any, **kwargs: Any) -> str:
        """Phase 36 — sole supported external wrapper around legacy ``build_response``."""
        from app.services.legacy_behavior_utils import build_response

        return build_response(*args, **kwargs)

    def _try_structured_route(self, gctx: GatewayContext, text: str, db: Session) -> dict[str, Any] | None:
        """Dev runs, missions, and dev hints only — ``None`` means generic chat."""
        from app.services.dev_runtime.gateway_hint import maybe_dev_gateway_hint
        from app.services.dev_runtime.run_dev_gateway import handle_run_dev_gateway
        from app.services.missions.parser import parse_mission

        uid = gctx.user_id
        dev_out = handle_run_dev_gateway(text, uid, db)
        if dev_out is not None:
            return dev_out

        mission = parse_mission(text)
        if mission:
            return self._run_mission(mission, uid, db, source_text=text)

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
        from app.services.memory_service import MemoryService
        from app.services.orchestrator_service import OrchestratorService
        from app.services.telegram_onboarding import is_weak_input, start_message

        uid = gctx.user_id
        channel = gctx.channel
        raw = (text or "").strip()
        orchestrator = OrchestratorService()
        memory_service = MemoryService()
        settings = get_settings()

        cctx = get_or_create_context(db, uid)
        snap = build_context_snapshot(cctx, db)

        rt = route_agent(raw, context_snapshot=snap)
        rt = apply_memory_aware_route_adjustment(rt, raw, snap, db)
        routing_agent_key = str(gctx.extras.get("routing_agent_key") or rt.get("agent_key") or "nexa")

        intent = get_intent(raw, conversation_snapshot=snap)
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

        if user_row.is_new and intent == "general_chat" and is_weak_input(raw):
            sm = start_message()
            return {"mode": "chat", "text": sm, "intent": intent}

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
                    "text": apply_tone(no_tasks_response(), beh_ctx.memory),
                    "intent": intent,
                }
            orchestrator.users.mark_user_onboarded(db, uid)
            beh_ctx_after = build_context(db, uid, memory_service, orchestrator)
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
            return {"mode": "chat", "text": reply, "intent": intent}

        t_clean = strip_correction_prefix(raw)
        stripped = raw
        correction_used = t_clean != stripped and len((t_clean or "").strip()) > 2
        if looks_like_general_question(t_clean) or correction_used:
            gq = answer_general_question(
                (t_clean or "").strip() or stripped,
                conversation_snapshot=snap,
            )
            return {"mode": "chat", "text": gq, "intent": "general_answer"}

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
        return {"mode": "chat", "text": reply, "intent": intent}

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
            structured = self._try_structured_route(gctx, text, db_inner)
            if structured is not None:
                return structured
            approval = self._try_approval_route(gctx, text, db_inner)
            if approval is not None:
                return approval
            return self.handle_full_chat(gctx, text, db=db_inner)

        if db is not None:
            return _route(db)

        with SessionLocal() as session:
            return _route(session)

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
        db.add(
            NexaMission(
                id=mission_id,
                user_id=user_id,
                title=title,
                status="running",
                input_text=raw_in[:50000] if raw_in else None,
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

        return {
            "status": "timeout" if timed_out else "completed",
            "mission": mission,
            "result": result,
            "timed_out": timed_out,
        }
