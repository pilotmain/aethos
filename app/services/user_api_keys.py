"""
Store and load per-telegram-user API keys (BYOK). Never log raw keys.
Keys do not grant role or Dev/Ops — only LLM access when merged in :mod:`app.services.llm_key_resolution`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.user_api_key import UserApiKey
from app.services import secret_manager

logger = logging.getLogger(__name__)

PROVIDERS = ("openai", "anthropic")


def count_all_user_api_key_rows(db: Session) -> int:
    n = db.scalar(select(func.count()).select_from(UserApiKey))
    return int(n or 0)


@dataclass(frozen=True)
class MaskedKeyInfo:
    provider: str
    last4: str
    has_key: bool


def normalize_provider(raw: str) -> str | None:
    p = (raw or "").strip().lower()
    if p in PROVIDERS:
        return p
    if p in ("oai", "open_ai"):
        return "openai"
    if p in ("anth", "claude", "anthropic_claude"):
        return "anthropic"
    return None


def _validate_key_shape(provider: str, key: str) -> str | None:
    if not key or not key.strip():
        return "Key is empty."
    k = key.strip()
    if len(k) < 12:
        return "Key is too short."
    if provider == "openai":
        if not (k.startswith("sk-") or k.startswith("sk-proj-")):
            return "OpenAI API keys should start with sk- or sk-proj-."
    elif provider == "anthropic":
        if not k.startswith("sk-ant"):
            return "Anthropic API keys should start with sk-ant."
    if re.search(r"[\r\n\x00]", k):
        return "Key may not contain line breaks."
    return None


def mask_key_hint(key: str) -> str:
    k = (key or "").strip()
    if len(k) <= 4:
        return "****"
    return "****" + k[-4:]


def set_user_api_key(
    db: Session,
    telegram_user_id: int,
    provider: str,
    raw_key: str,
) -> tuple[bool, str]:
    p = normalize_provider(provider) or (provider or "").strip().lower()
    if p not in PROVIDERS:
        return False, f"Unknown provider. Use: {', '.join(PROVIDERS)}"
    err = _validate_key_shape(p, raw_key)
    if err:
        return False, err
    if not secret_manager.is_configured():
        return (
            False,
            "Nexa is not configured to store keys yet (NEXA_SECRET_KEY missing on the server).",
        )
    try:
        enc = secret_manager.encrypt(raw_key.strip())
    except ValueError as e:
        logger.error("user_api_key encrypt not configured: %s", e)
        return False, "Encryption is not available on this server. Ask the Nexa owner to set NEXA_SECRET_KEY."

    row = db.scalar(
        select(UserApiKey).where(
            UserApiKey.telegram_user_id == int(telegram_user_id),
            UserApiKey.provider == p,
        )
    )
    if row is None:
        row = UserApiKey(
            telegram_user_id=int(telegram_user_id),
            provider=p,
            api_key_encrypted=enc,
        )
        db.add(row)
    else:
        row.api_key_encrypted = enc
    db.commit()
    label = "OpenAI" if p == "openai" else "Anthropic"
    return True, f"{label} key saved for your account."


def get_user_api_key(
    db: Session,
    telegram_user_id: int,
    provider: str,
) -> str | None:
    p = normalize_provider(provider) or (provider or "").strip().lower()
    if p not in PROVIDERS:
        return None
    row = db.scalar(
        select(UserApiKey).where(
            UserApiKey.telegram_user_id == int(telegram_user_id),
            UserApiKey.provider == p,
        )
    )
    if row is None or not (row.api_key_encrypted or "").strip():
        return None
    try:
        return secret_manager.decrypt(row.api_key_encrypted)
    except ValueError:
        return None


def get_decrypted_keys_by_provider(db: Session, telegram_user_id: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in list_user_api_key_rows(db, int(telegram_user_id)):
        try:
            k = secret_manager.decrypt(r.api_key_encrypted)
        except (ValueError, OSError) as e:
            logger.error("user_api_key decrypt row id=%s err=%s", r.id, type(e).__name__)
            continue
        p = (r.provider or "").strip()
        if p in PROVIDERS and k and k.strip():
            out[p] = k
    return out


def list_user_api_key_rows(db: Session, telegram_user_id: int) -> list[UserApiKey]:
    return list(
        db.scalars(
            select(UserApiKey).where(UserApiKey.telegram_user_id == int(telegram_user_id))
        ).all()
    )


def delete_user_api_key(
    db: Session,
    telegram_user_id: int,
    provider: str,
) -> bool:
    p = normalize_provider(provider) or (provider or "").strip().lower()
    if p not in PROVIDERS:
        return False
    r = db.execute(
        delete(UserApiKey).where(
            UserApiKey.telegram_user_id == int(telegram_user_id),
            UserApiKey.provider == p,
        )
    )
    db.commit()
    return (r.rowcount or 0) > 0


def list_user_providers(
    db: Session,
    telegram_user_id: int,
) -> list[MaskedKeyInfo]:
    out: list[MaskedKeyInfo] = []
    q = select(UserApiKey).where(UserApiKey.telegram_user_id == int(telegram_user_id))
    rows = {r.provider: r for r in db.scalars(q).all()}
    for p in PROVIDERS:
        row = rows.get(p)
        if not row or not (row.api_key_encrypted or "").strip():
            out.append(MaskedKeyInfo(p, "", has_key=False))
            continue
        try:
            plain = secret_manager.decrypt(row.api_key_encrypted)
            last4 = (plain or "")[-4:].rjust(4, "•")
            out.append(MaskedKeyInfo(p, last4, has_key=True))
        except (ValueError, OSError, TypeError) as e:
            logger.error("user_api_key list mask: %s", type(e).__name__)
            out.append(MaskedKeyInfo(p, "****", has_key=True))
    return out


def format_key_list_telegram(db: Session, telegram_user_id: int) -> str:
    lines: list[str] = ["Nexa API keys (your account)", ""]
    for m in list_user_providers(db, int(telegram_user_id)):
        if m.has_key and m.last4:
            pl = f"{m.provider}: set (…{m.last4})"
        else:
            pl = f"{m.provider}: not set"
        lines.append(f"– {pl}")
    lines += [
        "",
        "To add: `/key set openai <key>` or `/key set anthropic <key>`",
        "To remove: `/key delete openai` or `/key delete anthropic`",
    ]
    return "\n".join(lines)
