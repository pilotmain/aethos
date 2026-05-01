"""Redact dev command output for persistence; gate outbound dicts through the privacy firewall."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload
from app.services.privacy_firewall.redactor import redact_common_secrets

_RE_SK = re.compile(r"sk-[A-Za-z0-9]{8,}")


def redact_output_for_storage(text: str, *, max_chars: int = 200_000) -> str:
    """Best-effort secret redaction for DB rows (does not raise on secret shape — redacts)."""
    raw = (text or "")[:max_chars]
    redacted, _n = redact_common_secrets(raw)
    redacted = _RE_SK.sub("[REDACTED_KEY]", redacted)
    return redacted


def gate_outbound_dev_payload(
    payload: dict[str, object],
    *,
    db: Session | None,
    user_id: str | None,
) -> dict[str, object]:
    """
    Call before any external provider sees dev logs/diffs/output.

    Raises :exc:`PrivacyBlockedError` when secret-shaped material is present.
    """
    return prepare_external_payload(payload, pii_policy="redact", db=db, user_id=user_id)


def gate_agent_context_before_external(
    adapter_name: str,
    context: dict[str, object],
    *,
    db: Session | None,
    user_id: str | None,
) -> dict[str, object]:
    """
    Scan coding-agent context (diffs, logs, env-shaped strings) before remote/local-tool adapters run.

    Local stub skips the strict outbound gate to preserve offline ergonomics.
    """
    if (adapter_name or "").strip().lower() in ("", "local_stub"):
        return context
    out = gate_outbound_dev_payload({"ctx": dict(context)}, db=db, user_id=user_id)
    inner = out.get("ctx")
    return dict(inner) if isinstance(inner, dict) else dict(context)


__all__ = [
    "redact_output_for_storage",
    "gate_outbound_dev_payload",
    "gate_agent_context_before_external",
    "PrivacyBlockedError",
]
