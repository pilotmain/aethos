# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Deterministic custom-agent lifecycle routing — must win over folder/host/next-action heuristics.

Keep aligned with product intent: create / list / manage user-defined agents without host_executor.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.custom_agent_parser import is_valid_user_agent_handle
from app.services.multi_agent_routing import is_multi_agent_capability_question

_RE_DESCRIBE = re.compile(r"(?i)^describe\s+@([\w-]{1,64})\s*$")

# Explicit phrasing only — do not match vague "can you create multi agents …" questions.
_RE_EXPLICIT_NAMED_AGENT = re.compile(
    r"(?is)\b(?:create|make|build|set\s*up|add)\s+"
    r"(?:me\s+)?(?:a\s+|an\s+)?(?:custom\s+)?agent\s+"
    r"(?:called|named)\s+[@]?([a-zA-Z0-9_-]{1,40})\b"
)
_RE_ADD_CUSTOM_AGENT_AT = re.compile(r"(?is)\badd\s+(?:a\s+|an\s+)?(?:custom\s+)?agent\s+@([a-zA-Z0-9_-]{1,40})\b")
_RE_SETUP_AGENT_NAMED = re.compile(
    r"(?is)\bsetup\s+(?:a\s+|an\s+)?(?:custom\s+)?agent\s+(?:called|named)\s+[@]?([a-zA-Z0-9_-]{1,40})\b"
)

_VAGUE_CUSTOM_AGENT_TAIL = (
    " Use a real path on disk — not a generic word like “my” or a handle-like name."
)


def reply_for_custom_agent_path_clarification(agent_key: str, lf: Any) -> str:
    """User-facing clarification when a local path is missing (before LLM / host jobs)."""
    from app.services.custom_agents import display_agent_handle

    if getattr(lf, "directory_read_hint", False):
        dh = display_agent_handle(agent_key)
        base = (lf.clarification_message or "").strip()
        return (
            f"{base} For {dh}, provide a **file** path or ask to **analyze folder** for that directory."
        )

    ax = lf.clarification_axis or "neutral"
    dh = display_agent_handle(agent_key)
    if ax == "file":
        base = (
            f"What file should {dh} read? Please provide a full path like "
            f"`/Users/example/lifeos/README.md`."
        )
    elif ax == "folder":
        base = (
            f"Which folder should {dh} read? Please provide the full path, "
            f"for example `/Users/example/lifeos`."
        )
    else:
        base = f"What path should {dh} use? Please provide a full file or folder path."
    if lf.clarification_vague_path:
        base += _VAGUE_CUSTOM_AGENT_TAIL
    return base


def custom_agent_message_blocks_folder_heuristics(text: str) -> bool:
    """
    When True, skip infer_local_file_request + deterministic host infer so phrases like
    'review contracts' do not trigger read_multiple_files / analyze folder.
    """
    t = (text or "").strip()
    if not t:
        return False
    # Invariant: any user message that leads with @mention must not hit folder/host heuristics first.
    if t.lstrip().startswith("@"):
        return True
    tl = t.lower()
    if "custom agent" in tl:
        return True
    if "agent called" in tl or "agent named" in tl:
        return True
    if "personal agent" in tl and any(v in tl for v in ("create", "make", "build", "add", "set up")):
        return True
    if "@" in t and "agent" in tl:
        if any(v in tl for v in ("create", "make", "build", "add", "set up")):
            return True
        if any(v in tl for v in ("update", "disable", "enable", "delete", "remove")):
            return True
        # bare @mention plus manage verbs on same line often agent ops
    if re.search(
        r"(?i)(?:^|\s)(?:create|make|build|add)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:custom\s+)?agent\b",
        t,
    ):
        return True
    if re.search(r"(?i)\b(list|show)\s+(?:my\s+)?(?:custom\s+)?agents?\b", tl):
        return True
    if "what agents do i have" in tl or "show my custom agents" in tl:
        return True
    return False


def is_create_custom_agent_request(text: str) -> bool:
    """Always False (Phase 48): deterministic creation uses orchestration registry only."""
    _ = text
    return False


_RE_LIST = re.compile(
    r"(?i)^(?:list|show)\s+(?:my\s+)?(?:custom\s+)?agents?\s*$|"
    r"^list\s+my\s+agents?\s*$|"
    r"^(?:what\s+agents\s+do\s+i\s+have|show\s+my\s+custom\s+agents)\??\s*$",
)


def is_list_custom_agents_request(text: str) -> bool:
    t = (text or "").strip()
    return bool(_RE_LIST.match(t))


_RE_DISABLE = re.compile(r"(?i)^(disable|turn\s+off)\s+@([\w-]{1,64})\s*$")
_RE_ENABLE = re.compile(r"(?i)^(enable|turn\s+on)\s+@([\w-]{1,64})\s*$")
_RE_DELETE = re.compile(r"(?i)^(delete|remove)\s+(?:agent\s+)?@([\w-]{1,64})\s*$")
_RE_AGENT_MGMT = re.compile(
    r"(?is)^\s*(enable|turn\s+on|disable|turn\s+off|delete|remove)\s+@([\w-]{1,64})\b"
)


def try_deterministic_custom_agent_turn(
    db: Session,
    app_user_id: str,
    user_text: str,
    *,
    telegram_chat_id: int | None = None,
) -> str | None:
    """
    Single entry for Web/Telegram before host/next_action. Returns reply text or None.
    """
    from app.services.custom_agents import (
        can_user_create_custom_agents,
        create_custom_agent_from_prompt,
        format_custom_agent_describe_reply,
        format_unknown_with_custom,
        get_custom_agent,
        normalize_agent_key,
        resolve_disable_enable_delete,
        resolve_update_custom_agent,
        run_custom_user_agent,
    )
    from app.services.mention_control import format_unknown_mention_message, parse_mention

    raw = (user_text or "").strip()
    if not raw:
        return None

    mg = _RE_AGENT_MGMT.match(raw)
    if mg:
        verb = re.sub(r"\s+", " ", (mg.group(1) or "").lower().strip())
        handle = mg.group(2)
        trailing = raw[mg.end() :].strip()
        if verb in ("disable", "turn off"):
            return resolve_disable_enable_delete(db, app_user_id, handle, disable=True)
        if verb in ("enable", "turn on"):
            return resolve_disable_enable_delete(
                db,
                app_user_id,
                handle,
                disable=False,
                append_enable_resend_hint=bool(trailing),
            )
        if verb in ("delete", "remove"):
            return resolve_disable_enable_delete(db, app_user_id, handle, delete=True)

    # Web + shared core: @unknown-handle → custom user agent before host_executor / local_file.
    if raw.lstrip().startswith("@"):
        mr = parse_mention(raw)
        if mr.is_explicit and mr.error:
            raws = (mr.raw_mention or "unknown").strip()
            k = normalize_agent_key(raws)
            uca = get_custom_agent(db, app_user_id, k)
            m_body = (mr.text or "").strip()
            if uca:
                if not uca.is_active:
                    from app.services.custom_agents import display_agent_handle

                    dh = display_agent_handle(k)
                    return f"{dh} is **disabled**. Say **enable {dh}** before using it again."
                if not m_body:
                    return f"Add a message after `@{k}` (your custom agent)."
                from app.services.local_file_intent import infer_local_file_request

                lf_ca = infer_local_file_request(m_body, default_relative_base=".")
                if lf_ca.matched and lf_ca.error_message:
                    return lf_ca.error_message
                if lf_ca.matched and lf_ca.clarification_message:
                    return reply_for_custom_agent_path_clarification(k, lf_ca)
                from app.services.agent_runtime.boss_chat import (
                    is_boss_agent_key,
                    try_boss_runtime_chat_turn,
                )

                if is_boss_agent_key(uca.agent_key):
                    boss_fast = try_boss_runtime_chat_turn(db, app_user_id, m_body)
                    if boss_fast is not None:
                        return boss_fast
                return run_custom_user_agent(db, app_user_id, uca, m_body, source="deterministic_mention")
            return format_unknown_with_custom(
                format_unknown_mention_message(raws),
                db,
                app_user_id,
            )

    md = _RE_DESCRIBE.match(raw)
    if md:
        return format_custom_agent_describe_reply(db, app_user_id, md.group(1))

    if is_list_custom_agents_request(raw):
        from app.bot.unified_agent_commands import format_unified_agents_list_reply

        return format_unified_agents_list_reply(db, app_user_id, telegram_chat_id=telegram_chat_id)

    m = _RE_DISABLE.match(raw)
    if m:
        return resolve_disable_enable_delete(db, app_user_id, m.group(2), disable=True)
    m = _RE_ENABLE.match(raw)
    if m:
        return resolve_disable_enable_delete(
            db, app_user_id, m.group(2), disable=False, append_enable_resend_hint=False
        )
    m = _RE_DELETE.match(raw)
    if m:
        return resolve_disable_enable_delete(db, app_user_id, m.group(2), delete=True)

    if re.match(r"(?i)^update\s+@", raw):
        ok, err = can_user_create_custom_agents(db, app_user_id)
        if not ok:
            return err
        return resolve_update_custom_agent(db, app_user_id, raw)

    if is_create_custom_agent_request(raw):
        ok, err = can_user_create_custom_agents(db, app_user_id)
        if not ok:
            return err
        return create_custom_agent_from_prompt(db, user_id=app_user_id, prompt=raw)
    return None
