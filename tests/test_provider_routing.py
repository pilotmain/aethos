# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider router — early Vercel / Railway / GitHub intent."""

from __future__ import annotations

import pytest

from app.services.external_execution_session import text_has_railway_execution_context
from app.services.provider_router import (
    CONFIDENCE_SOFT_GATE,
    apply_router_to_operator_hints,
    detect_primary_provider,
    extract_urls_from_text,
    should_skip_railway_bounded_path,
)
from app.services.operator_runners.base import detect_provider_hints


def test_extract_urls() -> None:
    t = "see https://foo.vercel.app/ and https://github.com/x/y "
    u = extract_urls_from_text(t)
    assert any("vercel.app" in x for x in u)
    assert any("github.com" in x for x in u)


def test_vercel_url_and_vercel_com_text_high_confidence() -> None:
    msg = "go to vercel.com and check https://my-app.vercel.app"
    urls = extract_urls_from_text(msg)
    prov, conf = detect_primary_provider(msg, urls)
    assert prov == "vercel"
    assert conf >= 0.9


def test_railway_keyword_and_domain() -> None:
    msg = "railway logs for https://myproj.up.railway.app"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "railway"
    assert conf >= 0.85


def test_github_link_and_push_language() -> None:
    msg = "push to remote https://github.com/acme/repo"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "github"
    assert conf >= CONFIDENCE_SOFT_GATE


def test_mixed_strong_signals_tie_prefers_generic_bucket() -> None:
    msg = "compare https://x.vercel.app vs https://y.up.railway.app deploy"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "generic"
    assert conf < CONFIDENCE_SOFT_GATE


def test_should_skip_railway_for_vercel_only() -> None:
    msg = "open vercel.com and fix https://shop.example.vercel.app"
    assert should_skip_railway_bounded_path(msg) is True
    assert text_has_railway_execution_context(msg, None) is False


def test_should_not_skip_when_railway_explicit() -> None:
    msg = "railway logs https://svc.up.railway.app"
    assert should_skip_railway_bounded_path(msg) is False


def test_apply_router_clears_railway_when_vercel_wins() -> None:
    msg = "go to vercel.com status https://cool.vercel.app"
    base = detect_provider_hints(msg)
    merged = apply_router_to_operator_hints(msg, base)
    assert merged["vercel"] is True
    assert merged["railway"] is False


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_operator_turn_prefers_vercel_over_railway_default(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    import uuid

    from app.services.gateway.context import GatewayContext
    from app.services.operator_execution_loop import try_operator_execution

    monkeypatch.setattr(
        "app.services.operator_execution_loop.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=True),
    )
    monkeypatch.setattr(
        "app.services.operator_runners.vercel.run_vercel_operator_readonly",
        lambda cwd=None: (
            "vercel diagnostics ok",
            {},
            [],
            True,
        ),
    )

    uid = f"pr_{uuid.uuid4().hex[:8]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    msg = "check deployment on vercel.com https://demo.vercel.app"
    r = try_operator_execution(user_text=msg, gctx=gctx, db=db_session, snapshot={})
    assert r.handled is True
    assert r.provider == "vercel"
