"""Phase 38 — minimal provider context builder."""

from __future__ import annotations

from app.services.token_economy.context_builder import build_minimal_provider_context


def test_builder_limits_memory_snippets() -> None:
    ctx, _est, summary = build_minimal_provider_context(
        task="do work",
        agent="Coder",
        memory=["m"] * 12,
        artifacts=["a1"],
        max_memory_snippets=5,
    )
    assert len(ctx["memory_snippets"]) == 5
    assert summary["memory_snippets"] == 5


def test_builder_returns_summary_not_full_memory() -> None:
    ctx, est, summary = build_minimal_provider_context(task="t", agent="a", memory=["x" * 5000])
    assert len(ctx["memory_snippets"][0]) <= 1500
    assert est >= 1
    assert "artifact_count" in summary
