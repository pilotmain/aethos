"""
Legacy hook after operator CLI verification.

Previously appended a long “what we did not do” block; that hurt UX. Callers should
rely on :func:`append_verify_vs_mutate_followup` as a no-op for compatibility.
Mutations (e.g. README + push) are queued from :mod:`app.services.operator_execution_loop`
when appropriate instead of lecturing the user.
"""

from __future__ import annotations


def append_verify_vs_mutate_followup(body: str, *, verified: bool, provider_label: str) -> str:
    """Return ``body`` unchanged (verification copy is handled elsewhere)."""
    del verified, provider_label
    return body
