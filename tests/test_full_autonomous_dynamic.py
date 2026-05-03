"""Full autonomous / dynamic routing slice — prefs, credential UX dedup, multi-host scores."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.credential_session_store import mark_credential_guidance_shown, was_credential_guidance_recent
from app.services.external_execution_session import parse_followup_preferences
from app.services.provider_router import (
    apply_router_to_operator_hints,
    detect_primary_provider,
    extract_urls_from_text,
    should_skip_railway_bounded_path,
)
from app.services.operator_runners.base import detect_provider_hints


def test_fly_dev_url_scores_fly() -> None:
    msg = "logs for https://api.myapp.fly.dev/health"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "fly"
    assert conf >= 0.9


def test_render_com_scores_render() -> None:
    msg = "status https://mysvc.onrender.com"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "render"
    assert conf >= 0.9


def test_apply_router_digitalocean_clears_railway_when_do_url() -> None:
    msg = "droplet https://cloud.digitalocean.com/foo"
    base = detect_provider_hints(msg)
    merged = apply_router_to_operator_hints(msg, base)
    assert merged.get("digitalocean") is True
    assert merged.get("railway") is False


def test_should_skip_railway_for_netlify_url() -> None:
    msg = "fix preview https://branch--mysite.netlify.app"
    assert should_skip_railway_bounded_path(msg) is True


def test_parse_followup_autonomous_short_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_autonomous_external_flow=True),
    )
    out = parse_followup_preferences("go", {})
    assert out.get("permission_to_probe") is True
    assert out.get("auth_method") == "local_cli"
    assert out.get("deploy_mode") == "deploy_when_ready"


def test_parse_followup_autonomous_disabled_does_not_expand_go(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(nexa_operator_mode=True, nexa_operator_autonomous_external_flow=False),
    )
    out = parse_followup_preferences("go", {})
    assert out.get("deploy_mode") != "deploy_when_ready"


def test_credential_guidance_dedup_same_user() -> None:
    uid = "test_user_dedup_1"
    tag = "railway_token_paste"
    assert was_credential_guidance_recent(uid, tag, window_sec=60) is False
    mark_credential_guidance_shown(uid, tag)
    assert was_credential_guidance_recent(uid, tag, window_sec=60) is True


def test_credential_guidance_separate_users() -> None:
    mark_credential_guidance_shown("user_a", "railway_token_paste")
    assert was_credential_guidance_recent("user_b", "railway_token_paste", window_sec=60) is False
