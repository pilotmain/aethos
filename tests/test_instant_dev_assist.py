"""Phase 50 — instant dev assist bundle and gateway appendix."""

from __future__ import annotations

import pytest

from app.services.instant_dev_assist import format_assist_appendix, instant_dev_assist


def test_instant_dev_assist_tags_and_outline() -> None:
    t = "EKS pod CrashLoop, OIDC login 401 after npm upgrade"
    b = instant_dev_assist(t)
    assert "Kubernetes" in b["infra_tags"] or "EKS" in " ".join(b["infra_tags"])
    assert b["fix_outline"]
    assert b["risk"] == "low"


def test_format_assist_appendix_includes_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.execution_trigger.should_merge_phase50_assist",
        lambda intent: True,
    )
    out = format_assist_appendix(
        user_text="docker build fails on TypeScript project",
        intent="stuck_dev",
    )
    assert out
    assert "Context:" in out or "Likely checks:" in out


def test_format_assist_appendix_skipped_when_decisive_default() -> None:
    assert format_assist_appendix(user_text="npm test fails", intent="stuck_dev") is None
