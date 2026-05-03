"""Session credential reuse + tighter provider routing (operator slice)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.credential_session_store import CredentialSessionStore
from app.services.external_execution_credentials import extract_railway_token_from_user_text
from app.services.provider_router import (
    apply_router_to_operator_hints,
    detect_primary_provider,
    extract_urls_from_text,
    should_skip_railway_bounded_path,
)
from app.services.operator_runners.base import detect_provider_hints


def test_extract_railway_token_assignment() -> None:
    raw = "please use\nRAILWAY_TOKEN=rw_testtoken_value_ok_here\nthanks"
    assert extract_railway_token_from_user_text(raw) == "rw_testtoken_value_ok_here"


def test_vercel_url_beats_railway_keyword_without_railway_host() -> None:
    msg = "railway logs mention but deploy is https://cool.vercel.app only"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "vercel"
    assert conf >= 0.9


def test_apply_router_clears_railway_when_only_vercel_url() -> None:
    msg = "compare hosting https://z.vercel.app"
    base = detect_provider_hints(msg)
    merged = apply_router_to_operator_hints(msg, base)
    assert merged.get("vercel") is True
    assert merged.get("railway") is False


def test_should_skip_railway_for_github_url_only() -> None:
    msg = "push https://github.com/acme/writer"
    assert should_skip_railway_bounded_path(msg) is True


def test_credential_session_store_isolated_instance() -> None:
    s = CredentialSessionStore()
    s.store("u_cred_test", "railway", "railway_token", "tok_value_x")
    assert s.get("u_cred_test", "railway", "railway_token") == "tok_value_x"
    assert s.has_provider("u_cred_test", "railway") is True


def test_maybe_handle_sets_chain_when_operator_and_token(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    from app.services.external_execution_credentials import maybe_handle_external_credential_chat_turn

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            nexa_operator_session_credential_reuse=True,
            nexa_operator_mode=True,
            nexa_operator_zero_nag=True,
        ),
    )
    raw = "RAILWAY_TOKEN=pasted_token_value_for_test_only"
    out = maybe_handle_external_credential_chat_turn(
        db_session,
        user_id="u_chain",
        user_text=raw,
    )
    assert out is not None
    assert out.get("chain_bounded_runner_after_store") is True
