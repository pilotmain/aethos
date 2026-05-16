# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram commands for orchestration sub-agents (Phase 37).

Uses /subagent to avoid clashing with /agents (LLM catalog) and /agent (custom agents).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from app.core.db import SessionLocal
from app.services.agent.activity_tracker import get_activity_tracker
from app.core.config import get_settings
from app.services.sub_agent_registry import AgentRegistry, AgentStatus
from app.services.sub_agent_router import telegram_agent_registry_chat_id
from app.services.telegram_service import TelegramService

telegram_service = TelegramService()


def _user_web_registry_scope(app_user_id: str) -> str:
    """Same ``parent_chat_id`` as :func:`~app.api.routes.agent_spawn._web_chat_scope` (API / Mission Control)."""
    uid = (app_user_id or "").strip()[:128]
    return f"web:{uid}:default"


def telegram_subagent_scopes(telegram_chat_id: int, app_user_id: str) -> list[str]:
    """In-chat registry scope plus the user's web scope so API-created agents are visible in Telegram."""
    scopes: list[str] = [telegram_agent_registry_chat_id(telegram_chat_id)]
    uid = (app_user_id or "").strip()
    if uid:
        web_scope = _user_web_registry_scope(uid)
        if web_scope not in scopes:
            scopes.append(web_scope)
        # Phase 61 — match API / Mission Control: registry rows may use bare tg_<digits>
        if uid.startswith("tg_") and uid not in scopes:
            scopes.append(uid)
    return scopes


def _api_x_user_id_header(app_user_id: str) -> str:
    """Canonical ``tg_…`` / ``web_…`` id for ``X-User-Id`` (API validation)."""
    raw = (app_user_id or "").strip()
    if not raw:
        return raw
    try:
        from app.services.web_user_id import validate_web_user_id

        return validate_web_user_id(raw)
    except ValueError:
        return raw


def _candidate_api_list_urls() -> list[str]:
    """
    Try primary ``API_BASE_URL`` plus a loopback alias (``localhost`` ↔ ``127.0.0.1``) for the same port.

    Many "API list unavailable" cases are DNS/IPv6 quirks; a second URL often succeeds with no config change.
    """
    s = get_settings()
    primary = (s.api_base_url or "http://127.0.0.1:8010").strip().rstrip("/")
    prefix = (s.api_v1_prefix or "/api/v1").rstrip("/")
    path = f"{prefix}/agents/list"
    bases: list[str] = []
    seen: set[str] = set()

    def add_base(b: str) -> None:
        b = b.strip().rstrip("/")
        if b and b not in seen:
            seen.add(b)
            bases.append(b)

    add_base(primary)
    try:
        p = urlparse(primary)
        if p.scheme and p.hostname and p.hostname.lower() in ("localhost", "127.0.0.1"):
            alt = "127.0.0.1" if p.hostname.lower() == "localhost" else "localhost"
            port = f":{p.port}" if p.port else ""
            netloc = f"{alt}{port}"
            add_base(urlunparse((p.scheme, netloc, p.path or "", p.params, p.query, p.fragment)).rstrip("/"))
    except Exception:
        pass

    return [f"{b}{path}" for b in bases]


async def _fetch_agents_list_via_api(app_user_id: str) -> tuple[bool, list[dict[str, Any]] | None, str | None]:
    """
    GET ``…/agents/list`` — same roster as Mission Control (``X-User-Id`` must pass API validation).

    Returns ``(ok, agents, error_hint)``. Tries each candidate base URL until one succeeds.
    """
    uid_hdr = _api_x_user_id_header(app_user_id)
    headers: dict[str, str] = {"X-User-Id": uid_hdr}
    tok = (get_settings().nexa_web_api_token or "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"

    errs: list[str] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for url in _candidate_api_list_urls():
            try:
                r = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                errs.append(f"{url}: {exc!s}")
                continue
            if r.status_code != 200:
                snippet = (r.text or "")[:160].replace("\n", " ")
                errs.append(f"{url}: HTTP {r.status_code} {snippet}".strip())
                continue
            try:
                data = r.json()
            except ValueError:
                errs.append(f"{url}: invalid JSON")
                continue
            agents = data.get("agents")
            if not isinstance(agents, list):
                errs.append(f"{url}: bad response shape")
                continue
            return True, agents, None

    if not errs:
        hint = "no candidate URL"
    elif len(errs) == 1:
        hint = errs[0]
    else:
        hint = "; ".join(errs[:3]) + ("…" if len(errs) > 3 else "")
    return False, None, hint


async def agent_diagnostic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Phase 64 — show API vs registry counts for debugging /subagent list."""
    if not update.effective_user or not update.message:
        return

    db = SessionLocal()
    try:
        try:
            from app.services.channel_gateway.telegram_adapter import get_telegram_adapter
            app_user_id = get_telegram_adapter().resolve_app_user_id(db, update)
        except Exception:
            app_user_id = None
        orchestrator.users.get_or_create(db, app_user_id)
        class _Link: app_user_id = app_user_id
        link = _Link()

        s = get_settings()
        chat_id = update.effective_chat.id if update.effective_chat else 0
        scopes = telegram_subagent_scopes(chat_id, link.app_user_id)
        registry = AgentRegistry()
        local_n = (
            len(registry.list_agents_for_app_user(link.app_user_id))
            if link.app_user_id
            else len(registry.list_agents_merged(scopes))
        )

        urls = _candidate_api_list_urls()
        ok, agents, err = await _fetch_agents_list_via_api(link.app_user_id)

        lines = [
            "Agent diagnostic (Phase 64)",
            "",
            f"link.app_user_id: {link.app_user_id}",
            f"X-User-Id (validated): {_api_x_user_id_header(link.app_user_id)}",
            f"API_BASE_URL: {s.api_base_url}",
            f"Candidate GET URLs: {len(urls)}",
            "",
        ]
        for u in urls[:4]:
            lines.append(f"  • {u}")
        lines.append("")

        if ok and agents is not None:
            lines.append(f"API GET /agents/list: OK — {len(agents)} agent(s)")
        else:
            lines.append(f"API GET /agents/list: FAIL")
            if err:
                lines.append(f"  {err[:1500]}")

        lines.append("")
        lines.append(f"Local registry (merged scopes): {local_n} agent(s)")
        lines.append("")
        lines.append("If API fails, set API_BASE_URL to the URL curl can reach from this host.")
        await update.message.reply_text("\n".join(lines)[:9000])
    finally:
        db.close()


async def subagent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch: list | delete | pause | resume | status <name> [confirm]."""
    if not update.effective_user or not update.message or not update.effective_chat:
        return

    args = list(context.args or [])
    db = SessionLocal()
    try:
        try:
            from app.services.channel_gateway.telegram_adapter import get_telegram_adapter
            app_user_id = get_telegram_adapter().resolve_app_user_id(db, update)
        except Exception:
            app_user_id = None
        orchestrator.users.get_or_create(db, app_user_id)
        class _Link: app_user_id = app_user_id
        link = _Link()

        scopes = telegram_subagent_scopes(update.effective_chat.id, link.app_user_id)
        registry = AgentRegistry()
        tracker = get_activity_tracker()

        if not args or args[0].lower() in ("help", "-h", "--help"):
            await update.message.reply_text(
                "Orchestration agents (sub-agents)\n\n"
                "• /subagent list — roster + success rate\n"
                "• /subagent create <name> <domain> — spawn in this chat (Telegram scope)\n"
                "• /subagent show <name> — runtime truth (tasks, outputs)\n"
                "• /subagent tasks <name> — assigned tasks\n"
                "• /subagent results <name> — latest result\n"
                "• /subagent status <name> — details\n"
                "• /subagent pause <name>\n"
                "• /subagent resume <name>\n"
                "• /subagent delete <name> confirm — remove permanently\n\n"
                "Domains include **qa**, **marketing**, **git**, **vercel**, **railway**, **ops**, **test**, **security**, **general**.\n\n"
                "Includes agents created via the API / Mission Control (same account).\n"
                "Also: /agent_status (quick list), /agent_diagnostic (API vs registry)."
            )
            return

        sub = args[0].lower()

        if sub == "create":
            if len(args) < 3:
                await update.message.reply_text("Usage: /subagent create <name> <domain>")
                return
            settings = get_settings()
            if not bool(getattr(settings, "nexa_agent_orchestration_enabled", False)):
                await update.message.reply_text(
                    "Sub-agent orchestration is off. Set NEXA_AGENT_ORCHESTRATION_ENABLED=true."
                )
                return
            name_new = args[1].strip().lstrip("@")
            domain_new = args[2].strip().lower()
            if not name_new or not domain_new:
                await update.message.reply_text("Name and domain are required.")
                return
            if registry.get_agent_by_name_for_app_user(name_new, link.app_user_id):
                await update.message.reply_text(
                    f"An orchestration agent named @{name_new} already exists in this chat or your workspace."
                )
                return
            tscope = telegram_agent_registry_chat_id(update.effective_chat.id)
            trusted = bool(getattr(settings, "nexa_agent_auto_approve", False))
            spawned = registry.spawn_agent(
                name_new,
                domain_new,
                tscope,
                trusted=trusted,
                owner_app_user_id=link.app_user_id,
            )
            if not spawned:
                await update.message.reply_text(
                    "Could not create agent (limit reached, duplicate, or orchestration blocked)."
                )
                return
            get_activity_tracker().log_action(
                agent_id=spawned.id,
                agent_name=spawned.name,
                action_type="created",
                metadata={"via": "telegram_subagent_create", "parent_chat_id": tscope},
            )
            await update.message.reply_text(
                f"✅ @{spawned.name} created ({spawned.domain}). Scope: this Telegram chat."
            )
            return

        if sub == "list":
            ok, api_agents, api_err = await _fetch_agents_list_via_api(link.app_user_id)
            emoji = {
                "idle": "🟢",
                "busy": "🟡",
                "paused": "⏸️",
                "error": "🔴",
                "terminated": "⚫",
            }

            if ok and api_agents is not None:
                if not api_agents:
                    await update.message.reply_text(
                        "No orchestration agents yet. "
                        "Enable NEXA_AGENT_ORCHESTRATION_ENABLED and create agents from Mission Control or /subagent create."
                    )
                    return
                lines = ["Orchestration agents (same as Mission Control / API)", ""]
                for row in api_agents:
                    name = str(row.get("name") or "?").strip()
                    domain = str(row.get("domain") or "—").strip()
                    st = str(row.get("status") or "idle").lower()
                    em = emoji.get(st, "⚪")
                    sr = float(row.get("success_rate", 100.0) or 100.0)
                    ta = int(row.get("total_actions", 0) or 0)
                    lines.append(f"{em} @{name} ({domain})")
                    lines.append(f"   Success: {sr:.0f}%  ·  actions: {ta}")
                    lines.append("")
                lines.append("Delete: /subagent delete <name> confirm")
                await update.message.reply_text("\n".join(lines).strip()[:9000])
                return

            agents = (
                registry.list_agents_for_app_user(link.app_user_id)
                if link.app_user_id
                else registry.list_agents_merged(scopes)
            )
            header = (
                f"(API list unavailable{f': {api_err}' if api_err else ''}; showing local registry.)\n\n"
                if not ok
                else ""
            )
            if not agents:
                await update.message.reply_text(
                    header
                    + "No orchestration agents in this chat yet. "
                    "Enable NEXA_AGENT_ORCHESTRATION_ENABLED and spawn from Mission Control or the API. "
                    "If the API runs elsewhere, set API_BASE_URL in .env to the reachable base URL."
                )
                return
            if not header:
                lines: list[str] = ["Orchestration agents (local registry)", ""]
            else:
                lines = [header.rstrip(), "", "Orchestration agents (local registry)", ""]
            for agent in agents:
                stats = tracker.get_agent_statistics(agent.id)
                em = emoji.get(agent.status.value, "⚪")
                lines.append(f"{em} @{agent.name} ({agent.domain})")
                lines.append(f"   Success: {stats.get('success_rate', 100):.0f}%  ·  actions: {stats.get('total_actions', 0)}")
                lines.append("")
            lines.append("Delete: /subagent delete <name> confirm")
            await update.message.reply_text("\n".join(lines).strip()[:9000])
            return

        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /subagent <list|create|show|tasks|results|status|pause|resume|delete> … "
                "(create needs name + domain)"
            )
            return

        name = args[1].strip().lstrip("@")
        agent = (
            registry.get_agent_by_name_for_app_user(name, link.app_user_id)
            if link.app_user_id
            else registry.get_agent_by_name_in_scopes(name, scopes)
        )
        if not agent:
            await update.message.reply_text(
                f"No orchestration agent named '{name}' for this chat/account "
                f"(checked Telegram scope and your API/Mission Control workspace)."
            )
            return

        if sub in ("show", "results"):
            from app.runtime.agent_work_state import find_runtime_agent_by_registry_id
            from app.services.agent_runtime_truth import format_agent_status_reply

            rt = find_runtime_agent_by_registry_id(agent.id)
            reply = format_agent_status_reply(agent.name, sub=agent, runtime=rt)
            await update.message.reply_text(reply[:9000])
            return

        if sub == "tasks":
            from app.runtime.agent_work_state import find_runtime_agent_by_registry_id, list_tasks_for_agent

            rt = find_runtime_agent_by_registry_id(agent.id)
            aid = str((rt or {}).get("agent_id") or "")
            tasks = list_tasks_for_agent(aid) if aid else []
            if not tasks:
                await update.message.reply_text(f"@{agent.name} has no tracked tasks yet.")
                return
            lines = [f"Tasks for @{agent.name}:", ""]
            for t in tasks:
                lines.append(f"• {t.get('task_id')} — {t.get('state')} — {(t.get('prompt') or '')[:120]}")
            await update.message.reply_text("\n".join(lines)[:9000])
            return

        if sub == "status":
            stats = tracker.get_agent_statistics(agent.id)
            md = dict(agent.metadata or {})
            task = md.get("current_task")
            caps = list(agent.capabilities or [])[:12]
            cap_s = ", ".join(caps) if caps else "—"
            lines = [
                f"@{agent.name} ({agent.domain})",
                f"Status: {agent.status.value}",
                f"Trusted (auto-approve path): {bool(agent.trusted)}",
                f"Success rate (30d): {stats.get('success_rate', 100):.1f}%",
                f"Actions (30d): {stats.get('total_actions', 0)}",
                f"Skills: {cap_s}",
            ]
            if task:
                lines.append(f"Current task: {task[:500]}")
            await update.message.reply_text("\n".join(lines)[:9000])
            return

        if sub == "pause":
            registry.patch_agent(agent.id, status=AgentStatus.PAUSED)
            tracker.log_action(agent_id=agent.id, agent_name=agent.name, action_type="paused")
            await update.message.reply_text(f"⏸️ @{agent.name} paused.")
            return

        if sub == "resume":
            if agent.status == AgentStatus.TERMINATED:
                await update.message.reply_text("Cannot resume a terminated agent.")
                return
            registry.patch_agent(agent.id, status=AgentStatus.IDLE)
            tracker.log_action(agent_id=agent.id, agent_name=agent.name, action_type="resumed")
            await update.message.reply_text(f"▶️ @{agent.name} resumed (idle).")
            return

        if sub == "delete":
            if len(args) < 3 or args[2].lower() != "confirm":
                await update.message.reply_text(
                    f"⚠️ To permanently delete @{name}, run:\n"
                    f"/subagent delete {name} confirm"
                )
                return
            tracker.log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="deleted",
                metadata={"via": "telegram", "scopes": scopes, "parent_chat_id": agent.parent_chat_id},
            )
            if registry.remove_agent(agent.id):
                await update.message.reply_text(f"✅ Agent @{name} removed.")
            else:
                await update.message.reply_text("Could not remove agent (already gone).")
            return

        await update.message.reply_text("Unknown subcommand. Try /subagent help.")
    finally:
        db.close()


__all__ = ["agent_diagnostic_command", "subagent_command", "telegram_subagent_scopes"]
