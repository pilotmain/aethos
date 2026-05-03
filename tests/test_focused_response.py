"""Intent focus filter — no Railway noise on Vercel-scoped turns."""

from __future__ import annotations

import pytest

from app.services.gateway.runtime import gateway_finalize_operator_or_execution_reply
from app.services.intent_focus_filter import (
    apply_focus_discipline_to_operator_execution_text,
    extract_focused_intent,
)


def test_extract_focused_intent_vercel_github_ignores_railway() -> None:
    msg = "Deploy to Vercel production and push to GitHub https://x.vercel.app"
    fi = extract_focused_intent(msg)
    assert fi["vercel_deploy"] is True
    assert fi["github_push"] is True
    assert fi["railway"] is False
    assert fi.get("ignore_railway") is True


def test_extract_focused_intent_keeps_railway_when_named() -> None:
    msg = "Compare Vercel preview with Railway staging"
    fi = extract_focused_intent(msg)
    assert fi["railway"] is True
    assert fi.get("ignore_railway") is not True


def test_strip_railway_lines_when_vercel_focused() -> None:
    body = "### Progress\n\n→ Check Vercel\n\n→ Ask for Railway token on worker\n\n### Done"
    user = "fix my Vercel deploy at https://foo.vercel.app"
    out = apply_focus_discipline_to_operator_execution_text(body, user_text=user)
    assert "Railway" not in out
    assert "Vercel" in out


def test_squash_access_wall_when_long_vercel_scoped() -> None:
    filler = "word " * 200
    body = (
        "### A\n\n"
        + filler
        + "\n\nOnce access is in place you can retry the full hosted diagnostics flow.\n\n"
        + filler
        + "\n\n### B\n\nkeep"
    )
    user = "vercel deploy https://z.vercel.app"
    out = apply_focus_discipline_to_operator_execution_text(body, user_text=user)
    assert "Once access is in place" not in out.lower() or "only if a step below" in out.lower()


def test_gateway_finalize_strips_railway_for_vercel_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_orchestration_intro.get_settings",
        lambda: __import__("types").SimpleNamespace(nexa_operator_mode=False),
    )
    raw = "Check my Vercel dashboard https://a.vercel.app"
    body = "Line one.\n\nPlease configure Railway CLI on the worker.\n\nTail done."
    out = gateway_finalize_operator_or_execution_reply(body, user_text=raw, layer="operator_execution")
    assert "Railway" not in out
