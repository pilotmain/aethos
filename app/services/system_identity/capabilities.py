"""Canonical capability flags and identity strings for Nexa-next (Phase 40)."""

from __future__ import annotations

CAPABILITIES: dict[str, bool] = {
    "dev_execution": True,
    "memory": True,
    "scheduler": True,
    "local_models": True,
    "multi_agent_dynamic": True,
    "system_access": True,
}


def describe_capabilities() -> dict[str, bool]:
    """Return the frozen capability map (same keys as :data:`CAPABILITIES`)."""
    return dict(CAPABILITIES)


NEXA_CAPABILITY_REPLY = """I'm Nexa.

I help you execute real work — not just answer questions.

I can:

• Run development tasks on your codebase
• Execute multi-step workflows
• Remember context over time
• Operate locally (no external APIs required)
• Use external models with strict privacy controls
• Automate tasks and run continuously

I create agents dynamically when needed — you don't need to manage them.

Everything I do is:

• Permission-controlled
• Privacy-filtered
• Cost-aware
• Observable in Mission Control

What do you want to get done?"""


def narrative_capability_answer() -> str:
    """User-facing answer for “what can you do?” / general capability questions."""
    return NEXA_CAPABILITY_REPLY.strip()


NEXA_MULTI_AGENT_CLARIFICATION = """Yes — Nexa can coordinate multiple runs and parallel, task-focused work when that fits. I still need a **concrete goal** before setting anything up.

Examples:
• **Describe what you want shipped or fixed** — we'll break it into tracked work
• **Ask for a multi-step workflow** — missions and jobs can run after approval
• **Use chat to steer focus** — Nexa creates agents dynamically when the task needs them

What should we tackle first?"""
