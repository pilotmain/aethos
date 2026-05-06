"""
User-safe, concise decision metadata for transparency (not chain-of-thought).
"""

from __future__ import annotations

import re
from typing import Any

# Short, fixed templates only — do not add raw model text or private reasoning.
R_CODE_CHANGE = "The message asked for a code or file change."
R_PUBLIC_URL = "The message included a public URL."
R_CURRENT_PUBLIC = "The message asked for current public information."
R_COMMAND = "The message matched a known command or shortcut."
R_DETERMINISTIC_TOOL = "This was handled by a deterministic tool or fixed rule."
R_NO_LLM = "This was answered from Nexa state without calling an LLM."
R_APPROVAL = "This action may modify files, so approval is required before it runs."
R_RESEARCH = "Nexa routed to Research to read public sources for this request."
R_OPS = "Nexa routed to Ops to show status or run operational checks."
R_CHAT = "Nexa used the general chat path for this message."
R_GENERAL = "Nexa used the general assistant for this request."

# Terms we never ship to the client (safety for tests and future editors).
_BANNED_SUBSTRINGS = (
    "chain of thought",
    "chain-of-thought",
    "cot",
    "internal",
    "hidden",
    "system prompt",
)


def _sanitize_reason(s: str | None) -> str:
    t = (s or "").strip()
    for b in _BANNED_SUBSTRINGS:
        if b in t.lower():
            t = R_GENERAL
            break
    if len(t) > 500:
        t = t[:497] + "…"
    return t


def _norm_risk(s: str | None) -> str:
    x = (s or "low").strip().lower()
    if x in ("low", "normal", "medium", "high", "med", "max"):
        if x == "med":
            return "medium"
        if x == "max":
            return "high"
        return x
    return "low"


def build_decision_summary(
    *,
    agent_key: str,
    action: str,
    tool: str | None = None,
    reason: str | None = None,
    risk: str | None = None,
    approval_required: bool = False,
    intent: str | None = None,
) -> dict[str, Any]:
    """Build a user-facing decision dict. No prompts, no private reasoning."""
    a = (agent_key or "aethos").strip().lower()[:64] or "aethos"
    act = (action or "chat_response").strip()[:64] or "chat_response"
    t = (tool or "").strip()[:64] or None
    r = _sanitize_reason(reason or R_GENERAL)
    return {
        "agent": a,
        "action": act,
        "tool": t,
        "reason": r,
        "risk": _norm_risk(risk),
        "approval_required": bool(approval_required),
        "intent": (str(intent)[:64] if intent is not None else None),
    }


def merge_no_llm_path(
    decision: dict[str, Any] | None, *, had_llm: bool, tool_hint: str | None
) -> dict[str, Any]:
    """If no LLM was used, prefer tool-only framing unless already specific."""
    if had_llm:
        if decision:
            d = dict(decision)
            d["reason"] = _sanitize_reason(d.get("reason") or R_CHAT)
            return d
        return build_decision_summary(
            agent_key="aethos",
            action="chat_response",
            tool="llm",
            reason=R_CHAT,
            risk="low",
        )
    d = dict(decision) if decision else {}
    d.setdefault("agent", "aethos")
    d["action"] = "tool_only"
    th = (tool_hint or "local_state").strip()[:64] or "local_state"
    d["tool"] = th
    if (d.get("reason") or "") in ("", R_CHAT, R_GENERAL):
        d["reason"] = R_NO_LLM
    d.setdefault("risk", "low")
    d["approval_required"] = bool(d.get("approval_required", False))
    d["reason"] = _sanitize_reason(d.get("reason"))
    return d


def _has_url(u: str) -> bool:
    return bool(re.search(r"https?://", (u or ""), re.I))


def infer_decision_for_web_main(
    *,
    user_text: str,
    routed_agent_key: str,
    intent: str | None,
    response_kind: str | None,
) -> dict[str, Any]:
    t = (user_text or "").strip()
    rkind = (response_kind or "").strip() or None
    rk = (routed_agent_key or "aethos").lower().strip() or "aethos"

    if rkind == "marketing_web_analysis":
        return build_decision_summary(
            agent_key="marketing",
            action="marketing_web_analysis",
            tool="marketing_web_tools",
            reason="Marketing used read-only public page fetch and/or web search for this turn.",
            risk="low",
        )
    if rkind == "web_search" or (rk == "research" and "search" in t.lower() and not _has_url(t)):
        return build_decision_summary(
            agent_key="research",
            action="web_search_summary",
            tool="web_search",
            reason=R_CURRENT_PUBLIC,
            risk="low",
        )
    if rkind == "public_web" or (_has_url(t) and rk in ("aethos", "nexa", "research") and "browser" not in t.lower()):
        return build_decision_summary(
            agent_key="research" if rk == "research" else "aethos",
            action="public_url_summary",
            tool="public_web_reader",
            reason=R_PUBLIC_URL,
            risk="low",
        )
    if rkind == "browser_preview":
        return build_decision_summary(
            agent_key="research",
            action="public_url_summary",
            tool="browser_preview",
            reason="Your message used browser preview to render a public page (owner).",
            risk="low",
        )
    if rk == "ops":
        return build_decision_summary(
            agent_key="ops",
            action="ops_action",
            tool="ops",
            reason=R_OPS,
            risk="low",
        )
    if rk in ("developer", "dev", "dev_executor") and (
        t.startswith("/") or t.lower().strip().startswith("/dev")
    ):
        return build_decision_summary(
            agent_key="developer",
            action="dev_job",
            tool="aider",
            reason=R_CODE_CHANGE,
            risk="normal",
            approval_required=True,
        )
    if t.strip().startswith("/") or t.strip().startswith("@"):
        return build_decision_summary(
            agent_key=rk,
            action="command",
            tool="local_state",
            reason=R_COMMAND,
            risk="low",
        )
    if _has_url(t) and (rk == "research" or "research" in t.lower()):
        return build_decision_summary(
            agent_key="research",
            action="public_url_summary",
            tool="public_web_reader",
            reason=R_PUBLIC_URL,
            risk="low",
        )
    if rk == "research":
        return build_decision_summary(
            agent_key="research",
            action="web_search_summary",
            tool="web_search",
            reason=R_RESEARCH,
            risk="low",
        )
    return build_decision_summary(
        agent_key=rk,
        action="chat_response",
        tool="llm" if (intent or "") not in ("", "unknown") else "llm",
        reason=R_CHAT,
        intent=intent,
        risk="low",
    )


def decision_for_dev_job(
    *,
    job: Any,
    project_tool: str | None = "aider",
) -> dict[str, Any]:
    rsk = (getattr(job, "risk_level", None) or "normal") or "normal"
    ap = bool(getattr(job, "approval_required", False) or (getattr(job, "status", None) in ("needs_approval", "needs_risk_approval")))
    st = (getattr(job, "status", None) or "").strip()
    if st == "needs_risk_approval":
        rsk = "high"
    return build_decision_summary(
        agent_key="developer",
        action="dev_job",
        tool=(project_tool or "aider")[:64],
        reason=R_CODE_CHANGE,
        risk=_norm_risk(rsk) if rsk in ("low", "medium", "high", "normal") else "normal",
        approval_required=ap,
    )


def decision_for_web_explicit(
    mention_intent: str | None,
    agent_key: str | None,
    user_text: str,
    job: Any | None,
) -> dict[str, Any]:
    """
    `mention_intent` = ExplicitMentionResult.intent (e.g. dev_command, ops_mention).
    """
    mk = (agent_key or "aethos").lower().strip() or "aethos"
    mi = (mention_intent or "").strip() or "general_chat"
    if mi == "dev_command" and job is not None:
        return decision_for_dev_job(job=job)
    if mi in ("dev_command", "dev_mention", "dev_error"):
        if job is not None:
            return decision_for_dev_job(job=job)
        return build_decision_summary(
            agent_key="developer",
            action="dev_job",
            tool="aider",
            reason=R_CODE_CHANGE,
            risk="normal",
            approval_required=True,
        )
    if mi == "ops_mention" or mk == "ops":
        return build_decision_summary(
            agent_key="ops",
            action="ops_action",
            tool="ops",
            reason=R_OPS,
            risk="low",
        )
    if mi in ("dev_status",):
        return build_decision_summary(
            agent_key="developer",
            action="dev_status",
            tool="local_state",
            reason=R_DETERMINISTIC_TOOL,
            risk="low",
        )
    if mi in ("dev_create_project", "idea_workflow", "dev_create"):
        return build_decision_summary(
            agent_key=mk,
            action=mi,
            tool="local_state",
            reason=R_DETERMINISTIC_TOOL,
            risk="low",
        )
    if mk == "research" or "research" in mi:
        return build_decision_summary(
            agent_key="research",
            action="web_search_summary",
            tool="web_search",
            reason=R_RESEARCH,
            risk="low",
        )
    return build_decision_summary(
        agent_key=mk,
        action="tool_only" if "workflow" in mi else "chat_response",
        tool="local_state" if "workflow" in mi or "general" not in mi else "llm",
        reason=R_CHAT if "general" in mi else R_DETERMINISTIC_TOOL,
        risk="low",
    )


def build_decision_for_telegram_turn(
    *,
    user_text: str,
    intent: str | None,
    agent_key: str,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`extras` may include: `job` (orm object), `mention_intent` (if explicit path)."""
    ex = dict(extras or {})
    if ex.get("job") is not None:
        return decision_for_dev_job(job=ex["job"], project_tool=ex.get("project_tool"))
    mi = ex.get("mention_intent") or ex.get("m_intent")
    if mi:
        return decision_for_web_explicit(str(mi or ""), agent_key, user_text, ex.get("job"))
    u = (user_text or "").strip()
    rkind = (ex.get("response_kind") or "").strip() or None
    return infer_decision_for_web_main(
        user_text=u,
        routed_agent_key=agent_key,
        intent=intent,
        response_kind=rkind,
    )


def format_decision_for_telegram_why(decision: dict[str, Any] | None) -> str:
    """Multi-line /why (plain text, no HTML)."""
    if not decision:
        return "I don’t have a recent decision to explain yet."
    a = (decision.get("agent") or "aethos").title()
    tool = decision.get("tool") or "—"
    tlabel = (tool or "—").replace("_", " ").title() if (tool and tool != "—") else "—"
    r = (decision.get("reason") or "—")[:2000]
    rsk = (decision.get("risk") or "low").title()
    ap = bool(decision.get("approval_required", False))
    al = "Required" if ap else "Not required"
    lines = [
        "Last AethOS decision:",
        f"• Agent: {a}",
        f"• Tool: {tlabel}",
        f"• Reason: {r}",
        f"• Risk: {rsk}",
        f"• Approval: {al}",
    ]
    return "\n".join(lines)[:3900]


def collapsed_summary_line(d: dict[str, Any] | None) -> str:
    """One line for web collapsed row."""
    if not d:
        return ""
    a = (d.get("agent") or "aethos").title()
    t = (d.get("tool") or "").replace("_", " ") or "—"
    rsk = (d.get("risk") or "low").title()
    return f"{a} · {t} · {rsk} risk"
