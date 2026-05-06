"""Canonical capability flags and identity strings for AethOS (Phase 40)."""

from __future__ import annotations

import re

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


NEXA_CAPABILITY_REPLY = """I'm AethOS.

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


_CAPABILITY_IDENTITY_RE = re.compile(
    r"(?is)\b("
    r"what can you do|"
    r"what are you capable of|"
    r"what are your capabilities|"
    r"your capabilities|"
    r"what do you support"
    r")\b",
)


def is_capability_identity_question(text: str) -> bool:
    """Short product-capability questions → :func:`narrative_capability_answer` (not domain-specific how-tos)."""
    t = (text or "").strip()
    if not t or len(t) > 220:
        return False
    if not _CAPABILITY_IDENTITY_RE.search(t):
        return False
    low = t.lower()
    if "what can you do" in low:
        tail = low.split("what can you do", 1)[-1].lstrip()
        if tail.startswith("with "):
            return False
    return True


NEXA_MULTI_AGENT_CLARIFICATION = """Yes — AethOS can coordinate multiple runs and parallel, task-focused work when that fits. I still need a **concrete goal** before setting anything up.

Examples:
• **Describe what you want shipped or fixed** — we'll break it into tracked work
• **Ask for a multi-step workflow** — missions and jobs can run after approval
• **Use chat to steer focus** — AethOS creates agents dynamically when the task needs them

What should we tackle first?"""
