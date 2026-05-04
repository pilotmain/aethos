"""
Week 4 Phase 3 — sync execution for orchestration sub-agents (domain dispatch).

``nexa_agent_orchestration_autoqueue``: when true, runs ``execute_payload`` in-process
(loose approval; audit log). When false, enqueues ``host-executor`` jobs (normal approval).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.host_executor import execute_payload
from app.services.host_executor_chat import _validate_enqueue_payload, enqueue_host_job_from_validated_payload
from app.services.host_executor_intent import title_for_payload
from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent

logger = logging.getLogger(__name__)


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

        self.registry.update_status(agent.id, AgentStatus.BUSY)
        try:
            out = self._dispatch(agent, msg, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
            self.registry.touch_agent(agent.id)
            return out
        except Exception as exc:
            logger.exception("sub_agent execute failed agent=%s", agent.id)
            return f"Execution failed: {exc}"
        finally:
            self.registry.update_status(agent.id, AgentStatus.IDLE)

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
        domain = (agent.domain or "").strip().lower()
        if domain == "git":
            return self._git(message, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "vercel":
            return self._vercel(message, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "test":
            return self._test(message, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "railway":
            return (
                "Railway sub-agent is not wired to host execution in this release. "
                "Use the operator / execution loop for Railway, or extend `sub_agent_executor`."
            )
        return f"Unknown sub-agent domain {domain!r}."

    def _git(
        self,
        message: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        pl = try_infer_readme_push_chain_nl(message)
        if pl:
            return self._run_host_payload(pl, db=db, user_id=user_id, web_session_id=web_session_id, domain="git")

        low = message.lower()
        if re.search(r"\bgit\s+status\b", low) or low.strip() in {"status", "git status"}:
            safe = _validate_enqueue_payload({"host_action": "git_status"})
            if not safe:
                return "Could not build a git status request."
            return self._run_host_payload(safe, db=db, user_id=user_id, web_session_id=web_session_id, domain="git")

        return (
            "Git sub-agent: try an NL readme + push line (e.g. add README … and push), "
            "or ask for `git status`."
        )

    def _vercel(
        self,
        message: str,
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
                safe, db=db, user_id=user_id, web_session_id=web_session_id, domain="vercel"
            )
        return (
            "Vercel sub-agent: ask to `list projects` / `list my Vercel projects`. "
            "(Deploy/remove are not routed here yet.)"
        )

    def _test(
        self,
        message: str,
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
            return self._run_host_payload(safe, db=db, user_id=user_id, web_session_id=web_session_id, domain="test")
        return "Test sub-agent: ask to `run pytest` (allowlisted run_command)."

    def _run_host_payload(
        self,
        payload: dict[str, Any],
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
        domain: str,
    ) -> str:
        safe = _validate_enqueue_payload(payload)
        if not safe:
            return "Host tool payload failed validation (disallowed or incomplete)."

        settings = get_settings()
        auto = bool(getattr(settings, "nexa_agent_orchestration_autoqueue", False))

        if auto:
            logger.info(
                "sub_agent autoqueue execute domain=%s user=%s",
                domain,
                (user_id or "")[:64],
                extra={
                    "nexa_event": "sub_agent_autoqueue",
                    "domain": domain,
                    "host_action": safe.get("host_action"),
                    "user_id": user_id,
                },
            )
            try:
                text = execute_payload(safe)
            except ValueError as e:
                return str(e)
            return (text or "").strip() or "(empty host output)"

        if db is None or not (user_id or "").strip():
            return "Cannot queue a host job without an authenticated user and database session."

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
        return f"Queued host job #{job.id} — open Jobs to approve and run on the worker."


__all__ = ["AgentExecutor"]
