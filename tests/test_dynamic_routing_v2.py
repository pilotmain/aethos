# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Dynamic provider routing v2 — AWS, GitHub-only skip Railway, neutral probe intro."""

from __future__ import annotations

from app.services.external_execution_session import format_probe_readonly_intro
from app.services.intent_focus_filter import extract_focused_intent
from app.services.provider_router import (
    apply_router_to_operator_hints,
    detect_primary_provider,
    extract_urls_from_text,
    should_skip_railway_bounded_path,
)
from app.services.operator_runners.base import detect_provider_hints


def test_aws_url_scores_aws() -> None:
    msg = "check logs https://logs.us-east-1.amazonaws.com/foo"
    prov, conf = detect_primary_provider(msg, extract_urls_from_text(msg))
    assert prov == "aws"
    assert conf >= 0.85


def test_github_push_skips_railway_path_without_railway_name() -> None:
    msg = "push to remote https://github.com/acme/repo"
    assert should_skip_railway_bounded_path(msg) is True
    fi = extract_focused_intent(msg)
    assert fi.get("ignore_railway") is True


def test_apply_router_github_clears_railway_hint() -> None:
    msg = "push changes to github.com/acme/x"
    base = detect_provider_hints(msg)
    merged = apply_router_to_operator_hints(msg, base)
    assert merged.get("github") is True
    assert merged.get("railway") is False


def test_vercel_probe_intro_not_railway_first_sentence() -> None:
    intro = format_probe_readonly_intro(detected_provider="vercel")
    assert "Railway session now" not in intro
    assert "read-only" in intro.lower()


def test_extract_focused_intent_github_sets_ignore_railway() -> None:
    fi = extract_focused_intent("git push origin main https://github.com/x/y")
    assert fi.get("github_push") is True
    assert fi.get("ignore_railway") is True
