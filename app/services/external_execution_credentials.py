"""
Secure Railway / hosted credential guidance — chat pastes are not worker env (P0).

Optional in-process session reuse (``nexa_operator_session_credential_reuse``) holds pasted tokens in
RAM for allowlisted CLI subprocess env only — never logs values, never echoes them.

Structured hints on ConversationContext remain non-secret metadata only.
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

_TOKEN_EXTRACT_PATTERNS = (
    re.compile(r"(?i)\b(?:RAILWAY_TOKEN|RAILWAY_API_TOKEN)\s*=\s*([^\s\r\n]+)"),
    re.compile(r"(?i)\brailway\s+(?:api\s*)?(?:token|key)\s*=\s*([^\s\r\n]+)"),
)


def extract_railway_token_from_user_text(text: str) -> str | None:
    """Parse a Railway token value from user text — never log the return value."""
    raw = (text or "").strip()
    if not raw or len(raw) > 50_000:
        return None
    for pat in _TOKEN_EXTRACT_PATTERNS:
        m = pat.search(raw)
        if not m:
            continue
        val = (m.group(1) or "").strip().strip("\"'")
        if 8 <= len(val) <= 4096:
            return val
    return None


def format_secure_external_credential_setup(service: str, *, repo_root: str | None = None) -> str:
    """
    Instructions for placing tokens in worker `.env` — never echoes user-provided secrets.

    ``repo_root`` overrides the suggested ``cd`` path; otherwise ``NEXA_REPO_ROOT`` / placeholder.
    """
    svc = (service or "railway").strip().lower()
    try:
        from app.core.config import get_settings

        s = get_settings()
        zn = bool(getattr(s, "nexa_operator_mode", False)) and bool(getattr(s, "nexa_operator_zero_nag", True))
        reuse = bool(getattr(s, "nexa_operator_session_credential_reuse", True))
    except Exception:  # noqa: BLE001
        zn = False
        reuse = False
    if zn and reuse and svc == "railway":
        return (
            "**Key received** — stored in this API process for your session only (never echoed). "
            "Running bounded checks next…"
        )
    if zn and svc == "railway":
        return (
            "**Key received.** Proceeding with the next steps on this worker.\n\n"
            "I won’t echo or store that value in chat. Add the **new** token only to this host’s `.env` as "
            "`RAILWAY_TOKEN=…`, restart the API/bot stack, then send **retry external execution** for live CLI output."
        )
    if svc != "railway":
        return (
            "I detected what looks like a provider credential in chat. For safety I won’t echo or store it here.\n\n"
            "Add secrets only to your worker environment or vault — then restart the API/bot — and retry."
        )

    root = (repo_root or os.environ.get("NEXA_REPO_ROOT") or "").strip()
    cd = f"cd {root}" if root else "cd /path/to/nexa-next"

    return (
        "**Key received** — I won’t echo or store it in chat.\n\n"
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
    Railway/API secret pasted in chat → secure setup reply (no LLM).

    May store token in RAM when ``nexa_operator_session_credential_reuse`` is enabled (never logged).
    Returns a gateway payload dict or None.
    """
    raw = (user_text or "").strip()
    if not raw or not user_message_contains_railway_credential_paste(raw):
        return None

    uid = (user_id or "").strip()
    try:
        from app.core.config import get_settings

        reuse_enabled = bool(getattr(get_settings(), "nexa_operator_session_credential_reuse", True))
        operator_on = bool(getattr(get_settings(), "nexa_operator_mode", False))
    except Exception:  # noqa: BLE001
        reuse_enabled = False
        operator_on = False

    extracted = extract_railway_token_from_user_text(raw)
    stored = False
    if reuse_enabled and uid and extracted:
        from app.services.credential_session_store import credential_session_store

        credential_session_store.store(uid, "railway", "railway_token", extracted)
        stored = True
    logger.info(
        "external_credential.setup_reply user_id=%s stored_session=%s (redacted)",
        uid or None,
        stored,
    )

    from app.services.credential_session_store import mark_credential_guidance_shown, was_credential_guidance_recent

    _tag = "railway_token_paste"
    if uid and was_credential_guidance_recent(uid, _tag):
        return {
            "mode": "chat",
            "text": (
                "**Key received** (same session) — still won’t echo it. "
                "If that was a real token, rotate it in Railway and keep the new value only in the worker `.env`, "
                "then restart the API/bot. Send **retry external execution** when ready."
            ),
            "intent": "external_execution_continue",
            "credential_setup": True,
        }

    if db is not None and uid:
        from app.services.conversation_context_service import get_or_create_context

        cctx = get_or_create_context(db, uid)
        record_credential_setup_hint(db, cctx, service="railway")

    if uid:
        mark_credential_guidance_shown(uid, _tag)

    out: dict[str, Any] = {
        "mode": "chat",
        "text": format_secure_external_credential_setup("railway"),
        "intent": "external_execution_continue",
        "credential_setup": True,
    }
    if stored and reuse_enabled and operator_on:
        out["chain_bounded_runner_after_store"] = True
    return out


__all__ = [
    "extract_railway_token_from_user_text",
    "format_railway_token_not_loaded_retry_reply",
    "format_secure_external_credential_setup",
    "maybe_handle_external_credential_chat_turn",
    "record_credential_setup_hint",
]
