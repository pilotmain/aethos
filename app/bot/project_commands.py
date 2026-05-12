# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram — Mission Control projects & tasks (Phase 27).

Commands (BotFather): /goal, /task, /tasks, /assign, /claim, /unclaim, /done, /mission, /mcstatus

Note: ``/project`` is already used for workspace / dev project keys; use /goal for Mission Control.
"""

from __future__ import annotations

import re
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.project import get_project_controller
from app.services.user_capabilities import BLOCKED_MSG, get_telegram_role

_CTRL = get_project_controller


def _scope(update: Update) -> str:
    return str(update.effective_chat.id) if update.effective_chat else "unknown"


def _team_orch_scope(update: Update) -> str:
    """Sub-agent roster scope (matches gateway ``telegram:<chat_id>``)."""
    from app.services.sub_agent_router import telegram_agent_registry_chat_id

    return telegram_agent_registry_chat_id(update.effective_chat.id if update.effective_chat else None)


def _actor_member_id(update: Update) -> str:
    """Synthetic actor id for checkout/done when no roster agent is addressed."""
    uid = update.effective_user.id if update.effective_user else 0
    return f"tg:{uid}"


def _active_organization_id(update: Update) -> str | None:
    """Phase 29 — Mission Control rows tagged with the user's active workspace when RBAC is on."""
    s = get_settings()
    if not getattr(s, "nexa_rbac_enabled", False) or not update.effective_user:
        return None
    from app.services.rbac.organization_service import OrganizationService

    return OrganizationService().get_active_organization_id(str(update.effective_user.id))


async def _gate(update: Update) -> bool:
    if not update.effective_user or not update.message:
        return False
    s = get_settings()
    if not s.nexa_projects_enabled:
        await update.message.reply_text("Mission Control projects are disabled (NEXA_PROJECTS_ENABLED).")
        return False
    db = SessionLocal()
    try:
        if get_telegram_role(update.effective_user.id, db) == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return False
    finally:
        db.close()
    return True


def _find_task_by_title(ctrl: Any, team_scope: str, title: str) -> Any:
    title_l = title.strip().lower()
    for t in ctrl.list_tasks(team_scope=team_scope):
        if t.title.strip().lower() == title_l:
            return t
    return None


# --- /goal (Mission Control project) ---


async def goal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    raw = (update.message.text or "").strip()
    parts = raw.split(maxsplit=1)
    rest = parts[1].strip() if len(parts) > 1 else ""
    chat = _scope(update)
    ctrl = _CTRL()

    if not rest:
        await update.message.reply_text(
            "📋 Mission Control — projects\n\n"
            "/goal \"Your goal\" — create project & set it current\n"
            "/goal list — list projects in this chat\n"
            "/goal use <id> — set current project for /task add\n"
            "/goal status <id> — progress & task counts\n\n"
            "Also: /tasks, /task add \"…\", /assign @Member \"…\", /claim, /done, /mission"
        )
        return

    if rest.lower() in ("list", "ls"):
        oid = _active_organization_id(update)
        projects = ctrl.list_projects(chat, organization_id=oid)
        if not projects:
            await update.message.reply_text("No projects yet. Create: /goal \"Build the thing\"")
            return
        lines = ["📋 Your projects (this chat):", ""]
        for p in projects[:20]:
            lines.append(p.to_user_display())
            lines.append("")
        await update.message.reply_text("\n".join(lines)[:9000])
        return

    if rest.lower().startswith("use "):
        pid = rest[4:].strip()
        if not pid:
            await update.message.reply_text("Usage: /goal use <project_id>")
            return
        if ctrl.set_current_project(chat, pid):
            p = ctrl.get_project(pid)
            await update.message.reply_text(
                f"Current project: {p.name if p else pid} (`{pid}`)\n\nAdd tasks: /task add \"…\""
            )
        else:
            await update.message.reply_text("Unknown id or not in this chat.")
        return

    if rest.lower().startswith("status "):
        pid = rest[7:].strip()
        tree = ctrl.build_mission_tree(pid)
        if tree.get("error"):
            await update.message.reply_text(f"❌ {tree['error']}")
            return
        pr = tree["project"]
        ts = tree["tasks"]
        msg = (
            f"🎯 {pr['name']}\n"
            f"Goal: {pr['goal']}\n"
            f"Progress: {pr['progress']}% ({ts['done']}/{ts['total']} tasks done)\n"
        )
        await update.message.reply_text(msg[:9000])
        return

    # create: quoted string
    if (rest.startswith('"') and rest.endswith('"')) or (rest.startswith("'") and rest.endswith("'")):
        goal = rest[1:-1].strip()
        name = goal[:80]
        p = ctrl.create_project(
            name=name,
            goal=goal,
            team_scope=chat,
            organization_id=_active_organization_id(update),
        )
        await update.message.reply_text(
            f"✅ Project created\n\n🎯 {goal}\n🆔 `{p.id}` (current)\n\n"
            f"Next: /task add \"First task\""
        )
        return

    await update.message.reply_text('Use /goal \"Your goal text\" or /goal list')


# --- /task ---


async def task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    args = list(context.args or [])
    chat = _scope(update)
    ctrl = _CTRL()
    cur = ctrl.get_current_project_id(chat)

    if not args:
        await update.message.reply_text(
            "/task add \"Title\" — add to current project (/goal use …)\n"
            "/task list — tasks for current project or this chat"
        )
        return

    sub = args[0].lower()
    if sub == "add":
        title = " ".join(args[1:]).strip().strip('"').strip("'")
        if not title:
            await update.message.reply_text("Usage: /task add \"Task title\"")
            return
        task = ctrl.add_task(title, project_id=cur, team_scope=chat if not cur else None)
        await update.message.reply_text(
            f"✅ Task added\n📝 {task.title}\n🆔 `{task.id}`\n\nAssign: /assign @Member \"{task.title}\""
        )
        return

    if sub in ("list", "ls"):
        if cur:
            tasks = ctrl.list_tasks(project_id=cur)
        else:
            tasks = ctrl.list_tasks(team_scope=chat)
        if not tasks:
            await update.message.reply_text("No tasks. /task add \"…\" or /goal \"…\" first.")
            return
        lines = ["📋 Tasks:", ""]
        for t in tasks[:25]:
            lines.append(t.to_user_display())
            lines.append("")
        await update.message.reply_text("\n".join(lines)[:9000])
        return

    await update.message.reply_text("Unknown subcommand. Try /task add … or /task list")


# --- /tasks (flat list by chat scope) ---


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    ctrl = _CTRL()
    chat = _scope(update)
    tasks = ctrl.list_tasks(team_scope=chat)
    if not tasks:
        await update.message.reply_text("No tasks in this chat scope.")
        return
    lines = ["📋 All tasks (this chat):", ""]
    for t in tasks[:30]:
        pr = ""
        if t.project_id:
            pr = f" [project `{t.project_id}`]"
        lines.append(t.to_user_display() + pr)
        lines.append("")
    await update.message.reply_text("\n".join(lines)[:9000])


# --- /assign @Member "task title" ---


async def assign_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    raw = update.message.text or ""
    m = re.match(r"/assign\s+@(\S+)\s+\"([^\"]+)\"", raw.strip(), re.I)
    if not m:
        await update.message.reply_text('Usage: /assign @MemberName \"Exact task title\"')
        return
    member_name, task_title = m.group(1), m.group(2)
    chat = _scope(update)
    orch = _team_orch_scope(update)
    ctrl = _CTRL()
    member = ctrl.team_roster.get_member_by_name(member_name, orch)
    if not member:
        await update.message.reply_text(f"No team member @{member_name} in this chat. (/team)")
        return
    task = _find_task_by_title(ctrl, chat, task_title)
    if not task:
        await update.message.reply_text(f"Task not found: {task_title}")
        return
    if ctrl.assign_task(task.id, member.member_id, "telegram"):
        await update.message.reply_text(f"✅ Assigned \"{task.title}\" → @{member_name}")
    else:
        await update.message.reply_text("Could not assign (check orchestration / member).")


# --- /claim / /unclaim ---


async def claim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    raw = (update.message.text or "").strip()
    settings = get_settings()
    chat = _scope(update)
    orch = _team_orch_scope(update)
    ctrl = _CTRL()
    m = re.match(r"/claim\s+(?:@(\S+)\s+)?\"([^\"]+)\"", raw, re.I)
    if not m:
        await update.message.reply_text(
            'Usage: /claim \"Task title\"  OR  /claim @AgentName \"Task title\" '
            "(when orchestration is on, prefer @AgentName)."
        )
        return
    agent_name, title = m.group(1), m.group(2).strip()
    if getattr(settings, "nexa_agent_orchestration_enabled", False):
        if not agent_name:
            await update.message.reply_text(
                "Orchestration is on — claim as a team member:\n"
                '/claim @AgentName "Task title"'
            )
            return
        mem = ctrl.team_roster.get_member_by_name(agent_name, orch)
        if not mem:
            await update.message.reply_text(f"No team member @{agent_name} in this chat.")
            return
        actor = mem.member_id
    else:
        if agent_name:
            mem = ctrl.team_roster.get_member_by_name(agent_name, orch)
            actor = mem.member_id if mem else _actor_member_id(update)
        else:
            actor = _actor_member_id(update)
    task = _find_task_by_title(ctrl, chat, title)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    if ctrl.claim_task(task.id, actor):
        await update.message.reply_text(f"✅ Claimed: {task.title}")
    else:
        await update.message.reply_text("Could not claim (locked, done, or invalid member).")


async def unclaim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    raw = (update.message.text or "").strip()
    settings = get_settings()
    chat = _scope(update)
    orch = _team_orch_scope(update)
    ctrl = _CTRL()
    m = re.match(r"/unclaim\s+(?:@(\S+)\s+)?\"([^\"]+)\"", raw, re.I)
    if not m:
        await update.message.reply_text('Usage: /unclaim \"Task title\"  OR  /unclaim @Agent \"Task title\"')
        return
    agent_name, title = m.group(1), m.group(2).strip()
    if getattr(settings, "nexa_agent_orchestration_enabled", False) and not agent_name:
        await update.message.reply_text('/unclaim @AgentName "Task title" (orchestration is on).')
        return
    if agent_name:
        mem = ctrl.team_roster.get_member_by_name(agent_name, orch)
        actor = mem.member_id if mem else ""
    else:
        actor = _actor_member_id(update)
    if not actor:
        await update.message.reply_text("Unknown member.")
        return
    task = _find_task_by_title(ctrl, chat, title)
    if not task:
        await update.message.reply_text("Task not found.")
        return
    if ctrl.unclaim_task(task.id, actor):
        await update.message.reply_text(f"Released lock on: {task.title}")
    else:
        await update.message.reply_text("Not locked by you.")


# --- /done ---


async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    raw = (update.message.text or "").strip()
    # /done @Member "title" OR /done "title"
    m2 = re.match(r"/done\s+@(\S+)\s+\"([^\"]+)\"", raw, re.I)
    chat = _scope(update)
    orch = _team_orch_scope(update)
    ctrl = _CTRL()
    actor = _actor_member_id(update)

    if m2:
        member_name, task_title = m2.group(1), m2.group(2)
        mem = ctrl.team_roster.get_member_by_name(member_name, orch)
        if not mem:
            await update.message.reply_text(f"No member @{member_name}")
            return
        task = _find_task_by_title(ctrl, chat, task_title)
        if not task:
            await update.message.reply_text("Task not found.")
            return
        mid = mem.member_id
    else:
        parts = raw.split(maxsplit=1)
        title = (parts[1] if len(parts) > 1 else "").strip().strip('"').strip("'")
        if not title:
            await update.message.reply_text('Usage: /done \"Task title\" or /done @Member \"Task title\"')
            return
        task = _find_task_by_title(ctrl, chat, title)
        if not task:
            await update.message.reply_text("Task not found.")
            return
        mid = actor

    if ctrl.complete_task(task.id, mid):
        await update.message.reply_text(f"✅ Done: {task.title}")
    else:
        await update.message.reply_text("Could not complete (assignment / lock rules).")


# --- /mission ---


async def mission_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    args = list(context.args or [])
    chat = _scope(update)
    ctrl = _CTRL()
    pid = args[0] if args else ctrl.get_current_project_id(chat)
    if not pid:
        await update.message.reply_text("No project id. Set current: /goal use <id> or /mission <id>")
        return
    tree = ctrl.build_mission_tree(pid)
    if tree.get("error"):
        await update.message.reply_text(f"❌ {tree['error']}")
        return
    pr = tree["project"]
    ts = tree["tasks"]
    bar_n = max(0, min(10, pr["progress"] // 10))
    bar = "█" * bar_n + "░" * (10 - bar_n)
    msg = (
        f"🎯 Mission: {pr['name']}\n"
        f"Why: {tree['why_this_matters']}\n"
        f"{bar} {pr['progress']}%\n\n"
        f"✅ Done: {ts['done']}  🔄 In progress: {ts['in_progress']}  "
        f"⏳ Pending: {ts['pending']}"
    )
    if ts["blocked"]:
        msg += f"  🚫 Blocked: {ts['blocked']}"
    await update.message.reply_text(msg[:9000])


# --- /mcstatus @Member ---


async def mcstatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update):
        return
    assert update.message
    args = list(context.args or [])
    if len(args) < 1 or not args[0].startswith("@"):
        await update.message.reply_text("Usage: /mcstatus @MemberName")
        return
    name = args[0].lstrip("@")
    orch = _team_orch_scope(update)
    ctrl = _CTRL()
    mem = ctrl.team_roster.get_member_by_name(name, orch)
    if not mem:
        await update.message.reply_text(f"No member @{name} in this chat.")
        return
    tasks = ctrl.list_tasks(assigned_to=mem.member_id)
    cur = mem.current_task or "(none)"
    lines = [
        f"👤 @{mem.display_name}",
        f"Role: {mem.role_title}",
        f"Current task line: {cur}",
        "",
        "Assigned tasks:",
    ]
    if not tasks:
        lines.append("  (none)")
    else:
        for t in tasks[:12]:
            lines.append(f"  • {t.title} — {t.status.value}")
    await update.message.reply_text("\n".join(lines)[:9000])


__all__ = [
    "assign_cmd",
    "claim_cmd",
    "done_cmd",
    "goal_cmd",
    "mcstatus_cmd",
    "mission_cmd",
    "task_cmd",
    "tasks_cmd",
    "unclaim_cmd",
]
