"""Multi-user capability modes for the Nexa Telegram bot (env + DB bootstrap; no PII in replies)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.telegram_link import TelegramLink

logger = logging.getLogger(__name__)

ACCESS_RESTRICTED = (
    "This command is restricted.\n\n"
    "You can still chat with Nexa in plain language — ask what you’re trying to do or describe the outcome you want.\n"
    "If you need Dev, Ops, or project admin, ask the bot owner to grant access."
)

DEV_EXECUTION_RESTRICTED = "Development execution is restricted on this Nexa instance."

OPS_EXECUTION_RESTRICTED = "Ops execution is restricted on this Nexa instance."

GUEST_PROJECTS = (
    "Projects on this instance are not shown publicly. Ask the bot owner for access to Dev or project details."
)

BLOCKED_MSG = "This Nexa instance is not available for your account."


def parse_telegram_id_list(env_value: str | None) -> set[int]:
    out: set[int] = set()
    if not (env_value or "").strip():
        return out
    for part in re.split(r"[\s,]+", (env_value or "").strip()):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(int(p))
        except ValueError:
            continue
    return out


def owner_id_set() -> set[int]:
    return parse_telegram_id_list(os.environ.get("TELEGRAM_OWNER_IDS", ""))


def trusted_id_set() -> set[int]:
    return parse_telegram_id_list(os.environ.get("TELEGRAM_TRUSTED_USER_IDS", ""))


def blocked_id_set() -> set[int]:
    return parse_telegram_id_list(os.environ.get("TELEGRAM_BLOCKED_USER_IDS", ""))


def is_owner_ids_configured() -> bool:
    return bool((os.environ.get("TELEGRAM_OWNER_IDS") or "").strip())


def get_bootstrap_telegram_user_id(db: Session) -> int | None:
    row = db.scalars(
        select(TelegramLink).order_by(TelegramLink.created_at.asc()).limit(1)
    ).first()
    if row is None:
        return None
    return int(row.telegram_user_id)


def get_telegram_role(telegram_user_id: int, db: Session) -> str:
    """
    One of: owner, trusted, guest, blocked
    * TELEGRAM_OWNER_IDS: explicit owner list (highest).
    * If that env is **empty** (typical local dev), the first linked user (min created_at) is owner; others are guests.
    * TELEGRAM_TRUSTED_USER_IDS: trusted; cannot override owner list.
    """
    tid = int(telegram_user_id)
    if tid in blocked_id_set():
        return "blocked"
    oset = owner_id_set()
    tset = trusted_id_set()
    if oset:
        if tid in oset:
            return "owner"
        if tid in tset:
            return "trusted"
        return "guest"
    # No explicit owners: bootstrap the first user who linked (local dev)
    boot = get_bootstrap_telegram_user_id(db)
    if boot is not None and tid == boot:
        return "owner"
    if tid in tset:
        return "trusted"
    return "guest"


def is_owner_role(role: str) -> bool:
    return (role or "").strip() == "owner"


def is_trusted_or_owner(role: str) -> bool:
    return (role or "").strip() in ("owner", "trusted")


def get_telegram_role_for_app_user(db: Session, app_user_id: str) -> str:
    """Telegram-linked id → role; other app_user_ids (e.g. web) are not owner here."""
    from app.services.app_user_id_parse import parse_telegram_id_from_app_user_id

    tid = parse_telegram_id_from_app_user_id((app_user_id or "").strip())
    if tid is not None:
        return get_telegram_role(tid, db)
    return "guest"


def is_privileged_owner_for_web_mutations(db: Session, app_user_id: str) -> bool:
    """
    Owner gate for Mission Control mutating APIs that historically required a Telegram
    ``tg_*`` id with bootstrap / ``TELEGRAM_OWNER_IDS`` owner role.

    Also grants access when enterprise governance marks the user as owner/admin
    (``users.governance_role``) or assigns org owner/admin on an enabled membership row,
    matching admin surfaces in :mod:`app.api.routes.governance_api`.
    """
    if is_owner_role(get_telegram_role_for_app_user(db, app_user_id)):
        return True
    uid = (app_user_id or "").strip()[:64]
    if not uid:
        return False

    from app.models.governance import OrganizationMembership
    from app.models.user import User
    from app.services.governance.service import ROLE_ADMIN, ROLE_OWNER

    u = db.get(User, uid)
    if u is not None:
        gr = str(u.governance_role or "").strip().lower()
        if gr in ("owner", "admin"):
            return True

    m = db.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == uid,
            OrganizationMembership.enabled.is_(True),
            OrganizationMembership.role.in_((ROLE_OWNER, ROLE_ADMIN)),
        ).limit(1)
    )
    return m is not None


def require_personal_workspace_mutation_allowed(db: Session, app_user_id: str) -> None:
    """
    Who may add workspace roots and Nexa workspace projects (labeled folders).

    - Non-Telegram-shaped app user ids (``web_*``, ``local_*``, email, etc.) are treated as
      the sole operator of that id and may manage their own rows.
    - Telegram-linked ``tg_*`` users need **owner** or **trusted** (guest cannot register paths).
    """
    from fastapi import HTTPException, status

    from app.services.app_user_id_parse import parse_telegram_id_from_app_user_id

    uid = (app_user_id or "").strip()
    if not parse_telegram_id_from_app_user_id(uid):
        return
    role = get_telegram_role_for_app_user(db, uid)
    if is_trusted_or_owner(role):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This action requires owner or trusted role for Telegram-linked accounts.",
    )


# --- high-level permissions ---

def can_run_dev_agent_jobs(role: str) -> bool:
    return is_owner_role(role)


def can_approve_reject_jobs(role: str) -> bool:
    return is_owner_role(role)


def can_use_dev_doctor_or_git(role: str) -> bool:
    return is_owner_role(role)


def can_read_dev_stack_commands(role: str) -> bool:
    """ /dev health, status, tools, queue (not admin-only) """
    return is_trusted_or_owner(role)


def can_write_global_memory_file(role: str) -> bool:
    return is_owner_role(role)


def can_use_ops_write_actions(role: str) -> bool:
    return is_owner_role(role)


def can_use_ops_mention_at_all(role: str) -> bool:
    return is_trusted_or_owner(role)


def can_see_repo_paths_in_projects(role: str) -> bool:
    return is_owner_role(role)


def can_view_projects_list(role: str) -> bool:
    return is_trusted_or_owner(role)


def can_project_admin(role: str) -> bool:
    return is_owner_role(role)


def can_list_dev_jobs_commands(role: str) -> bool:
    return is_trusted_or_owner(role)


def can_memory_working_remember_forget(role: str) -> bool:
    return is_trusted_or_owner(role)


@dataclass
class AccessContext:
    telegram_id: int
    role: str
    app_user_id: str | None
    username: str | None


def make_access(
    db: Session, telegram_id: int, app_user_id: str | None, username: str | None
) -> AccessContext:
    return AccessContext(
        telegram_id=telegram_id,
        role=get_telegram_role(telegram_id, db),
        app_user_id=app_user_id,
        username=username,
    )


def format_access_command_text(role: str) -> str:
    """Plain text for /access (no code fences)."""
    r = (role or "guest").strip()
    lines: list[str] = ["Nexa access", "", f"You are: {r}", "", "Capabilities:"]
    if r == "owner":
        lines += [
            "• Chat: enabled",
            "• Development tasks (run & host work): enabled",
            "• Ops: enabled",
            "• Memory (global file write): enabled",
            "• Project admin: enabled",
        ]
    elif r == "trusted":
        lines += [
            "• Chat: enabled",
            "• Reset / planning: enabled",
            "• Read-only dev stack (e.g. /dev health, /dev status) where allowed: enabled",
            "• Development task runs: disabled by default (owner runs host execution)",
            "• Ops: read-only (status, logs) where allowlisted — no deploy/restart",
            "• Project admin: disabled; summary views only (no host paths to others)",
        ]
    elif r == "blocked":
        lines += [
            "• This account is blocked for this instance.",
        ]
    else:  # guest
        lines += [
            "• Chat: enabled",
            "• Reset / planning: enabled (say “reset” or ask Nexa for slash-command help)",
            "• Development tasks: disabled",
            "• Ops: disabled",
            "• Project lists with host details: not shown (ask the owner to grant access)",
        ]
    return "\n".join(lines)[:5000]


def access_section_for_doctor(telegram_id: int, db: Session) -> str:
    r = get_telegram_role(telegram_id, db)
    ocfg = "yes" if is_owner_ids_configured() else "no (bootstrap: first /start = owner; others guest until you set the env var)"
    return "\n".join(
        [
            "",
            "**Access**",
            f"• `TELEGRAM_OWNER_IDS` configured: {ocfg}",
            f"• current user role: {r}",
            "• risky command checks: yes (Nexa capability mode)",
        ]
    )[:2000]
