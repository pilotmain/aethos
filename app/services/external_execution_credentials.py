"""
Secure Railway / hosted credential guidance — chat pastes are not worker env (P0).

Never persist secrets from user text; only record structured hints on ConversationContext.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.services.input_secret_guard import user_message_contains_railway_credential_paste

logger = logging.getLogger(__name__)

_CREDENTIAL_HINT_SUBKEY = "external_credential_hint"


def format_secure_external_credential_setup(service: str, *, repo_root: str | None = None) -> str:
    """
    Instructions for placing tokens in worker `.env` — never echoes user-provided secrets.

    ``repo_root`` overrides the suggested ``cd`` path; otherwise ``NEXA_REPO_ROOT`` / placeholder.
    """
    svc = (service or "railway").strip().lower()
    if svc != "railway":
        return (
            "I detected what looks like a provider credential in chat. For safety I won’t echo or store it here.\n\n"
            "Add secrets only to your worker environment or vault — then restart the API/bot — and retry."
        )

    root = (repo_root or os.environ.get("NEXA_REPO_ROOT") or "").strip()
    cd = f"cd {root}" if root else "cd /path/to/nexa-next"

    return (
        "I detected a Railway token in chat. For safety, I won’t echo or store it here.\n\n"
        "**Chat text does not automatically become this worker’s environment.** "
        "Connected access means the token is on the machine that runs Nexa (for example in `.env`) "
        "and the API/bot process has been restarted.\n\n"
        f"To connect Railway access to this worker, add it locally instead:\n\n"
        f"{cd}\n"
        "nano .env\n\n"
        "Add:\n\n"
        "RAILWAY_TOKEN=your_token_here\n\n"
        "Then restart:\n\n"
        "docker compose restart api bot\n\n"
        "Because this token was pasted into chat, **rotate it in Railway first**, then place the **new** token in `.env`.\n\n"
        "After restart, say:\n\n"
        "**retry external execution**\n\n"
        "I’ll run read-only checks only:\n"
        "- `railway whoami`\n"
        "- `railway status`\n"
        "- `railway logs`\n"
        "- `git status`\n\n"
        "No deploy, push, or file changes will run without approval."
    )


def format_railway_token_not_loaded_retry_reply() -> str:
    """Exact blocker when retry is requested but the worker has no Railway CLI nor env token."""
    return (
        "I tried to start read-only Railway checks, but **`RAILWAY_TOKEN` is not loaded in this worker** "
        "(and the Railway CLI is not available here either).\n\n"
        "Add `RAILWAY_TOKEN` or `RAILWAY_API_TOKEN` to `.env` on the host that runs Nexa, "
        "or install/authenticate the `railway` CLI on that host — then **`docker compose restart api bot`** — and retry."
    )


def _merge_top_level_flow_json(cctx: ConversationContext, fragment: dict[str, Any]) -> None:
    raw = cctx.current_flow_state_json or ""
    try:
        st = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        st = {}
    if not isinstance(st, dict):
        st = {}
    st[_CREDENTIAL_HINT_SUBKEY] = fragment
    cctx.current_flow_state_json = json.dumps(st, ensure_ascii=False)[:20_000]


def record_credential_setup_hint(
    db: Session,
    cctx: ConversationContext,
    *,
    service: str,
) -> None:
    """Persist only non-secret metadata — never token values."""
    _merge_top_level_flow_json(
        cctx,
        {
            "credential_setup_needed": True,
            "service": (service or "railway").strip().lower(),
            "secret_seen_in_chat": True,
        },
    )
    db.add(cctx)
    db.commit()


def maybe_handle_external_credential_chat_turn(
    db: Session | None,
    *,
    user_id: str,
    user_text: str,
) -> dict[str, Any] | None:
    """
    Railway/API secret pasted in chat → secure setup reply (no LLM, no secret storage).

    Returns a gateway payload dict or None.
    """
    raw = (user_text or "").strip()
    if not raw or not user_message_contains_railway_credential_paste(raw):
        return None

    uid = (user_id or "").strip()
    logger.info("external_credential.setup_reply user_id=%s (redacted)", uid or None)

    if db is not None and uid:
        from app.services.conversation_context_service import get_or_create_context

        cctx = get_or_create_context(db, uid)
        record_credential_setup_hint(db, cctx, service="railway")

    return {
        "mode": "chat",
        "text": format_secure_external_credential_setup("railway"),
        "intent": "external_execution_continue",
        "credential_setup": True,
    }


__all__ = [
    "format_railway_token_not_loaded_retry_reply",
    "format_secure_external_credential_setup",
    "maybe_handle_external_credential_chat_turn",
    "record_credential_setup_hint",
]
