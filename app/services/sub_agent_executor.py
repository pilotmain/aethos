"""
Week 4 Phase 3 + Week 5 hardening — sync sub-agent execution (domain dispatch).

``nexa_agent_orchestration_autoqueue``: when true, may run ``execute_payload`` in-process
subject to :mod:`app.services.sub_agent_autoqueue_guard`. Otherwise enqueues jobs.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.budget.hooks import budget_enabled, estimate_tokens_from_text
from app.services.budget.models import UsageType
from app.services.budget.tracker import BudgetTracker
from app.services.host_executor import execute_payload
from app.services.host_executor_chat import _validate_enqueue_payload, enqueue_host_job_from_validated_payload
from app.services.host_executor_intent import title_for_payload
from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.sub_agent_audit import log_agent_event
from app.services.sub_agent_auto_approve import get_auto_approve_message, should_auto_approve
from app.services.sub_agent_autoqueue_guard import (
    record_autoqueue_success,
    should_run_autoqueue_payload,
)
from app.services.sub_agent_rate_limit import check_rate_limits, record_rate_limited_action
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent

logger = logging.getLogger(__name__)

_QA_NAMES = frozenset({"qa_agent", "qa", "security_agent"})
_QA_DOMAINS = frozenset({"qa", "security", "sec"})


class AgentExecutor:
    """Dispatches sub-agent messages to allowlisted host payloads (sync)."""

    @property
    def registry(self) -> AgentRegistry:
        return AgentRegistry()

    def execute(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str = "default",
    ) -> str:
        msg = (message or "").strip()
        if not msg:
            return f"Agent '{agent.name}' has no instruction text."

        if budget_enabled():
            bt = BudgetTracker()
            bt.check_and_reset_budget(agent.id)
            budget = bt.get_or_create_budget(agent.id)
            reserve = max(2048, estimate_tokens_from_text(msg))
            if not budget.can_execute(reserve):
                return (
                    f"⚠️ Agent '{agent.name}' work-hour budget is exhausted for this period "
                    f"(monthly limit: {budget.monthly_limit:,} tokens). "
                    "Ask an admin to raise limits with `/budget` or wait for the next reset."
                )

        ok, rate_err = check_rate_limits(agent.id, agent.domain, chat_id)
        if not ok:
            log_agent_event(
                "rate_limited",
                agent_id=agent.id,
                agent_name=agent.name,
                domain=agent.domain,
                chat_id=chat_id,
                user_id=user_id,
                action=msg[:500],
                success=False,
                error=rate_err,
            )
            return f"⏸️ {rate_err}"

        t0 = time.perf_counter()
        self.registry.update_status(agent.id, AgentStatus.BUSY)
        try:
            out = self._dispatch(
                agent, msg, chat_id, db=db, user_id=user_id, web_session_id=web_session_id
            )
            if budget_enabled():
                bt = BudgetTracker()
                used = estimate_tokens_from_text(msg) + estimate_tokens_from_text(out)
                bt.record_usage(
                    agent.id,
                    max(1, used),
                    UsageType.AGENT_TASK,
                    description=f"Agent task: {msg[:120]}",
                    member_name=agent.name,
                )
            record_rate_limited_action(agent.id, agent.domain, chat_id)
            self.registry.touch_agent(agent.id)
            dur_ms = (time.perf_counter() - t0) * 1000.0
            log_agent_event(
                "execute",
                agent_id=agent.id,
                agent_name=agent.name,
                domain=agent.domain,
                chat_id=chat_id,
                user_id=user_id,
                action=msg[:500],
                success=True,
                duration_ms=dur_ms,
            )
            get_activity_tracker().log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="execute",
                input_data={"message": msg[:2000]},
                output_data={"preview": (out or "")[:2000]},
                success=True,
                duration_ms=dur_ms,
                metadata={"chat_id": chat_id, "user_id": user_id},
            )
            return out
        except Exception as exc:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            log_agent_event(
                "execute",
                agent_id=agent.id,
                agent_name=agent.name,
                domain=agent.domain,
                chat_id=chat_id,
                user_id=user_id,
                action=msg[:500],
                success=False,
                error=str(exc)[:2000],
                duration_ms=dur_ms,
            )
            get_activity_tracker().log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="execute",
                input_data={"message": msg[:2000]},
                success=False,
                error=str(exc)[:2000],
                duration_ms=dur_ms,
                metadata={"chat_id": chat_id, "user_id": user_id},
            )
            logger.exception("sub_agent execute failed agent=%s", agent.id)
            return f"Execution failed: {exc}"
        finally:
            cur = self.registry.get_agent(agent.id)
            if cur is not None and cur.status == AgentStatus.BUSY:
                self.registry.update_status(agent.id, AgentStatus.IDLE)

    def _is_qa_security_agent(self, agent: SubAgent) -> bool:
        n = (agent.name or "").strip().lower()
        d = (agent.domain or "").strip().lower()
        return n in _QA_NAMES or d in _QA_DOMAINS

    def _dispatch(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        if self._is_qa_security_agent(agent):
            from app.services.qa_agent.security_review import run_security_review_sync

            return run_security_review_sync(agent, message, db=db, user_id=user_id)

        domain = (agent.domain or "").strip().lower()
        if domain == "git":
            return self._git(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "vercel":
            return self._vercel(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "test":
            return self._test(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "railway":
            return (
                "Railway sub-agent is not wired to host execution in this release. "
                "Use the operator / execution loop for Railway, or extend `sub_agent_executor`."
            )
        return f"Unknown sub-agent domain {domain!r}."

    def _git(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        pl = try_infer_readme_push_chain_nl(message)
        if pl:
            return self._run_host_payload(
                pl,
                chat_id=chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
                domain="git",
                agent=agent,
            )

        low = message.lower()
        if re.search(r"\bgit\s+status\b", low) or low.strip() in {"status", "git status"}:
            safe = _validate_enqueue_payload({"host_action": "git_status"})
            if not safe:
                return "Could not build a git status request."
            return self._run_host_payload(
                safe,
                chat_id=chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
                domain="git",
                agent=agent,
            )

        return (
            "Git sub-agent: try an NL readme + push line (e.g. add README … and push), "
            "or ask for `git status`."
        )

    def _vercel(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        low = message.lower()
        if "list" in low or "projects" in low:
            safe = _validate_enqueue_payload({"host_action": "vercel_projects_list"})
            if not safe:
                return "Could not build Vercel projects list."
            return self._run_host_payload(
                safe,
                chat_id=chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
                domain="vercel",
                agent=agent,
            )
        return (
            "Vercel sub-agent: ask to `list projects` / `list my Vercel projects`. "
            "(Deploy/remove are not routed here yet.)"
        )

    def _test(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        low = message.lower()
        if "pytest" in low or re.search(r"\brun\s+tests?\b", low):
            safe = _validate_enqueue_payload({"host_action": "run_command", "run_name": "pytest"})
            if not safe:
                return "pytest run_command is not available (validation failed)."
            return self._run_host_payload(
                safe,
                chat_id=chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
                domain="test",
                agent=agent,
            )
        return "Test sub-agent: ask to `run pytest` (allowlisted run_command)."

    def _enqueue(
        self,
        safe: dict[str, Any],
        *,
        chat_id: str,
        db: Session,
        user_id: str,
        web_session_id: str,
        domain: str,
        suffix: str = "",
    ) -> str:
        title = title_for_payload(safe)
        job = enqueue_host_job_from_validated_payload(
            db,
            user_id.strip(),
            safe_pl=safe,
            title=title,
            web_session_id=(web_session_id or "default").strip()[:64] or "default",
        )
        logger.info(
            "sub_agent queued host job id=%s domain=%s",
            job.id,
            domain,
            extra={"nexa_event": "sub_agent_queued", "job_id": job.id, "domain": domain},
        )
        base = f"Queued host job #{job.id} — open Jobs to approve and run on the worker."
        return f"{base} {suffix}".strip()

    def _run_host_payload(
        self,
        payload: dict[str, Any],
        *,
        chat_id: str,
        db: Session | None,
        user_id: str,
        web_session_id: str,
        domain: str,
        agent: SubAgent,
    ) -> str:
        safe = _validate_enqueue_payload(payload)
        if not safe:
            return "Host tool payload failed validation (disallowed or incomplete)."

        settings = get_settings()
        if bool(getattr(settings, "nexa_auto_approve_enabled", False)):
            aa_ok, _aa_reason = should_auto_approve(chat_id, domain, agent=agent)
            if aa_ok:
                steps = (
                    len(safe.get("actions") or [])
                    if (safe.get("host_action") or "").strip().lower() == "chain"
                    else 1
                )
                t_exec = time.perf_counter()
                try:
                    text = execute_payload(safe)
                except ValueError as exc:
                    log_agent_event(
                        "auto_approved_execute",
                        agent_id=agent.id,
                        agent_name=agent.name,
                        domain=domain,
                        chat_id=chat_id,
                        user_id=user_id,
                        action=str(safe.get("host_action"))[:200],
                        success=False,
                        error=str(exc)[:2000],
                        duration_ms=(time.perf_counter() - t_exec) * 1000.0,
                    )
                    return str(exc)
                log_agent_event(
                    "auto_approved_execute",
                    agent_id=agent.id,
                    agent_name=agent.name,
                    domain=domain,
                    chat_id=chat_id,
                    user_id=user_id,
                    action=str(safe.get("host_action"))[:200],
                    success=True,
                    duration_ms=(time.perf_counter() - t_exec) * 1000.0,
                    extra={"steps": steps},
                )
                head = get_auto_approve_message(domain, steps)
                body = (text or "").strip()
                return f"{head}\n\n{body}" if body else head

        auto = bool(getattr(settings, "nexa_agent_orchestration_autoqueue", False))

        if auto:
            run_inline, guard_msg, prefer_queue = should_run_autoqueue_payload(chat_id, domain, agent)
            if not run_inline:
                log_agent_event(
                    "autoqueue_redirect_queue",
                    agent_id=agent.id,
                    agent_name=agent.name,
                    domain=domain,
                    chat_id=chat_id,
                    user_id=user_id,
                    success=True,
                    extra={"reason": guard_msg or "guard"},
                )
                if prefer_queue and db is not None and (user_id or "").strip():
                    return self._enqueue(
                        safe,
                        chat_id=chat_id,
                        db=db,
                        user_id=user_id,
                        web_session_id=web_session_id,
                        domain=domain,
                        suffix=guard_msg or "",
                    )
                return (
                    guard_msg
                    or "In-process auto-queue is not allowed. Enable approval queue with a signed-in session."
                )

            log_agent_event(
                "autoqueue_execute",
                agent_id=agent.id,
                agent_name=agent.name,
                domain=domain,
                chat_id=chat_id,
                user_id=user_id,
                success=True,
                autoqueue=True,
                extra={"host_action": safe.get("host_action")},
            )
            try:
                text = execute_payload(safe)
            except ValueError as e:
                log_agent_event(
                    "autoqueue_execute",
                    agent_id=agent.id,
                    agent_name=agent.name,
                    domain=domain,
                    chat_id=chat_id,
                    user_id=user_id,
                    success=False,
                    error=str(e),
                    autoqueue=True,
                )
                return str(e)
            record_autoqueue_success(agent.id)
            return (text or "").strip() or "(empty host output)"

        if db is None or not (user_id or "").strip():
            return "Cannot queue a host job without an authenticated user and database session."

        return self._enqueue(
            safe,
            chat_id=chat_id,
            db=db,
            user_id=user_id,
            web_session_id=web_session_id,
            domain=domain,
        )


__all__ = ["AgentExecutor"]
