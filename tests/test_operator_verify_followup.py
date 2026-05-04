"""operator_verify_followup copy."""

from __future__ import annotations

from app.services.operator_verify_followup import append_verify_vs_mutate_followup


def test_no_append_when_not_verified() -> None:
    out = append_verify_vs_mutate_followup("BASE", verified=False, provider_label="X")
    assert out == "BASE"


def test_no_long_form_when_verified() -> None:
    out = append_verify_vs_mutate_followup("BASE", verified=True, provider_label="Test")
    assert out == "BASE"
    assert "What this step did" not in out
