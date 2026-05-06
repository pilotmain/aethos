"""
Hints for mini-document style (scannable ## sections) on substantial replies only.
Not applied to one-line or trivial chat — see :func:`should_use_structured_style`.
"""
from __future__ import annotations

import re
from typing import Any

# Marketing: expected section flow (align with agent_orchestrator marketing system prompt)
MARKETING_MINI_DOC_SECTIONS: tuple[str, ...] = (
    "What I found",
    "Insight",
    "Positioning",
    "Marketing angles",
    "Suggested copy",
    "Sources",
)

# Research-style answers
RESEARCH_MINI_DOC_SECTIONS: tuple[str, ...] = (
    "Summary",
    "Findings",
    "Sources",
    "Next steps",
)

# Strategy
STRATEGY_MINI_DOC_SECTIONS: tuple[str, ...] = (
    "Situation",
    "Options",
    "Recommendation",
    "Next steps",
)

# General substantial responses (AethOS composer, no specialist agent)
GENERAL_MINI_DOC_SECTIONS: tuple[str, ...] = (
    "Summary",
    "Key points",
    "Recommendation",
    "Next steps",
)

# Post-document / document planning
DOCUMENT_FOLLOWUP_SECTIONS: tuple[str, ...] = (
    "Document created",
    "Download",
    "Suggested follow-up",
)

WORKFLOW_SECTIONS: tuple[str, ...] = (
    "Current work",
    "Completed",
    "Next step",
)

# Flows that always get section guidance (user message may be a short URL or word)
FORCED_RESPONSE_KINDS: frozenset[str] = frozenset(
    {
        "marketing_web_analysis",
        "public_web",
        "web_search",
        "document_artifact",
        "document_planning",
        "browser_preview",
        "workflow_summary",
    }
)

_RE_WORK_OR_ANALYSIS = re.compile(
    r"(?i)\b("
    r"launch|roadmap|gtm|strategy|marketing|campaign|compare|analyze|analyse|"
    r"competitor|messaging|positioning|"
    r"how (do|to|can)|\bbuild\b|write a|plan (a|my|the|our|for)|"
    r"go to market|business plan|product|features|workflow"
    r")\b"
)


def _wants_list_or_summary(t: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(list|summarise|summarize|summary|break down|outline|steps|"
            r"analyze|analyse|compare|research|draft)\b",
            t,
        )
    )


def _is_brief_identity_or_one_line_faq(t: str) -> bool:
    """
    e.g. "Who is Raya?" — not a work deliverable; keep the reply casual / non mini-doc
    (unless a forced response_kind already applies).
    """
    raw = (t or "").strip()
    if not raw or "\n" in raw or len(raw) > 200:
        return False
    if _RE_WORK_OR_ANALYSIS.search(raw):
        return False
    w = len(raw.split())
    if w > 6:
        return False
    low = raw.rstrip("?.! ").lower()
    if 2 <= w <= 5 and re.match(r"^who (is|are) .{1,120}$", low, re.DOTALL):
        return True
    if 2 <= w <= 4 and re.match(
        r"^what (is|are) (the )?[\w' -]+(\s+[\w' -]+){0,2}\??$",
        low,
    ) and " the " not in f" {low} ":
        if re.match(r"^what (is|are) the\b", low) and w > 4:
            return False
        if re.match(r"^what (is|are) (a|an) \b", low):
            return False
        return True
    if re.match(
        r"(?i)^(?:what do you mean|huh\?|pardon\?|can you (?:say that )?again\??)([.!?\s]*)$",
        raw,
    ) and w <= 8:
        return True
    return False


def should_use_structured_style(
    user_text: str,
    agent_key: str | None = None,
    intent: str | None = None,
    response_kind: str | None = None,
) -> bool:
    """
    True when the *prompt* for the model should include mini-doc section guidance
    (not for one-line or trivial user messages).
    """
    from app.services.copilot_next_steps import is_goal_oriented_user_message, is_trivial_user_message

    _ = intent
    t = (user_text or "").strip()
    rk = (response_kind or "").strip()
    if rk in FORCED_RESPONSE_KINDS:
        return True
    if _is_brief_identity_or_one_line_faq(t):
        return False
    if is_trivial_user_message(t):
        return False
    ak = (agent_key or "").strip().lower()
    if ak in (
        "marketing",
        "research",
        "strategy",
        "dev",
        "ops",
        "developer",
        "qa",
    ):
        return bool(len(t) > 1)
    if is_goal_oriented_user_message(t) or _wants_list_or_summary(t):
        return True
    if len(t.split()) >= 5:
        return True
    return False


def structured_style_guidance_for(
    agent_key: str | None,
    response_kind: str | None = None,
) -> str:
    """
    Short block to append to a system prompt for scannable, sectioned output.
    """
    rk = (response_kind or "").strip()
    ak = (agent_key or "").strip().lower()

    if rk == "marketing_web_analysis" or ak == "marketing":
        return (
            "For website or product marketing analysis, use exactly these Markdown section headings, "
            "in this order: "
            "## What I found, ## Insight, ## Positioning, ## Marketing angles, "
            "## Suggested copy, ## Sources. "
            "If the page or search evidence is thin, start with: "
            "I found limited product detail from the public page/search results. "
            "Then still give insight, hedged positioning, and best-effort copy."
        )
    if ak == "research" or rk in (
        "public_web",
        "web_search",
        "browser_preview",
    ):
        return (
            "For research or public-web responses, use these sections in order: "
            "## Summary, ## Findings, ## Sources, ## Next steps. "
            "Cite or list sources clearly when the tools or sources provided any."
        )
    if ak == "strategy" or rk in ("product_planning", "strategy_brief"):
        return (
            "For strategy or product planning, use: "
            "## Situation, ## Options, ## Recommendation, ## Next steps. "
            "Keep each section scannable; avoid dumping unstructured paragraphs."
        )
    if rk in ("document_artifact", "document_planning"):
        return (
            "Clarify what was planned or created, how to download or find the document, and optionally "
            "## Suggested follow-up with one concrete next action."
        )
    if rk == "workflow_summary":
        return (
            "For a workflow or progress summary, use: "
            "## Current work, ## Completed, ## Next step. "
            "Be concrete and task-shaped; avoid a wall of text."
        )

    return (
        "For a substantial answer (not a greeting or a one-liner), prefer: "
        "## Summary, ## Key points, ## Recommendation, ## Next steps — "
        "or only the sections that fit, with a brief intro. "
        "Do not use this full structure for two-word replies, greetings, or simple yes/no."
    )


def structured_system_suffix_for_nexa_composer(ctx: Any) -> str:
    """
    For response composer: append only when the user request warrants structure.
    `ctx` is a :class:`response_composer.ResponseContext`.
    """
    u = (getattr(ctx, "user_message", None) or "")[:8_000]
    ak = getattr(ctx, "routing_agent_key", None)
    rk = getattr(ctx, "response_kind", None)
    if not should_use_structured_style(
        u,
        agent_key=str(ak) if ak else None,
        intent=getattr(ctx, "intent", None),
        response_kind=str(rk) if rk else None,
    ):
        return ""
    return "\n\n" + structured_style_guidance_for(ak, rk).strip()
