"""Minimal outbound context for providers (Phase 38)."""

from __future__ import annotations

from typing import Any

from app.services.token_economy.counter import estimate_payload_tokens


def build_minimal_provider_context(
    *,
    task: str | None = None,
    agent: str | None = None,
    memory: list[str] | None = None,
    artifacts: list[str] | None = None,
    user_message: str | None = None,
    turn_memory_summary: str | None = None,
    max_tokens: int | None = None,
    max_memory_snippets: int = 5,
) -> tuple[dict[str, Any], int, dict[str, Any]]:
    """
    Build a minimal dict for provider prompts and return (payload, token_estimate, summary).

    Never includes full conversation or raw files by default.
    """
    mem_in = list(memory or [])[:max_memory_snippets]
    art_in = list(artifacts or [])[:20]

    ctx: dict[str, Any] = {
        "task": (task or "")[:8000],
        "agent_role": (agent or "")[:500],
        "memory_snippets": [str(x)[:1500] for x in mem_in],
        "artifact_refs": [str(x)[:2000] for x in art_in],
    }
    if user_message:
        ctx["user_message"] = str(user_message)[:8000]
    if turn_memory_summary:
        ctx["turn_memory_summary"] = str(turn_memory_summary)[:2000]

    est = estimate_payload_tokens(ctx)
    if max_tokens is not None and est > max_tokens:
        # Trim memory snippets first
        while ctx["memory_snippets"] and estimate_payload_tokens(ctx) > max_tokens:
            ctx["memory_snippets"].pop()
        est = estimate_payload_tokens(ctx)

    summary = {
        "task_chars": len(ctx.get("task") or ""),
        "memory_snippets": len(ctx.get("memory_snippets") or []),
        "artifact_count": len(ctx.get("artifact_refs") or []),
        "user_message_chars": len(ctx.get("user_message") or ""),
        "turn_memory_summary_chars": len(ctx.get("turn_memory_summary") or ""),
    }
    return ctx, est, summary
