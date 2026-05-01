"""Ingress for outbound payloads — worker dict gate + legacy string gate for providers."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.mission_control.nexa_next_state import add_privacy_event
from app.services.privacy_firewall.audit import log_event
from app.services.privacy_firewall.detectors import detect_sensitive_data, detect_sensitive_segments
from app.services.privacy_firewall.redactor import redact_common_secrets, redact_sensitive_data


class PrivacyBlockedError(RuntimeError):
    """Raised when outbound payload must not proceed (e.g. API key detected)."""


def prepare_external_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Mandatory gate before tool execution / external bodies — dict in, sanitized dict out.

    Raises :exc:`PrivacyBlockedError` when secret-shaped material is detected.
    """
    text = str(payload)
    findings = detect_sensitive_data(text)

    if findings["secrets"]:
        ev = {"type": "secret_blocked", "data": findings}
        log_event(ev)
        add_privacy_event(ev)
        raise PrivacyBlockedError("Blocked: secret detected")

    if findings["pii"]:
        ev = {"type": "pii_redacted", "data": findings}
        log_event(ev)
        add_privacy_event(ev)
        return redact_sensitive_data(payload)

    return payload


def prepare_external_text(text: str, *, user_id: str | None = None, purpose: str = "llm") -> dict[str, Any]:
    """
    Legacy string-body gate for OpenAI / Anthropic / remote HTTP (settings-aware).
    """
    s = get_settings()
    if not s.nexa_privacy_firewall_enabled:
        return {"allowed": True, "body": text, "skipped": True, "purpose": purpose}

    hits = detect_sensitive_segments(text)
    body, n_red = redact_common_secrets(text)
    blocked = bool(s.nexa_block_secrets_to_external_api and hits)

    safe_body = body if s.nexa_redact_pii_before_external_api else text
    out: dict[str, Any] = {
        "allowed": not blocked,
        "body": "" if blocked else safe_body,
        "redactions": n_red,
        "hits": [{"kind": h.kind} for h in hits],
        "purpose": purpose,
        "user_id_prefix": (user_id or "")[:16],
    }
    if blocked:
        out["reason"] = "blocked_secret_or_pii_pattern"
    return out
