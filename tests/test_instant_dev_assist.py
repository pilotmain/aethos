"""Phase 50 — instant dev assist bundle and gateway appendix."""

from __future__ import annotations

from app.services.instant_dev_assist import format_assist_appendix, instant_dev_assist


def test_instant_dev_assist_tags_and_outline() -> None:
    t = "EKS pod CrashLoop, OIDC login 401 after npm upgrade"
    b = instant_dev_assist(t)
    assert "Kubernetes" in b["infra_tags"] or "EKS" in " ".join(b["infra_tags"])
    assert b["fix_outline"]
    assert b["risk"] == "low"


def test_format_assist_appendix_includes_detected() -> None:
    out = format_assist_appendix(
        user_text="docker build fails on TypeScript project",
        intent="stuck_dev",
    )
    assert out
    assert "Detected" in out or "Lean fix" in out
