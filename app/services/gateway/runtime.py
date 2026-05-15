# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""AethOS Gateway runtime — single entry for channels → missions → agents → MC."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.goal_orchestrator import nexa_llm_first_gateway_active
from app.services.logging.logger import get_logger
from app.services.metrics.runtime import record_mission_completed, record_mission_timeout

_log = get_logger("gateway")


def gateway_resolve_optional_pro_classes() -> dict[str, Any]:
    """Expose optional ``aethos_pro.*`` classes when the commercial wheel is enabled (see ``pro_extensions``)."""
    from app.services.pro_extensions import resolve_optional_pro_classes

    return resolve_optional_pro_classes()


def gateway_finalize_chat_reply(
    text: str,
    *,
    source: str = "gateway",
    user_text: str | None = None,
) -> str:
    """Normalize user-visible copy: log legacy markers, then scrub when needed (Phase 51)."""
    from app.services.external_execution_session import scrub_operator_idle_loop_phrases
    from app.services.identity.scrub import gateway_identity_needs_scrub, scrub_legacy_identity_text

    text = scrub_operator_idle_loop_phrases(text)

    if gateway_identity_needs_scrub(text):
        _log.warning(
            "gateway.identity_scrub source=%s preview=%s",
            source,
            (text or "")[:240],
        )
        text = scrub_legacy_identity_text(text)
    if user_text:
        from app.services.intent_focus_filter import extract_focused_intent
        from app.services.operator_chain_clarification import append_chain_clarification_if_needed

        text = append_chain_clarification_if_needed(text, extract_focused_intent(user_text))
    return text


def gateway_finalize_operator_or_execution_reply(
    body: str,
    *,
    user_text: str,
    layer: str,
) -> str:
    """Apply OpenClaw-style operator preamble (when enabled), then identity scrub."""
    from app.services.intent_focus_filter import (
        apply_focus_discipline_to_operator_execution_text,
        apply_operator_zero_nag_surface,
        apply_precise_operator_response,
        clean_operator_reply_format,
    )
    from app.services.operator_orchestration_intro import maybe_prepend_operator_orchestration_intro

    layered = maybe_prepend_operator_orchestration_intro(
        body,
        user_text=user_text,
        orchestration_source=layer,
    )
    layered = apply_focus_discipline_to_operator_execution_text(layered, user_text=user_text)
    settings = get_settings()
    if bool(getattr(settings, "nexa_operator_mode", False)) and bool(
        getattr(settings, "nexa_operator_zero_nag", True)
    ):
        layered = apply_operator_zero_nag_surface(layered)
    if bool(getattr(settings, "nexa_operator_mode", False)) and bool(
        getattr(settings, "nexa_operator_precise_short_responses", True)
    ):
        layered = apply_precise_operator_response(layered, user_text=user_text)
    if bool(getattr(settings, "nexa_operator_mode", False)):
        layered = clean_operator_reply_format(layered)
    return gateway_finalize_chat_reply(layered, source=layer, user_text=user_text)


def merge_credential_payload_with_chained_execution(
    db: Session,
    gctx: GatewayContext,
    *,
    uid: str,
    raw_user_text: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append bounded Railway investigation output after a stored credential ack (same HTTP request)."""
    if not payload.get("chain_bounded_runner_after_store"):
        return payload
    from app.services.conversation_context_service import build_context_snapshot, get_or_create_context
    from app.services.execution_loop import try_execute_or_explain

    _cctx = get_or_create_context(db, uid)
    _snap = build_context_snapshot(_cctx, db)
    loop_st = try_execute_or_explain(
        user_text="retry external execution",
        gctx=gctx,
        db=db,
        snapshot=_snap,
    )
    if not loop_st.handled:
        payload.pop("chain_bounded_runner_after_store", None)
        return payload
    ack = (payload.get("text") or "").rstrip()
    combined = (ack + "\n\n---\n\n" + (loop_st.text or "").strip()).strip()
    payload["text"] = gateway_finalize_operator_or_execution_reply(
        combined,
        user_text=raw_user_text,
        layer="execution_loop",
    )
    payload["execution_loop"] = True
    payload["ran"] = loop_st.ran
    payload["verified"] = loop_st.verified
    payload["blocker"] = loop_st.blocker
    payload.pop("chain_bounded_runner_after_store", None)
    return payload


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
        t2 = gateway_finalize_chat_reply(t, source="gateway_payload")
        from app.services.chat_response_banner import apply_gateway_response_style

        intent_val = payload.get("intent")
        intent_str = str(intent_val) if intent_val is not None else ""
        t2 = apply_gateway_response_style(intent_str, t2)
        return {**payload, "text": t2}
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
        from app.services.host_executor_intent import parse_file_write_intent
        from app.services.goal_orchestrator import is_goal_planning_line

        if parse_file_write_intent(raw):
            return None
        if is_goal_planning_line(raw):
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
            settings = get_settings()
            if len(rows) == 0 and bool(getattr(settings, "nexa_operator_mode", False)) and bool(
                getattr(settings, "nexa_operator_zero_nag", True)
            ):
                return None
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
        if (
            conf == "medium"
            and bool(getattr(settings, "nexa_execution_confirm_medium", True))
            and not bool(getattr(settings, "nexa_operator_mode", False))
        ):
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

    @staticmethod
    def _host_action_intent_from_state(
        db: Session,
        cctx: Any,
        related_job_ids: tuple[int, ...],
    ) -> str:
        """Best-effort host action name for gateway clients that branch on ``intent``."""
        for raw in (
            getattr(cctx, "next_action_pending_inject_json", None),
            getattr(cctx, "blocked_host_executor_json", None),
        ):
            if not (raw or "").strip():
                continue
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if not isinstance(parsed, dict):
                continue
            payload = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else parsed
            action = str(payload.get("host_action") or "").strip()
            if action:
                if action == "run_command" and str(payload.get("command") or "").strip():
                    return "command_approval"
                return action

        if related_job_ids:
            try:
                from app.models.agent_job import AgentJob

                job = db.get(AgentJob, int(related_job_ids[0]))
                payload = job.payload_json if job is not None else None
                if isinstance(payload, dict):
                    action = str(payload.get("host_action") or "").strip()
                    if action:
                        if action == "run_command" and str(payload.get("command") or "").strip():
                            return "command_approval"
                        return action
            except (TypeError, ValueError):
                pass

        return "host_executor"

    def _try_operator_and_execution_loop(
        self,
        gctx: GatewayContext,
        raw_gate: str,
        db: Session,
    ) -> dict[str, Any] | None:
        """
        Bounded operator CLI + external execution loop before host NL or ``parse_mission``.

        Must run ahead of :meth:`_try_host_executor_turn` (which probes mission syntax) so
        Railway/deploy-shaped asks short-circuit without spawning fake https missions.
        """
        from app.services.conversation_context_service import build_context_snapshot, get_or_create_context
        from app.services.execution_loop import try_execute_or_explain
        from app.services.operator_execution_loop import try_operator_execution

        uid_gate = (gctx.user_id or "").strip()
        raw = (raw_gate or "").strip()
        if not uid_gate or not raw:
            return None

        _cctx_loop = get_or_create_context(db, uid_gate)
        _snap_loop = build_context_snapshot(_cctx_loop, db)

        if not gctx.extras.get("operator_execution_attempted"):
            op_result = try_operator_execution(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=_snap_loop,
            )
            gctx.extras["operator_execution_attempted"] = True
            if op_result.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        op_result.text,
                        user_text=raw,
                        layer="operator_execution",
                    ),
                    "operator_execution": True,
                    "operator_provider": op_result.provider,
                    "ran": op_result.ran,
                    "verified": op_result.verified,
                    "blocker": op_result.blocker,
                    "operator_evidence": op_result.evidence,
                    "intent": "operator_execution",
                }

        if not gctx.extras.get("execution_loop_attempted"):
            loop_result = try_execute_or_explain(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=_snap_loop,
            )
            gctx.extras["execution_loop_attempted"] = True
            if loop_result.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        loop_result.text,
                        user_text=raw,
                        layer="execution_loop",
                    ),
                    "execution_loop": True,
                    "ran": loop_result.ran,
                    "blocker": loop_result.blocker,
                    "verified": loop_result.verified,
                    "intent": loop_result.intent or "execution_loop",
                }
        return None

    def _try_host_executor_turn(self, gctx: GatewayContext, text: str, db: Session) -> dict[str, Any] | None:
        """
        Mission-control gateway parity with web chat's deterministic host executor path.

        This keeps mutating local actions permission/confirmation-gated while preventing
        file-write requests from falling through to sub-agent creation or generic chat.
        """
        raw = (text or "").strip()
        uid = (gctx.user_id or "").strip()
        if not uid or not raw:
            return None
        from app.services.missions.parser import parse_mission

        if parse_mission(raw):
            return None

        from app.services.conversation_context_service import get_or_create_context
        from app.services.host_executor_chat import (
            evaluate_deterministic_host_permission_turn,
            may_run_pre_llm_deterministic_host,
            try_apply_host_executor_turn,
        )

        s = get_settings()
        debug_owner = (os.environ.get("NEXA_DEBUG_GATEWAY_OWNER_BYPASS") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        raw_auto = (os.environ.get("NEXA_AUTO_APPROVE_OWNER") or "").strip().lower()
        if raw_auto in ("0", "false", "no"):
            auto_owner = False
        elif raw_auto in ("1", "true", "yes"):
            auto_owner = True
        else:
            auto_owner = bool(getattr(s, "nexa_auto_approve_owner", True))

        if debug_owner:
            owners_env = (os.environ.get("AETHOS_OWNER_IDS") or "").strip()
            owners_settings = (getattr(s, "aethos_owner_ids", None) or "").strip()
            host_ex = bool(getattr(s, "nexa_host_executor_enabled", False))
            _log.info(
                "[DEBUG] host_executor_turn text_preview=%r user_id=%r nexa_host_executor_enabled=%s "
                "NEXA_AUTO_APPROVE_OWNER(raw_env)=%r resolved_auto_owner=%s "
                "settings.nexa_auto_approve_owner=%s AETHOS_OWNER_IDS(env)=%r settings.aethos_owner_ids=%r",
                (raw[:50] + ("…" if len(raw) > 50 else "")),
                uid,
                host_ex,
                (os.environ.get("NEXA_AUTO_APPROVE_OWNER") or ""),
                auto_owner,
                getattr(s, "nexa_auto_approve_owner", None),
                owners_env[:300],
                owners_settings[:300],
            )

        web_session_id = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
        cctx = get_or_create_context(db, uid, web_session_id=web_session_id)
        if bool(getattr(s, "nexa_host_executor_enabled", False)) and auto_owner:
            from app.services.user_capabilities import is_privileged_owner_for_web_mutations

            is_owner = is_privileged_owner_for_web_mutations(db, uid)
            if debug_owner:
                _log.info(
                    "[DEBUG] host_executor_turn owner_gate is_privileged_owner=%s (AETHOS_OWNER_IDS must "
                    "contain this user_id for web_* operators)",
                    is_owner,
                )

            if is_owner:
                from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
                from app.services.host_executor import execute_payload
                from app.services.host_executor_chat import _validate_enqueue_payload
                from app.services.host_executor_nl_chain import try_infer_browser_automation_nl
                from app.services.nexa_safety_policy import stamp_host_payload

                inf_browser = try_infer_browser_automation_nl(raw)
                if debug_owner:
                    _log.info(
                        "[DEBUG] host_executor_turn try_infer_browser_automation_nl matched=%s payload_keys=%s",
                        bool(inf_browser),
                        sorted(inf_browser.keys()) if isinstance(inf_browser, dict) else None,
                    )
                if inf_browser:
                    stamped_b = stamp_host_payload(
                        apply_trusted_instruction_source(
                            dict(inf_browser), InstructionSource.USER_MESSAGE.value
                        )
                    )
                    safe_browser = _validate_enqueue_payload(stamped_b)
                    if debug_owner:
                        _log.info(
                            "[DEBUG] host_executor_turn owner browser path safe_browser=%s host_action=%r",
                            bool(safe_browser),
                            (safe_browser or {}).get("host_action") if isinstance(safe_browser, dict) else None,
                        )
                    if safe_browser:
                        if debug_owner:
                            _log.info(
                                "[DEBUG] Owner bypass active — executing browser/host payload immediately "
                                "(source=host_executor_owner_browser)"
                            )

                        class _OwnerBrowserJob:
                            user_id = uid
                            payload_json: dict[str, Any] = {}

                        try:
                            text_br = execute_payload(safe_browser, db=db, job=_OwnerBrowserJob())
                        except ValueError as exc:
                            err_br = f"I couldn't run that browser action: {exc}"[:4000]
                            return {
                                "mode": "chat",
                                "text": gateway_finalize_chat_reply(
                                    err_br, source="host_executor_owner_browser", user_text=raw
                                ),
                                "intent": "host_executor",
                                "host_executor": True,
                            }
                        reply_br = (text_br or "").strip()[:12000] or "(no output)"
                        ha_br = (safe_browser.get("host_action") or "").strip().lower()
                        intent_br = (
                            "browser_host"
                            if ha_br in ("plugin_skill", "chain", "browser_open", "browser_screenshot")
                            else "command_completed"
                        )
                        return {
                            "mode": "chat",
                            "text": gateway_finalize_chat_reply(
                                reply_br, source="host_executor_owner_browser", user_text=raw
                            ),
                            "intent": intent_br,
                            "host_executor": True,
                        }

        result = try_apply_host_executor_turn(db, cctx, raw, web_session_id=web_session_id)
        if result is None and may_run_pre_llm_deterministic_host(cctx):
            result = evaluate_deterministic_host_permission_turn(
                db,
                cctx,
                raw,
                web_session_id=web_session_id,
            )
        if result is None:
            return None

        db.refresh(cctx)
        intent = result.intent_override or self._host_action_intent_from_state(
            db, cctx, result.related_job_ids
        )
        out: dict[str, Any] = {
            "mode": "chat",
            "text": result.early_assistant or result.inject_ack or "",
            "intent": intent,
            "host_executor": True,
        }
        if result.related_job_ids:
            out["related_job_ids"] = list(result.related_job_ids)
        if result.pending_system_events:
            out["pending_system_events"] = [
                {"kind": kind, "text": event_text} for kind, event_text in result.pending_system_events
            ]
        if result.permission_required:
            out["permission_required"] = result.permission_required
        if result.telegram_inline_keyboard_rows:
            out["telegram_inline_keyboard_rows"] = result.telegram_inline_keyboard_rows
        return out

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
        _uid = (gctx.user_id or "").strip()
        raw_t = (text or "").strip()
        if _uid and raw_t:
            from app.services.memory.context_injection import build_memory_context_for_turn

            turn = build_memory_context_for_turn(_uid, raw_t, purpose="gateway_structured")
            if turn.get("used"):
                if gctx.memory is None:
                    gctx.memory = {}
                gctx.memory.update(turn)

        from app.services.conversation_context_service import build_context_snapshot, get_or_create_context
        from app.services.execution_loop import try_execute_or_explain
        from app.services.external_execution_credentials import maybe_handle_external_credential_chat_turn

        cred_st = maybe_handle_external_credential_chat_turn(db, user_id=_uid, user_text=raw_t)
        if cred_st is not None:
            return merge_credential_payload_with_chained_execution(
                db,
                gctx,
                uid=_uid,
                raw_user_text=raw_t,
                payload=cred_st,
            )

        if _uid and raw_t:
            _cctx_st = get_or_create_context(db, _uid)
            _snap_st = build_context_snapshot(_cctx_st, db)
            from app.services.operator_execution_loop import try_operator_execution

            op_st = try_operator_execution(
                user_text=raw_t,
                gctx=gctx,
                db=db,
                snapshot=_snap_st,
            )
            gctx.extras["operator_execution_attempted"] = True
            if op_st.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        op_st.text,
                        user_text=raw_t,
                        layer="operator_execution",
                    ),
                    "operator_execution": True,
                    "operator_provider": op_st.provider,
                    "ran": op_st.ran,
                    "verified": op_st.verified,
                    "blocker": op_st.blocker,
                    "operator_evidence": op_st.evidence,
                    "intent": "operator_execution",
                }

            loop_st = try_execute_or_explain(
                user_text=raw_t,
                gctx=gctx,
                db=db,
                snapshot=_snap_st,
            )
            gctx.extras["execution_loop_attempted"] = True
            if loop_st.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        loop_st.text,
                        user_text=raw_t,
                        layer="execution_loop",
                    ),
                    "execution_loop": True,
                    "ran": loop_st.ran,
                    "blocker": loop_st.blocker,
                    "verified": loop_st.verified,
                    "intent": loop_st.intent or "execution_loop",
                }

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
        from app.services.session_queue import gateway_lane_id, session_queue

        def _body() -> dict[str, Any]:
            gctx.extras["operator_execution_attempted"] = False
            approval = self._try_approval_route(gctx, text, db)
            if approval is not None:
                return approval
            from app.services.gateway.sandbox_nl import (
                try_sandbox_approve_gateway_turn,
                try_sandbox_development_file_fastpath,
                try_sandbox_plan_gateway_turn,
            )

            raw_c = (text or "").strip()
            sbx_apr = try_sandbox_approve_gateway_turn(gctx, raw_c, db)
            if sbx_apr is not None:
                return sbx_apr

            dev_sbx = try_sandbox_development_file_fastpath(gctx, raw_c, db)
            if dev_sbx is not None:
                return dev_sbx

            sbx_plan = try_sandbox_plan_gateway_turn(gctx, raw_c, db)
            if sbx_plan is not None:
                return sbx_plan
            from app.services.gateway.llm_fallback import try_gateway_llm_fallback_turn

            llm_fb = try_gateway_llm_fallback_turn(gctx, raw_c, db)
            if llm_fb is not None:
                return llm_fb
            return self.handle_full_chat(gctx, text, db=db)

        with session_queue.acquire(gateway_lane_id(gctx)):
            return _body()

    def _route_gateway_llm_first(
        self,
        db_inner: Session,
        gctx: GatewayContext,
        raw_gate: str,
        text: str,
    ) -> dict[str, Any]:
        """Host + deploy + agents + executor, then :meth:`handle_full_chat` (LLM-first interior)."""
        from app.services.gateway.deploy_nl import try_gateway_deploy_turn
        from app.services.gateway.deployment_status_nl import try_gateway_deployment_status_turn
        from app.services.gateway.early_nl_host_actions import try_early_nl_host_actions
        from app.services.gateway.start_built_app_gateway_turn import try_start_built_app_gateway_turn
        from app.services.inter_agent_coordinator import try_inter_agent_gateway_turn
        from app.services.sub_agent_router import try_sub_agent_gateway_turn

        uid_gate = (gctx.user_id or "").strip()

        loop_early = self._try_operator_and_execution_loop(gctx, raw_gate, db_inner)
        if loop_early is not None:
            return loop_early

        host_out = self._try_host_executor_turn(gctx, raw_gate, db_inner)
        if host_out is not None:
            return host_out

        early_nl = try_early_nl_host_actions(gctx, raw_gate, db_inner)
        if early_nl is not None:
            return early_nl

        deploy_status = try_gateway_deployment_status_turn(gctx, raw_gate, db_inner)
        if deploy_status is not None:
            return deploy_status

        deploy_nl = try_gateway_deploy_turn(gctx, raw_gate, db_inner)
        if deploy_nl is not None:
            return deploy_nl

        start_app_nl = try_start_built_app_gateway_turn(gctx, raw_gate, db_inner)
        if start_app_nl is not None:
            return start_app_nl

        inter_ag = try_inter_agent_gateway_turn(gctx, raw_gate, db_inner)
        if inter_ag is not None:
            return inter_ag

        orch = try_sub_agent_gateway_turn(gctx, raw_gate, db_inner)
        if orch is not None:
            return orch

        structured = self._try_structured_route(gctx, text, db_inner)
        if structured is not None:
            return structured
        approval = self._try_approval_route(gctx, text, db_inner)
        if approval is not None:
            return approval
        gctx.extras["gateway_structured_ran"] = True
        return self.handle_full_chat(gctx, text, db=db_inner)

    def _handle_full_chat_llm_first_tail(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session,
    ) -> dict[str, Any]:
        """After credentials: snapshot + memory + ``general_chat`` LLM reply only (no planner/greeting NL)."""
        from app.services.legacy_behavior_utils import build_context
        from app.services.conversation_context_service import (
            build_context_snapshot,
            get_or_create_context,
        )
        from app.services.execution_loop import try_execute_or_explain
        from app.services.memory.context_injection import build_memory_context_for_turn
        from app.services.memory.memory_index import MemoryIndex
        from app.services.memory_service import MemoryService
        from app.services.operator_execution_loop import try_operator_execution
        from app.services.orchestrator_service import OrchestratorService

        uid = gctx.user_id
        channel = gctx.channel
        raw = (text or "").strip()
        _ws_full = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
        cctx = get_or_create_context(db, uid, web_session_id=_ws_full)
        snap = build_context_snapshot(cctx, db)
        from app.services.memory_manager import enrich_conversation_snapshot_for_llm

        snap = enrich_conversation_snapshot_for_llm(snap, cctx, raw)
        if isinstance(snap, dict):
            snap.setdefault("web_session_id", _ws_full)

        if not gctx.extras.get("operator_execution_attempted"):
            op_fb = try_operator_execution(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=snap,
            )
            gctx.extras["operator_execution_attempted"] = True
            if op_fb.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        op_fb.text,
                        user_text=raw,
                        layer="operator_execution",
                    ),
                    "operator_execution": True,
                    "operator_provider": op_fb.provider,
                    "ran": op_fb.ran,
                    "verified": op_fb.verified,
                    "blocker": op_fb.blocker,
                    "operator_evidence": op_fb.evidence,
                    "intent": "operator_execution",
                }

        if not gctx.extras.get("execution_loop_attempted"):
            loop_fb = try_execute_or_explain(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=snap,
            )
            gctx.extras["execution_loop_attempted"] = True
            if loop_fb.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        loop_fb.text,
                        user_text=raw,
                        layer="execution_loop",
                    ),
                    "execution_loop": True,
                    "ran": loop_fb.ran,
                    "blocker": loop_fb.blocker,
                    "verified": loop_fb.verified,
                    "intent": loop_fb.intent or "execution_loop",
                }

        if not (isinstance(gctx.memory, dict) and gctx.memory.get("used")):
            turn_mem = build_memory_context_for_turn(uid, raw, purpose="chat")
            if turn_mem.get("used"):
                if gctx.memory is None:
                    gctx.memory = {}
                gctx.memory.update(turn_mem)
                if turn_mem.get("active_memory_used"):
                    _log.info(
                        "gateway.active_memory hits=%s",
                        turn_mem.get("active_memory_hits"),
                        extra={"nexa_event": "gateway_active_memory"},
                    )

        orchestrator = OrchestratorService()
        memory_service = MemoryService()

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

        routing_agent_key = str(gctx.extras.get("routing_agent_key") or "aethos")

        uid_stripped = (uid or "").strip()
        orchestrator.users.get_or_create(db, uid)
        beh_ctx = build_context(db, uid, memory_service, orchestrator)
        _attach_memory_brain(beh_ctx)

        intent = "general_chat"
        _log.info(
            "gateway.full_chat_llm_first channel=%s",
            channel,
        )

        from app.services.external_execution_session import (
            scrub_generic_login_refusal_when_local_auth_claimed,
        )

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
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(reply, source="full_chat_llm_first", user_text=raw),
            "intent": intent,
        }

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
            return merge_credential_payload_with_chained_execution(
                db,
                gctx,
                uid=(uid or "").strip(),
                raw_user_text=raw,
                payload=cred_full,
            )

        if nexa_llm_first_gateway_active():
            # Co-pilot next-step parsing must not intercept general NL; see ``next_action_confirmation``
            # (no "Reply run" / fuzzy substitution when LLM-first is on).
            return self._handle_full_chat_llm_first_tail(gctx, text, db=db)

        _ws_full = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
        cctx = get_or_create_context(db, uid, web_session_id=_ws_full)
        snap = build_context_snapshot(cctx, db)
        from app.services.memory_manager import enrich_conversation_snapshot_for_llm

        snap = enrich_conversation_snapshot_for_llm(snap, cctx, raw)
        if isinstance(snap, dict):
            snap.setdefault("web_session_id", _ws_full)

        from app.core.config import get_settings as _orch_get_settings

        if (
            _orch_get_settings().nexa_orchestration_enabled
            and (uid or "").strip()
            and raw
        ):
            from app.services.orchestration.delegate import format_delegation_reply, run_delegation
            from app.services.orchestration.policy import parse_gateway_delegate

            parsed = parse_gateway_delegate(raw)
            if parsed:
                agents, goal, parallel = parsed
                out = run_delegation(
                    db,
                    uid,
                    agents,
                    goal,
                    parallel=parallel,
                    channel=str(channel or "web")[:32],
                    web_session_id=gctx.extras.get("web_session_id"),
                )
                return {
                    "mode": "chat",
                    "text": format_delegation_reply(out),
                    "intent": "orchestration_delegate",
                    "orchestration_delegate": True,
                    "spawn_group_id": out.get("spawn_group_id"),
                    "ok": out.get("ok"),
                }

        if not gctx.extras.get("operator_execution_attempted"):
            from app.services.operator_execution_loop import try_operator_execution

            op_fb = try_operator_execution(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=snap,
            )
            gctx.extras["operator_execution_attempted"] = True
            if op_fb.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        op_fb.text,
                        user_text=raw,
                        layer="operator_execution",
                    ),
                    "operator_execution": True,
                    "operator_provider": op_fb.provider,
                    "ran": op_fb.ran,
                    "verified": op_fb.verified,
                    "blocker": op_fb.blocker,
                    "operator_evidence": op_fb.evidence,
                    "intent": "operator_execution",
                }

        if not gctx.extras.get("execution_loop_attempted"):
            from app.services.execution_loop import try_execute_or_explain

            loop_fb = try_execute_or_explain(
                user_text=raw,
                gctx=gctx,
                db=db,
                snapshot=snap,
            )
            gctx.extras["execution_loop_attempted"] = True
            if loop_fb.handled:
                return {
                    "mode": "chat",
                    "text": gateway_finalize_operator_or_execution_reply(
                        loop_fb.text,
                        user_text=raw,
                        layer="execution_loop",
                    ),
                    "execution_loop": True,
                    "ran": loop_fb.ran,
                    "blocker": loop_fb.blocker,
                    "verified": loop_fb.verified,
                    "intent": loop_fb.intent or "execution_loop",
                }

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
                if turn_mem.get("active_memory_used"):
                    _log.info(
                        "gateway.active_memory hits=%s",
                        turn_mem.get("active_memory_hits"),
                        extra={"nexa_event": "gateway_active_memory"},
                    )

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

        rt = route_agent(raw, context_snapshot=snap)
        rt = apply_memory_aware_route_adjustment(rt, raw, snap, db)
        routing_agent_key = str(gctx.extras.get("routing_agent_key") or rt.get("agent_key") or "aethos")

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

        if intent == "config_query":
            from app.services.config_query import handle_config_query

            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    handle_config_query(raw),
                    source="config_query",
                    user_text=raw,
                ),
                "intent": "config_query",
            }

        if intent == "greeting":
            from app.services.gateway.greeting_replies import greeting_reply_for_text

            body = greeting_reply_for_text(raw)
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(body, source="greeting_reply", user_text=raw),
                "intent": "greeting",
            }

        # Orchestration sub-agents (Mission Control): NL roster → create_sub_agent via intent_classifier +
        # looks_like_registry_agent_creation_nl (Phase 54/59).
        # Web ``/web/chat`` runs this spawn path when ``prefers_registry_sub_agent`` is true before
        # ``get_intent`` — gateway must do the same, otherwise ``POST …/mission-control/gateway/run``
        # falls through to general chat when the classifier returns ``general_chat``.
        from app.services.sub_agent_natural_creation import (
            prefers_registry_sub_agent,
            try_spawn_natural_sub_agents,
        )
        from app.services.sub_agent_router import orchestration_chat_key

        uid_stripped = (uid or "").strip()
        registry_nl = bool(uid_stripped and prefers_registry_sub_agent(raw))
        intent_spawn = intent in ("create_sub_agent", "create_custom_agent")
        if uid_stripped and (intent_spawn or registry_nl):
            if intent == "create_sub_agent" or registry_nl:
                orch_key = orchestration_chat_key(gctx)
                sub_txt = try_spawn_natural_sub_agents(db, uid, raw, parent_chat_id=orch_key)
                if sub_txt:
                    return {
                        "mode": "chat",
                        "text": gateway_finalize_chat_reply(
                            sub_txt, source="natural_sub_agent_create", user_text=raw
                        ),
                        "intent": "create_sub_agent",
                    }

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
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(sm, source="onboarding_weak_reply", user_text=raw),
                "intent": intent,
            }

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
                        user_text=raw,
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
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(reply, source="brain_dump_reply", user_text=raw),
                "intent": intent,
            }

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
            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    gq,
                    source="general_answer",
                    user_text=(t_clean or "").strip() or stripped,
                ),
                "intent": "general_answer",
            }

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
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(reply, source="full_chat_reply", user_text=raw),
            "intent": intent,
        }

    def handle_message(
        self,
        gctx: GatewayContext,
        text: str,
        *,
        db: Session | None = None,
    ) -> dict[str, Any]:
        gctx.extras.setdefault("via_gateway", True)
        gctx.extras["execution_loop_attempted"] = False
        gctx.extras["operator_execution_attempted"] = False
        _log.debug(
            "gateway admission channel=%s permission_keys=%s extra_keys=%s",
            gctx.channel,
            sorted(gctx.permissions.keys()),
            sorted(gctx.extras.keys()),
        )
        from app.core.db import SessionLocal
        from app.services.plugins.registry import load_plugins

        load_plugins()

        vis_uid = (gctx.user_id or "").strip()
        from app.services.agent_visibility_feed import drain_user_visibility_banner

        visibility_banner = drain_user_visibility_banner(vis_uid) if vis_uid else None

        from app.services.session_queue import gateway_lane_id, session_queue

        def _merge_visibility_banner(payload: dict[str, Any], banner: str | None) -> dict[str, Any]:
            if not banner or not isinstance(payload, dict):
                return payload
            t = payload.get("text")
            if isinstance(t, str) and t.strip():
                return {**payload, "text": (banner.rstrip() + "\n\n" + t).strip()}
            return {**payload, "text": banner}

        def _route(db_inner: Session) -> dict[str, Any]:
            from app.services.external_execution_credentials import maybe_handle_external_credential_chat_turn

            raw_gate = (text or "").strip()
            uid_gate = (gctx.user_id or "").strip()
            # External-credential capture must stay first; then LLM-first skips all other NL shortcuts below.
            cred_gate = maybe_handle_external_credential_chat_turn(
                db_inner,
                user_id=uid_gate,
                user_text=raw_gate,
            )
            if cred_gate is not None:
                return merge_credential_payload_with_chained_execution(
                    db_inner,
                    gctx,
                    uid=uid_gate,
                    raw_user_text=raw_gate,
                    payload=cred_gate,
                )

            loop_early = self._try_operator_and_execution_loop(gctx, raw_gate, db_inner)
            if loop_early is not None:
                return loop_early

            if nexa_llm_first_gateway_active():
                # Same as full-chat path: LLM-first before co-pilot / deterministic NL (``next_action_confirmation``).
                return self._route_gateway_llm_first(db_inner, gctx, raw_gate, text)

            from app.services.config_query import handle_config_query
            from app.services.intent_classifier import is_config_query

            if is_config_query(raw_gate):
                return {
                    "mode": "chat",
                    "text": gateway_finalize_chat_reply(
                        handle_config_query(raw_gate),
                        source="config_query",
                        user_text=raw_gate,
                    ),
                    "intent": "config_query",
                }

            _log.debug(
                "host_executor gateway check text=%s",
                (raw_gate[:50] + ("…" if len(raw_gate) > 50 else "")),
            )
            host_out = self._try_host_executor_turn(gctx, raw_gate, db_inner)
            if host_out is not None:
                return host_out

            from app.services.gateway.soul_versioning_nl import try_soul_versioning_nl_turn

            soul_nl = try_soul_versioning_nl_turn(gctx, raw_gate, db_inner)
            if soul_nl is not None:
                return soul_nl

            from app.services.gateway.early_nl_host_actions import try_early_nl_host_actions

            early_nl = try_early_nl_host_actions(gctx, raw_gate, db_inner)
            if early_nl is not None:
                return early_nl

            from app.services.intent_classifier import (
                ambiguous_product_clarification_reply,
                is_ambiguous_product_request,
            )

            if is_ambiguous_product_request(raw_gate):
                return {
                    "mode": "chat",
                    "text": gateway_finalize_chat_reply(
                        ambiguous_product_clarification_reply(),
                        source="ambiguous_product_request",
                        user_text=raw_gate,
                    ),
                    "intent": "clarification",
                }

            from app.services.gateway.sandbox_nl import try_sandbox_approve_gateway_turn

            sbx_apr = try_sandbox_approve_gateway_turn(gctx, raw_gate, db_inner)
            if sbx_apr is not None:
                return sbx_apr

            from app.services.gateway.intelligence_nl import try_gateway_llm_intelligence_turn

            intel_nl = try_gateway_llm_intelligence_turn(gctx, raw_gate, db_inner)
            if intel_nl is not None:
                return intel_nl

            from app.services.gateway.owner_self_improvement_nl import (
                try_owner_self_improvement_nl_turn,
            )

            owner_si = try_owner_self_improvement_nl_turn(gctx, raw_gate, db_inner)
            if owner_si is not None:
                return owner_si

            from app.services.gateway.agent_os_nl import try_agent_os_status_turn

            agent_os_st = try_agent_os_status_turn(gctx, raw_gate, db_inner)
            if agent_os_st is not None:
                return agent_os_st

            from app.services.gateway.sandbox_nl import try_sandbox_development_file_fastpath

            dev_sbx = try_sandbox_development_file_fastpath(gctx, raw_gate, db_inner)
            if dev_sbx is not None:
                return dev_sbx

            from app.services.gateway.development_nl import try_development_nl_gateway_turn

            dev_nl = try_development_nl_gateway_turn(gctx, raw_gate, db_inner)
            if dev_nl is not None:
                return dev_nl

            from app.services.gateway.sandbox_nl import try_sandbox_plan_gateway_turn

            sbx_plan = try_sandbox_plan_gateway_turn(gctx, raw_gate, db_inner)
            if sbx_plan is not None:
                return sbx_plan

            from app.services.gateway.deployment_status_nl import (
                try_gateway_deployment_status_turn,
            )

            deploy_status = try_gateway_deployment_status_turn(gctx, raw_gate, db_inner)
            if deploy_status is not None:
                return deploy_status

            from app.services.gateway.deploy_nl import try_gateway_deploy_turn

            deploy_nl = try_gateway_deploy_turn(gctx, raw_gate, db_inner)
            if deploy_nl is not None:
                return deploy_nl

            from app.services.gateway.start_built_app_nl import try_start_built_app_gateway_turn

            start_app_nl = try_start_built_app_gateway_turn(gctx, raw_gate, db_inner)
            if start_app_nl is not None:
                return start_app_nl

            from app.services.inter_agent_coordinator import try_inter_agent_gateway_turn

            inter_ag = try_inter_agent_gateway_turn(gctx, raw_gate, db_inner)
            if inter_ag is not None:
                return inter_ag

            from app.services.sub_agent_router import try_sub_agent_gateway_turn

            orch = try_sub_agent_gateway_turn(gctx, raw_gate, db_inner)
            if orch is not None:
                return orch

            structured = self._try_structured_route(gctx, text, db_inner)
            if structured is not None:
                return structured
            approval = self._try_approval_route(gctx, text, db_inner)
            if approval is not None:
                return approval
            gctx.extras["gateway_structured_ran"] = True
            from app.services.gateway.llm_fallback import try_gateway_llm_fallback_turn

            llm_fb = try_gateway_llm_fallback_turn(gctx, raw_gate, db_inner)
            if llm_fb is not None:
                return llm_fb
            return self.handle_full_chat(gctx, text, db=db_inner)

        def _dispatch_lane() -> dict[str, Any]:
            if db is not None:
                out = _merge_visibility_banner(_finalize_gateway_payload(_route(db)), visibility_banner)
            else:
                with SessionLocal() as session:
                    out = _merge_visibility_banner(_finalize_gateway_payload(_route(session)), visibility_banner)
            try:
                from app.services.jsonl_audit_log import log_jsonl_audit_event

                uid = (gctx.user_id or "").strip() or "unknown"
                intent = out.get("intent") if isinstance(out, dict) else None
                mode = out.get("mode") if isinstance(out, dict) else None
                log_jsonl_audit_event(
                    user_id=uid,
                    action="gateway.chat",
                    outcome="success",
                    details={
                        "intent": intent,
                        "mode": mode,
                        "channel": gctx.channel,
                    },
                )
            except Exception:  # noqa: BLE001
                pass
            return out

        with session_queue.acquire(gateway_lane_id(gctx)):
            return _dispatch_lane()

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
