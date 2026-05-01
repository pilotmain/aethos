"""
Merge per-user API keys (BYOK) with system env keys for LLM calls.
User key wins per provider, then system; never logged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.telegram_repo import TelegramRepository
from app.services import user_api_keys as uak
from app.services.llm_request_context import get_llm_telegram_context


@dataclass
class MergedLlmKeyInfo:
    anthropic_api_key: str | None
    openai_api_key: str | None
    has_user_anthropic: bool = False
    has_user_openai: bool = False
    has_system_anthropic: bool = False
    has_system_openai: bool = False
    has_any_key: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        a = (self.anthropic_api_key or "").strip() if self.anthropic_api_key else None
        o = (self.openai_api_key or "").strip() if self.openai_api_key else None
        self.anthropic_api_key = a or None
        self.openai_api_key = o or None
        self.has_any_key = bool(self.anthropic_api_key or self.openai_api_key)

    @property
    def primary_label(self) -> str:
        """What the stack would try first (anthropic, then openai) — for doctor only."""
        if self.anthropic_api_key:
            if self.has_user_anthropic:
                return "anthropic (user key)"
            return "anthropic (system key)"
        if self.openai_api_key:
            if self.has_user_openai:
                return "openai (user key)"
            return "openai (system key)"
        return "none"

    @property
    def is_fallback(self) -> bool:
        s = get_settings()
        if not s.use_real_llm:
            return True
        return not self.has_any_key


@dataclass(frozen=True)
class ResolvedLLM:
    """Who can pay for LLM calls for this Nexa user (BYOK first, then server env)."""

    provider: str | None  # "anthropic" | "openai" | None
    source: Literal["user", "system", "none"]
    available: bool
    reason: str | None = None


def resolve_llm_for_user(db: Session, app_user_id: str) -> ResolvedLLM:
    """
    Same merge order as chat: user BYOK (per linked Telegram user), then system keys in settings/env.

    Used for gates that must match “provider online” in the UI (custom agents, etc.).
    """
    s = get_settings()
    if not s.use_real_llm:
        return ResolvedLLM(
            provider=None,
            source="none",
            available=False,
            reason="USE_REAL_LLM is off on this server.",
        )

    link = TelegramRepository().get_by_app_user(db, app_user_id)
    if link and link.telegram_user_id:
        try:
            m = uak.get_decrypted_keys_by_provider(db, int(link.telegram_user_id))
        except (TypeError, OSError, ValueError):
            m = {}
        if m.get("anthropic"):
            return ResolvedLLM(provider="anthropic", source="user", available=True)
        if m.get("openai"):
            return ResolvedLLM(provider="openai", source="user", available=True)

    sa = (s.anthropic_api_key or "").strip()
    so = (s.openai_api_key or "").strip()
    if sa:
        return ResolvedLLM(provider="anthropic", source="system", available=True)
    if so:
        return ResolvedLLM(provider="openai", source="system", available=True)

    return ResolvedLLM(
        provider=None,
        source="none",
        available=False,
        reason="No user BYOK and no ANTHROPIC_API_KEY / OPENAI_API_KEY on the server.",
    )


def get_merged_api_keys() -> MergedLlmKeyInfo:
    s = get_settings()
    sa = (s.anthropic_api_key or None) if (s.anthropic_api_key or "").strip() else None
    so = (s.openai_api_key or None) if (s.openai_api_key or "").strip() else None
    info = MergedLlmKeyInfo(
        anthropic_api_key=sa,
        openai_api_key=so,
    )
    info.has_system_anthropic = sa is not None
    info.has_system_openai = so is not None
    db, tid = get_llm_telegram_context()
    if not db or tid is None or not int(tid):
        return info
    try:
        m = uak.get_decrypted_keys_by_provider(db, int(tid))
    except (TypeError, OSError) as e:
        # DB errors — fall back to system
        from logging import getLogger
        getLogger(__name__).debug("get_decrypted_keys: %s", e)
        m = {}
    if m.get("anthropic"):
        info.anthropic_api_key = m["anthropic"]
        info.has_user_anthropic = True
    if m.get("openai"):
        info.openai_api_key = m["openai"]
        info.has_user_openai = True
    return MergedLlmKeyInfo(
        anthropic_api_key=info.anthropic_api_key,
        openai_api_key=info.openai_api_key,
        has_user_anthropic=info.has_user_anthropic,
        has_user_openai=info.has_user_openai,
        has_system_anthropic=info.has_system_anthropic,
        has_system_openai=info.has_system_openai,
    )


def doctor_user_llm_block(
    db: Any,
    *,
    telegram_user_id: int | None,
) -> str:
    """One section for :func:`app.services.nexa_doctor.build_nexa_doctor_text` (User LLM)."""
    from app.services.llm_request_context import llm_telegram_context

    s = get_settings()
    if db is not None and telegram_user_id is not None:
        with llm_telegram_context(db, int(telegram_user_id)):
            merged = get_merged_api_keys()
        d = uak.get_decrypted_keys_by_provider(db, int(telegram_user_id))
        u_present = bool(d.get("anthropic") or d.get("openai"))
    else:
        merged = get_merged_api_keys()
        u_present = bool(merged.has_user_anthropic or merged.has_user_openai)
    u_line = f"user key: **{'present' if u_present else 'missing'}**"
    if not s.use_real_llm:
        p_line = "provider: **n/a (USE_REAL_LLM is off — no model calls on this run)**"
    elif not merged.has_any_key:
        p_line = "provider: **fallback (no API keys in this merge: heuristics / offline)**"
    else:
        p_line = f"provider: **{merged.primary_label}**"
    if not s.use_real_llm:
        s_line = "system fallback: **off** (set USE_REAL_LLM to use system or /key keys)"
    else:
        ok = merged.has_system_anthropic or merged.has_system_openai
        s_line = f"system env keys: **{'enabled' if ok else 'unavailable (not set)'}**"
    return f"**User LLM**:\n- {u_line}\n- {p_line}\n- {s_line}"
