"""operator_verify_followup copy."""

from __future__ import annotations

from app.services.operator_verify_followup import append_verify_vs_mutate_followup


def test_no_append_when_not_verified() -> None:
    out = append_verify_vs_mutate_followup("BASE", verified=False, provider_label="X")
    assert out == "BASE"


def test_appends_when_verified() -> None:
    out = append_verify_vs_mutate_followup("BASE", verified=True, provider_label="Test")
    assert "BASE" in out
    assert "Test verification succeeded" in out
    assert "§11.8" in out
