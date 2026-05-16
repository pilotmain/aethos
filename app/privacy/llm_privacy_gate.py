# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Apply Phase 2 privacy / egress / redaction before external LLM provider calls."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Any

from app.core.config import Settings, get_settings
from app.privacy.egress_guard import EgressBlocked, evaluate_egress
from app.privacy.message_text import flatten_messages_for_pii
from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text
from app.privacy.privacy_events import PrivacyEventType, emit_privacy_event
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode
from app.privacy.redaction_policy import should_redact_for_external_model
from app.services.llm.base import Message

_RECENT_LLM_PRIVACY: deque[dict[str, Any]] = deque(maxlen=32)


def recent_llm_privacy_decisions(*, limit: int = 12) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 32))
    return list(_RECENT_LLM_PRIVACY)[:lim]


def _is_local_provider(name: str) -> bool:
    return (name or "").strip().lower() == "ollama"


def _redact_message_list(messages: list[Message]) -> tuple[list[Message], int]:
    out: list[Message] = []
    redactions = 0
    for m in messages:
        c = m.content
        if isinstance(c, str):
            r = redact_text(c)
            if r != c:
                redactions += 1
            out.append(replace(m, content=r))
        elif isinstance(c, list):
            new_blocks: list[dict[str, Any]] = []
            changed = False
            for block in c:
                if isinstance(block, dict) and str(block.get("type") or "") == "text":
                    t = str(block.get("text") or "")
                    r = redact_text(t)
                    if r != t:
                        changed = True
                        redactions += 1
                    nb = dict(block)
                    nb["text"] = r
                    new_blocks.append(nb)
                else:
                    new_blocks.append(block)  # type: ignore[arg-type]
            out.append(replace(m, content=new_blocks) if changed else m)
        else:
            out.append(m)
    return out, redactions


def apply_llm_privacy_gate(
    messages: list[Message],
    *,
    provider_name: str,
    model_id: str | None,
    settings: Settings | None = None,
) -> tuple[list[Message], dict[str, Any]]:
    """
    Enforce privacy on outbound LLM payloads.

    Returns possibly redacted messages plus routing metadata (safe for logs / MC).
    Raises :class:`~app.privacy.egress_guard.EgressBlocked` when block policy applies.
    """
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    pname = (provider_name or "").strip().lower() or "unknown"
    external = not _is_local_provider(pname)

    flat = flatten_messages_for_pii(messages)
    matches = detect_pii(flat)
    cats = sorted({m.category for m in matches})

    meta: dict[str, Any] = {
        "provider": pname,
        "model": (model_id or "").strip() or None,
        "privacy_mode": mode.value,
        "pii_categories": cats,
        "redactions_applied": 0,
        "local_first": bool(getattr(s, "aethos_local_first_enabled", False) or getattr(s, "nexa_local_first", False)),
        "egress_allowed": True,
        "fallback_used": False,
        "routing_decision": "route_local" if not external else "route_external",
    }

    if mode == PrivacyMode.OFF:
        _RECENT_LLM_PRIVACY.appendleft(meta)
        return messages, meta

    if cats:
        emit_privacy_event(
            PrivacyEventType.PII_DETECTED,
            details={"boundary": "llm", "categories": cats, "count": len(matches), "provider": pname},
        )

    if external and cats:
        ok, reason = evaluate_egress(s, "llm", pii_categories=cats)
        meta["egress_allowed"] = bool(ok)
        if not ok:
            primary_cat = cats[0] if cats else "unknown"
            payload = {
                "error": "privacy_egress_blocked",
                "reason": f"PII categories present on outbound LLM request ({reason})",
                "category": primary_cat,
                "mode": mode.value,
                "provider": pname,
            }
            raise EgressBlocked(payload["reason"], payload=payload)

    out_msgs = messages
    if external and cats and should_redact_for_external_model(s):
        out_msgs, nred = _redact_message_list(messages)
        meta["redactions_applied"] = int(nred)
        meta["routing_decision"] = "route_external_redacted" if nred else "route_external"
        if nred:
            emit_privacy_event(
                PrivacyEventType.PII_REDACTED,
                details={"boundary": "llm", "provider": pname, "redactions": nred, "categories": cats},
            )
    elif not external and cats and mode == PrivacyMode.REDACT:
        out_msgs, nred = _redact_message_list(messages)
        meta["redactions_applied"] = int(nred)
        meta["routing_decision"] = "route_local_redacted" if nred else "route_local"
        if nred:
            emit_privacy_event(
                PrivacyEventType.PII_REDACTED,
                details={"boundary": "llm", "provider": pname, "redactions": nred, "categories": cats},
            )

    _RECENT_LLM_PRIVACY.appendleft(dict(meta))
    return out_msgs, meta


def evaluate_text_egress(
    text: str,
    *,
    boundary: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Structured egress evaluation for arbitrary text (API / tooling)."""
    s = settings or get_settings()
    mode = current_privacy_mode(s)
    matches = detect_pii(text or "")
    cats = sorted({m.category for m in matches})
    ok, reason = evaluate_egress(s, boundary, pii_categories=cats)
    return {
        "privacy_mode": mode.value,
        "allowed": bool(ok),
        "reason": reason,
        "pii_categories": cats,
        "count": len(matches),
        "matches": [m.as_public_dict() for m in matches],
    }
