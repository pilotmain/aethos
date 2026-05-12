# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Telegram — workspaces (organizations), invites, and team switcher (Phase 29).

Commands: /org …
"""

from __future__ import annotations

import re
import shlex

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.rbac.models import RoleType, slugify_name
from app.services.rbac.organization_service import OrganizationService
from app.services.user_capabilities import BLOCKED_MSG, get_telegram_role

_svc = OrganizationService()


def _tokens_after_command(text: str) -> list[str]:
    t = (text or "").strip()
    m = re.match(r"^/org(?:@\S+)?\s*(.*)$", t, flags=re.IGNORECASE | re.DOTALL)
    rest = (m.group(1) or "").strip() if m else ""
    if not rest:
        return []
    try:
        return shlex.split(rest)
    except ValueError:
        return rest.split()


def _uid(update: Update) -> str:
    return str(update.effective_user.id) if update.effective_user else ""


async def _gate(update: Update) -> bool:
    if not update.effective_user or not update.message:
        return False
    s = get_settings()
    if not getattr(s, "nexa_rbac_enabled", False):
        await update.message.reply_text(
            "Multi-tenant workspaces are disabled. Set NEXA_RBAC_ENABLED=true to enable /org."
        )
        return False
    db = SessionLocal()
    try:
        if get_telegram_role(update.effective_user.id, db) == "blocked":
            await update.message.reply_text(BLOCKED_MSG)
            return False
    finally:
        db.close()
    return True


def _parse_role(name: str) -> RoleType | None:
    n = name.strip().lower()
    mapping = {
        "owner": RoleType.OWNER,
        "admin": RoleType.ADMIN,
        "member": RoleType.MEMBER,
        "viewer": RoleType.VIEWER,
    }
    return mapping.get(n)


async def org_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _gate(update) or not update.message:
        return
    uid = _uid(update)
    display = (
        update.effective_user.full_name
        if update.effective_user and getattr(update.effective_user, "full_name", None)
        else None
    )
    tokens = _tokens_after_command(update.message.text or "")
    if not tokens:
        await update.message.reply_text(
            "🏢 Workspace commands\n\n"
            "/org create \"Company Name\" — new workspace (you become owner)\n"
            "/org list — your workspaces\n"
            "/org switch <slug> — set active workspace\n"
            "/org members — members in active workspace\n"
            "/org invite — create invite code\n"
            "/org join <code> — accept invite\n"
            "/org role <name_or_id> admin|member|viewer — needs manage_members\n"
            "/org remove <name_or_id> — remove member\n"
            "/org team create \"Team name\" — create team in active org\n"
            "/org team list — list teams\n\n"
            "Mission Control projects created while an workspace is active "
            "are tagged with that workspace (when NEXA_RBAC_ENABLED)."
        )
        return

    sub = tokens[0].lower()

    if sub == "create":
        name = " ".join(tokens[1:]).strip()
        if name.startswith(('"', "'")) and name.endswith(('"', "'")):
            name = name[1:-1].strip()
        if not name:
            await update.message.reply_text('Usage: /org create "Company Name"')
            return
        slug_base = slugify_name(name)
        org = _svc.create_organization(name, slug_base, uid)
        await update.message.reply_text(
            f"✅ Workspace created\n\n"
            f"Name: {org.name}\n"
            f"Slug: `{org.slug}`\n\n"
            f"You are the owner. Invite others: `/org invite` then send them `/org join <code>`\n"
            f"Switch anytime: `/org switch {org.slug}`"
        )
        return

    if sub == "list":
        orgs = _svc.list_organizations_for_user(uid)
        if not orgs:
            await update.message.reply_text(
                "You are not in any workspace yet. `/org create \"My team\"`"
            )
            return
        lines = ["🏢 Your workspaces:", ""]
        for org in orgs:
            mem = _svc.get_member(org.id, uid)
            role_l = mem.role.value if mem else "?"
            emoji = {"owner": "👑", "admin": "🛡️", "member": "👤", "viewer": "👁️"}.get(
                role_l, "👤"
            )
            lines.append(f"{emoji} {org.name} — `{org.slug}` ({role_l})")
        active = _svc.get_active_organization_id(uid)
        if active:
            ao = _svc.get_organization(active)
            lines.append("")
            lines.append(f"Active: {ao.name if ao else active} (`{ao.slug if ao else ''}`)")
        await update.message.reply_text("\n".join(lines)[:9000])
        return

    if sub == "switch" and len(tokens) >= 2:
        slug = tokens[1].strip().lower()
        org = _svc.get_organization_by_slug(slug)
        if not org:
            await update.message.reply_text(f"Workspace `{slug}` not found.")
            return
        if not _svc.get_member(org.id, uid):
            await update.message.reply_text("You do not have access to that workspace.")
            return
        _svc.set_active_organization_id(uid, org.id)
        await update.message.reply_text(f"✅ Active workspace: **{org.name}** (`{org.slug}`)")
        return

    if sub == "members":
        oid = _svc.get_active_organization_id(uid)
        if not oid:
            await update.message.reply_text("No active workspace. Use `/org switch <slug>` or `/org list`.")
            return
        members = _svc.list_members(oid)
        lines = ["👥 Workspace members:", ""]
        for m in members:
            emoji = {"owner": "👑", "admin": "🛡️", "member": "👤", "viewer": "👁️"}.get(
                m.role.value, "👤"
            )
            label = m.user_name or m.user_id
            lines.append(f"{emoji} {label} — {m.role.value} (`{m.user_id}`)")
        await update.message.reply_text("\n".join(lines)[:9000])
        return

    if sub == "invite":
        oid = _svc.get_active_organization_id(uid)
        if not oid:
            await update.message.reply_text("Set an active workspace first: `/org switch <slug>`")
            return
        if not _svc.check_permission(oid, uid, "manage_members"):
            await update.message.reply_text("You need manage_members (admin/owner) to invite.")
            return
        role = RoleType.MEMBER
        if len(tokens) >= 2:
            r = _parse_role(tokens[1])
            if r:
                role = r
        inv = _svc.create_invite(oid, uid, role=role)
        if not inv:
            await update.message.reply_text("Could not create invite.")
            return
        await update.message.reply_text(
            f"📩 Invite created (role: **{role.value}**)\n\n"
            f"Code: `{inv.id}`\n"
            f"Others run: `/org join {inv.id}`\n"
            f"Expires: {inv.expires_at.isoformat(timespec='minutes')}"
        )
        return

    if sub == "join" and len(tokens) >= 2:
        code = tokens[1].strip()
        ok = _svc.accept_invite(code, uid, user_name=display)
        if ok:
            await update.message.reply_text("✅ You joined the workspace. `/org list` — `/org switch …`")
            return
        await update.message.reply_text("Invite invalid, expired, or already used.")
        return

    if sub == "role" and len(tokens) >= 3:
        oid = _svc.get_active_organization_id(uid)
        if not oid:
            await update.message.reply_text("No active workspace.")
            return
        if not _svc.check_permission(oid, uid, "manage_members"):
            await update.message.reply_text("Permission denied (manage_members).")
            return
        target = tokens[1].strip()
        new_role = _parse_role(tokens[2])
        if not new_role or new_role == RoleType.OWNER:
            await update.message.reply_text("Usage: /org role <user_id_or_name> admin|member|viewer")
            return
        tid = _resolve_member_user_id(oid, target)
        if not tid:
            await update.message.reply_text("Member not found in this workspace.")
            return
        if not _svc.update_member_role(oid, tid, new_role):
            await update.message.reply_text("Could not update role.")
            return
        await update.message.reply_text(f"✅ Role updated to **{new_role.value}** for `{tid}`")
        return

    if sub == "remove" and len(tokens) >= 2:
        oid = _svc.get_active_organization_id(uid)
        if not oid:
            await update.message.reply_text("No active workspace.")
            return
        if not _svc.check_permission(oid, uid, "manage_members"):
            await update.message.reply_text("Permission denied (manage_members).")
            return
        target = tokens[1].strip()
        tid = _resolve_member_user_id(oid, target)
        if not tid or tid == uid:
            await update.message.reply_text("Cannot remove yourself or unknown member.")
            return
        mem = _svc.get_member(oid, tid)
        if mem and mem.role == RoleType.OWNER:
            await update.message.reply_text("Cannot remove the workspace owner.")
            return
        _svc.remove_member(oid, tid)
        await update.message.reply_text(f"Removed `{tid}` from this workspace.")
        return

    if sub == "team" and len(tokens) >= 2:
        await _org_team_subcommand(update, uid, tokens)
        return

    await update.message.reply_text("Unknown /org command. Try `/org` for help.")


def _resolve_member_user_id(org_id: str, token: str) -> str | None:
    token = token.strip().lstrip("@")
    mem = _svc.get_member(org_id, token)
    if mem:
        return mem.user_id
    for m in _svc.list_members(org_id):
        if m.user_name and m.user_name.strip().lower() == token.lower():
            return m.user_id
    return None


async def _org_team_subcommand(update: Update, uid: str, tokens: list[str]) -> None:
    assert update.message
    sub2 = tokens[1].lower()
    oid = _svc.get_active_organization_id(uid)
    if not oid:
        await update.message.reply_text("No active workspace. `/org switch <slug>`")
        return
    if not _svc.check_permission(oid, uid, "create_project"):
        await update.message.reply_text("Permission denied.")
        return

    if sub2 == "create":
        name = " ".join(tokens[2:]).strip()
        if name.startswith(('"', "'")) and name.endswith(('"', "'")):
            name = name[1:-1].strip()
        if not name:
            await update.message.reply_text('Usage: /org team create "Team name"')
            return
        team = _svc.create_team(oid, name, uid)
        om = _svc.get_member(oid, uid)
        if om:
            _svc.add_team_member(team.id, om.id)
        await update.message.reply_text(f"✅ Team **{team.name}** (`{team.id}`)")
        return

    if sub2 in ("list", "ls"):
        teams = _svc.list_teams(oid)
        if not teams:
            await update.message.reply_text("No teams yet. `/org team create \"Name\"`")
            return
        lines = ["📂 Teams:", ""]
        for tm in teams:
            lines.append(f"• {tm.name} (`{tm.id}`)")
        await update.message.reply_text("\n".join(lines)[:9000])
        return

    await update.message.reply_text("Usage: /org team create … | /org team list")


__all__ = ["org_cmd"]
