# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""BYOK: encrypted user keys, merged LLM selection, and role invariants."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.services import secret_manager
from app.services.llm_key_resolution import get_merged_api_keys, doctor_user_llm_block
from app.services.llm_request_context import bind_llm_telegram, unbind_llm_telegram, llm_telegram_context
from app.services import user_api_keys as uak
from app.services.user_capabilities import can_run_dev_agent_jobs


SECRET = "0" * 32


@pytest.fixture(autouse=True)
def _secret_env(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXA_SECRET_KEY", SECRET)
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
    yield
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()


def test_secret_encrypt_roundtrip() -> None:
    c = secret_manager.encrypt("sk-abc123def456hij7890xyz")
    assert "sk-abc" not in c
    p = secret_manager.decrypt(c)
    assert p == "sk-abc123def456hij7890xyz"


def test_set_get_delete_key_roundtrip() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        tid = 900_001_001
        assert uak.set_user_api_key(
            db, tid, "openai", "sk-1234567890abcdefghijklmnopqrstuvwxy"
        )[0] is True
        k = uak.get_user_api_key(db, tid, "openai")
        assert k is not None and k.startswith("sk-12")
        assert uak.delete_user_api_key(db, tid, "openai") is True
        assert uak.get_user_api_key(db, tid, "openai") is None
    finally:
        db.close()


def test_list_masks_no_full_key() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        tid = 900_001_002
        uak.set_user_api_key(db, tid, "openai", "sk-1234567890abcdefghijklmnopqrst")
        t = uak.format_key_list_telegram(db, tid)
    finally:
        db.close()
    assert "sk-12" not in t
    assert "1234" in t or "st" in t or "…" in t or "set" in t  # last4 or masked
    assert "Nexa API keys" in t or "Nexa" in t


def test_merged_prefers_user_key_over_system(monkeypatch) -> None:
    """With both env and user keys, merged OpenAI is the user key (BYOK wins per provider)."""
    ensure_schema()
    db = SessionLocal()
    try:
        tid = 42
        uak.set_user_api_key(
            db, tid, "openai", "sk-aaaaaaaaaaaaaaaaaaaaaa_aaaaaa_xxxx"
        )
        s = get_settings()
        p = patch.object(
            s,
            "openai_api_key",
            "sk-bbbbbbbbbbbbbbbbbbbbbbb_sys_only",
        )
        p.start()
        try:
            p2 = patch.object(s, "anthropic_api_key", None)
            p2.start()
            try:
                t = bind_llm_telegram(db, int(tid))
                try:
                    m = get_merged_api_keys()
                finally:
                    unbind_llm_telegram(t)
                assert m.has_user_openai is True
                assert m.openai_api_key == "sk-aaaaaaaaaaaaaaaaaaaaaa_aaaaaa_xxxx"
            finally:
                p2.stop()
        finally:
            p.stop()
    finally:
        db.close()


def test_fallback_no_keys_empty_merge(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    m = get_merged_api_keys()
    assert not m.has_any_key


def test_guest_cannot_run_dev_with_personal_key() -> None:
    assert not can_run_dev_agent_jobs("guest")


def test_mask_does_not_echo_prefix() -> None:
    m = uak.mask_key_hint("sk-xyzyyyyyyyzzzzwxyz9abcdefghij")
    assert m.startswith("****")
    assert "yzy" not in m[4:]

def test_doctor_user_llm_mentions_key_status() -> None:
    mdb = MagicMock()
    t = doctor_user_llm_block(mdb, telegram_user_id=1)
    assert "User LLM" in t
    assert "user key" in t
