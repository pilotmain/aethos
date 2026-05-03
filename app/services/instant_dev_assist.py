"""Phase 50 — instant dev assist: classify context, outline fix path, gate execution tone."""

from __future__ import annotations

from typing import Any

from app.services.context_awareness import detect_infra_context, detect_stack_tags
from app.services.execution_policy import assess_interaction_risk, should_auto_execute


def instant_dev_assist(user_text: str) -> dict[str, Any]:
    """
    Deterministic assist bundle for dev/snag messages.

    Does not run shell or queue jobs — surfaces structured hints for the reply layer.
    """
    raw = (user_text or "").strip()
    stack = detect_stack_tags(raw)
    infra = detect_infra_context(raw)
    risk = assess_interaction_risk(raw)
    tags = stack + [x for x in infra if x not in stack]
    fix_outline = _default_fix_outline(stack, infra, risk)
    return {
        "stack_tags": stack,
        "infra_tags": infra,
        "risk": risk,
        "combined_tags": tags,
        "fix_outline": fix_outline,
    }


def _default_fix_outline(stack: list[str], infra: list[str], risk: str) -> list[str]:
    lines: list[str] = []
    if risk == "high":
        lines.append("Confirm scope and environment before changing anything destructive.")
    if any("Kubernetes" in x or "EKS" in x for x in infra):
        lines.append("Check pod events, image tag, and ingress/backend health for the failing service.")
    if any("Docker" in x for x in infra) and not lines:
        lines.append("Reproduce with the same image tag locally; inspect build logs and layer cache.")
    if any("OIDC" in x or "OAuth" in x for x in infra):
        lines.append("Verify redirect URI, client secret rotation, and clock skew on the issuer.")
    if any("Mongo" in x for x in infra):
        lines.append("Validate connection string, replica set name, and TLS settings.")
    if any("TypeScript" in x or "Python" in x for x in stack):
        lines.append("Isolate the failing module with the smallest repro command (test or typecheck).")
    if not lines:
        lines.append("Capture the exact command + first error block; bisect what changed last.")
    return lines[:4]


def format_assist_appendix(*, user_text: str, intent: str) -> str | None:
    """
    Short appendix for gateway replies — identity-clean, action-first phrasing.

    Returns None when this layer has nothing to add.
    """
    from app.services.execution_trigger import should_merge_phase50_assist

    if not should_merge_phase50_assist(intent):
        return None
    if intent not in ("stuck_dev", "analysis"):
        return None
    bundle = instant_dev_assist(user_text)
    risk = bundle["risk"]
    tags = bundle["combined_tags"][:6]
    outline = bundle["fix_outline"][:3]
    auto = should_auto_execute(intent, risk)

    parts: list[str] = []
    if risk == "high":
        parts.append(
            "**Risk:** this looks like production or destructive scope — confirm before executing changes."
        )
    elif risk == "medium":
        parts.append("**Scope:** medium-impact change — worth a quick review before applying.")

    if tags:
        parts.append("**Context:** " + " · ".join(tags))

    if outline:
        parts.append("**Likely checks:**\n" + "\n".join(f"• {o}" for o in outline))

    if auto:
        parts.append("_If your workspace is connected in Mission Control, Nexa can run this investigation on the repo._")
    else:
        parts.append("_Add the exact error snippet if you want a sharper read._")

    return "\n\n".join(parts) if parts else None


__all__ = ["format_assist_appendix", "instant_dev_assist"]
