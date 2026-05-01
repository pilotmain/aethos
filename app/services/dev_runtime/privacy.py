"""Redact dev command output for persistence; gate outbound dicts through the privacy firewall."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload
from app.services.privacy_firewall.redactor import redact_common_secrets

_RE_SK = re.compile(r"sk-[A-Za-z0-9]{8,}")

# Phase 38 — strict caps before anything remote sees logs/diffs
_MAX_LOG_CHARS = 8000
_MAX_DIFF_CHARS = 12000
_MAX_FILES_LIST = 100
_MAX_MEMORY_SNIPPETS = 5


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


def minimize_dev_context(context: dict[str, Any]) -> dict[str, Any]:
    """
    Shrink dev payloads before external adapters: truncate logs/diffs, bound file lists and memory.

    Does not remove secrets by itself — combine with :func:`gate_outbound_dev_payload`.
    """
    out: dict[str, Any] = {}
    for k, v in (context or {}).items():
        lk = str(k)
        if lk in ("log", "logs", "stdout", "stderr", "test_output", "tests_output"):
            s = str(v or "")
            out[lk] = s[:_MAX_LOG_CHARS] + ("…" if len(s) > _MAX_LOG_CHARS else "")
        elif lk in ("diff", "git_diff", "patch"):
            if isinstance(v, dict):
                prev = str((v or {}).get("diff_preview") or "")
                out[lk] = {
                    **v,
                    "diff_preview": prev[:_MAX_DIFF_CHARS] + ("…" if len(prev) > _MAX_DIFF_CHARS else ""),
                }
            else:
                s = str(v or "")
                out[lk] = s[:_MAX_DIFF_CHARS] + ("…" if len(s) > _MAX_DIFF_CHARS else "")
        elif lk in ("files", "changed_files", "paths"):
            if isinstance(v, (list, tuple)):
                lst = [str(x) for x in v][: _MAX_FILES_LIST]
                out[lk] = lst
            else:
                out[lk] = v
        elif lk in ("memory", "memory_snippets"):
            if isinstance(v, list):
                out[lk] = [str(x)[:4000] for x in v[:_MAX_MEMORY_SNIPPETS]]
            else:
                out[lk] = v
        else:
            out[lk] = v
    return out


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
    trimmed = minimize_dev_context(dict(context))
    if (adapter_name or "").strip().lower() in ("", "local_stub"):
        return trimmed
    out = gate_outbound_dev_payload({"ctx": trimmed}, db=db, user_id=user_id)
    inner = out.get("ctx")
    return dict(inner) if isinstance(inner, dict) else trimmed


__all__ = [
    "redact_output_for_storage",
    "gate_outbound_dev_payload",
    "gate_agent_context_before_external",
    "minimize_dev_context",
    "PrivacyBlockedError",
]
