"""
Week 4 Phase 3 + Week 5 hardening — sync sub-agent execution (domain dispatch).

``nexa_agent_orchestration_autoqueue``: when true, may run ``execute_payload`` in-process
subject to :mod:`app.services.sub_agent_autoqueue_guard`. Otherwise enqueues jobs.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.budget.hooks import budget_enabled, estimate_tokens_from_text
from app.services.budget.models import UsageType
from app.services.budget.tracker import BudgetTracker
from app.services.infra_cli import (
    railway_projects as _cli_railway_projects,
    railway_whoami as _cli_railway_whoami,
    vercel_projects_list as _cli_vercel_projects,
    vercel_whoami as _cli_vercel_whoami,
)
from app.services.host_executor import execute_payload
from app.services.host_executor_chat import _validate_enqueue_payload, enqueue_host_job_from_validated_payload
from app.services.host_executor_intent import title_for_payload
from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.fsmonitor import watch
from app.services.infra.railway import get_railway_client
from app.services.infra.vercel import get_vercel_client
from app.services.qa_agent.file_analysis import run_qa_file_analysis
from app.services.telegram_outbound import send_telegram_message
from app.services.sub_agent_audit import log_agent_event
from app.services.sub_agent_auto_approve import get_auto_approve_message, should_auto_approve
from app.services.sub_agent_autoqueue_guard import (
    record_autoqueue_success,
    should_run_autoqueue_payload,
)
from app.services.sub_agent_rate_limit import check_rate_limits, record_rate_limited_action
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent

logger = logging.getLogger(__name__)

_SECURITY_REVIEW_NAMES = frozenset({"security_agent", "security_expert", "sec_agent"})


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

    def _should_run_security_review_sync(self, agent: SubAgent) -> bool:
        """Security scanner path — **not** generic QA/pytest agents (Phase 47)."""
        n = (agent.name or "").strip().lower()
        d = (agent.domain or "").strip().lower()
        if d in ("security", "sec"):
            return True
        if n in _SECURITY_REVIEW_NAMES:
            return True
        return False

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
        if self._should_run_security_review_sync(agent):
            from app.services.qa_agent.security_review import run_security_review_sync

            return run_security_review_sync(agent, message, db=db, user_id=user_id)

        domain = (agent.domain or "").strip().lower()
        if domain in {"ops", "railway"}:
            return self._infra_ops(
                agent,
                message,
                chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
            )
        if domain == "git":
            return self._git(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain == "vercel":
            return self._vercel(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain in {"qa", "test"}:
            return self._qa_or_test(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if domain in {"general", "marketing", "ceo", "support", "scrum", "backend", "frontend"}:
            return (
                f"🤖 **@{agent.name}** ({domain}) is registered for this chat.\n\n"
                "Send a concrete instruction. For tooling runs, use agents with domains "
                "**git**, **vercel**, **railway**, **ops**, **qa**, **test**, or **security**."
            )[:4000]
        return f"Unknown sub-agent domain {domain!r}."

    def _infra_ops(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        """Railway/Vercel-oriented ops (direct CLI when available)."""
        low = (message or "").lower()
        domain = (agent.domain or "").strip().lower()

        if re.search(r"(?i)\bmonitor\s+", message or ""):
            return self._fs_monitor_ack(agent, message, chat_id)

        if "vercel" in low:
            if any(k in low for k in ("whoami", "account", "login")):
                return _cli_vercel_whoami()
            if any(k in low for k in ("list", "project", "ls")):
                return self._vercel(
                    agent,
                    message,
                    chat_id,
                    db=db,
                    user_id=user_id,
                    web_session_id=web_session_id,
                )

        # Railway — keyword or railway-tagged agent domain
        if "railway" in low or domain == "railway":
            if any(k in low for k in ("deploy", "ship", "release", "push live")):
                return self._railway_deploy(message)
            if any(k in low for k in ("whoami", "status", "logged", "account")):
                return _cli_railway_whoami()
            if any(k in low for k in ("project", "list", "apps", "service")):
                return _cli_railway_projects()
            # Short prompts like "status" alone on a railway-domain agent
            if domain == "railway" and any(
                k in low for k in ("status", "health", "check", "who")
            ):
                return _cli_railway_whoami()
            return (
                "🤖 **Railway** — try:\n"
                "- `railway whoami` (login status)\n"
                "- `railway list` (projects)\n"
                "_Requires Railway CLI on the worker (`npm i -g @railway/cli`)._"
            )

        if "vercel" in low:
            return self._vercel(
                agent,
                message,
                chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
            )

        return (
            "🤖 **Ops agent** — mention **railway** (`railway whoami`, `railway list`) "
            "or **vercel** (`vercel projects`, `/vercel projects list`). "
            "Spawn a **vercel**-domain agent for deploy-focused flows."
        )

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
        if any(k in low for k in ("deploy", "ship", "--prod", "production deploy")):
            proj_m = re.search(r"(?i)(?:project|proj)\s+(?:is\s+)?([a-z0-9._-]{1,120})", message or "")
            proj = proj_m.group(1).strip(" `\"'") if proj_m else None
            vc = get_vercel_client()
            r = vc.deploy_prod(project=proj)
            if r.get("success"):
                body = (r.get("output") or "").strip()[:4000]
                return f"✅ **Vercel deploy** (prod)\n\n```\n{body}\n```"
            err = (r.get("error") or r.get("stderr") or "deploy failed")[:2000]
            return f"❌ **Vercel deploy failed**\n\n```\n{err}\n```"
        if any(k in low for k in ("whoami", "account")):
            return _cli_vercel_whoami()
        if any(k in low for k in ("json", "api")) and "project" in low:
            rows = get_vercel_client().list_projects_json()
            if rows:
                names = []
                for row in rows[:40]:
                    if isinstance(row, dict) and row.get("name"):
                        names.append(str(row["name"]))
                    elif isinstance(row, str):
                        names.append(row)
                body = "\n".join(names) if names else str(rows)[:12000]
                return f"📁 **Vercel projects (json)**\n\n```\n{body[:12000]}\n```"
            return _cli_vercel_projects()
        wants_list = any(
            k in low for k in ("list", "project", "projects")
        ) or low.strip() in {"ls", "list"}
        if wants_list:
            if shutil.which("vercel"):
                return _cli_vercel_projects()
            cli_msg = _cli_vercel_projects()
            safe = _validate_enqueue_payload({"host_action": "vercel_projects_list"})
            if not safe:
                return cli_msg
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
            "Vercel sub-agent: ask to **list projects** / **list my Vercel projects**, "
            "**deploy** (prod), or **whoami**. Use `/vercel help` in Telegram for shortcuts."
        )

    def _railway_deploy(self, message: str) -> str:
        kv: dict[str, str] = {}
        for m in re.finditer(r"\b([A-Z][A-Z0-9_]{1,24})=(\S+)", message or ""):
            kv[m.group(1)] = m.group(2).strip("`\"'")
        retry = 3000 if kv.get("PORT") == "8080" else None
        client = get_railway_client()
        res = client.deploy(extra_env=kv or None, retry_alt_port=retry)
        if res.get("success"):
            head = "✅ **Railway deploy** (`railway up`)"
            if res.get("retried"):
                head += f" — retried with PORT={res.get('retry_port')}"
            out = (res.get("output") or "").strip()[:3500]
            return f"{head}\n\n```\n{out}\n```"
        err = (res.get("error") or res.get("stderr") or "unknown error")[:2000]
        return (
            f"❌ **Railway deploy failed**\n\n```\n{err}\n```\n\n"
            "💡 Set **`RAILWAY_TOKEN`** (or `RAILWAY_API_TOKEN`) and optionally **`RAILWAY_PROJECT_ID`** "
            "in `.env`, or run `railway link` on the worker."
        )

    def _fs_monitor_ack(self, agent: SubAgent, message: str, chat_id: str) -> str:
        raw_m = (message or "").strip()
        raw_path: str | None = None
        m = re.search(r"(?is)\bmonitor\s+(.+?)(?:\s+for\s+|$)", raw_m)
        if m:
            raw_path = m.group(1).strip().strip("`\"'")
        if not raw_path:
            m2 = re.search(r"(?i)\bwatch\s+(\S+)", raw_m)
            raw_path = m2.group(1).strip().strip("`\"'") if m2 else None
        if not raw_path:
            return (
                "👀 **Monitor** — specify a directory.\n"
                "Example: `Monitor /Users/you/proj for Python file changes`"
            )
        pattern = "*.py"
        low = (message or "").lower()
        if "javascript" in low or ".js" in low:
            pattern = "*.js"
        if "*" in raw_path:
            pattern = raw_path.split("*")[-1] or pattern

        def _telegram_chat_target(scope: str) -> str | None:
            s = (scope or "").strip()
            if s.lower().startswith("telegram:"):
                tail = s.split(":", 1)[1].strip()
                return tail or None
            if s.lstrip("-").isdigit():
                return s
            return None

        def _on_change(fp: str) -> None:
            logger.info(
                "fsmonitor chat=%s agent=%s path=%s",
                chat_id,
                agent.name,
                fp[:500],
            )
            tid = _telegram_chat_target(chat_id)
            if tid:
                send_telegram_message(
                    tid,
                    f"📝 **File changed**\n`{fp}`\n\nTip: `@qa_agent analyze {fp}`",
                )

        try:
            wid = watch(raw_path, pattern, _on_change, duration_seconds=1800.0)
        except FileNotFoundError:
            return f"❌ Path not found: `{raw_path}`"
        except Exception as exc:
            return f"❌ Could not start watcher: {exc}"
        return (
            f"👀 **Watching** `{raw_path}` (pattern `{pattern}`).\n"
            f"Watcher id: `{wid}` — changes are logged on the worker for ~30 minutes."
        )

    def _qa_or_test(
        self,
        agent: SubAgent,
        message: str,
        chat_id: str,
        *,
        db: Session | None,
        user_id: str,
        web_session_id: str,
    ) -> str:
        low = (message or "").lower()
        dom = (agent.domain or "").strip().lower()
        wants_pytest = "pytest" in low or re.search(r"\brun\s+tests?\b", low)
        if wants_pytest:
            return self._test(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)
        if dom == "qa":
            path_like = bool(re.search(r"/[\w/.-]+\.\w+", message or ""))
            wants_scan = any(
                k in low for k in ("analyze", "review file", "scan file", "lint file", "audit file")
            )
            if wants_scan or path_like:
                return run_qa_file_analysis(message)
        return self._test(agent, message, chat_id, db=db, user_id=user_id, web_session_id=web_session_id)

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
                domain=(agent.domain or "test").strip().lower() or "test",
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
