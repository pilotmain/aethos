# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
In-process session credential cache + UX dedup for credential guidance.

When ``nexa_operator_session_credential_reuse`` is enabled, short-lived secrets may be held in
RAM **only for this API process** so bounded CLI probes can authenticate without repeated chat
prompts. Values are **never logged**, never echoed in replies, and never leave the worker except
via explicit subprocess env passed to allowlisted CLI calls.

Guidance timestamps remain separate — no secrets.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_last_guidance_mono: dict[str, float] = {}
_DEFAULT_WINDOW_SEC = 3600.0

_credential_values: dict[str, str] = {}


def _guidance_key(user_id: str, tag: str) -> str:
    return f"{(user_id or '').strip()}:{(tag or 'default').strip()}"


def _cred_key(user_id: str, provider: str, key_type: str) -> str:
    return f"{(user_id or '').strip().lower()}:{(provider or '').strip().lower()}:{(key_type or '').strip().lower()}"


class CredentialSessionStore:
    """Per-process in-memory store keyed by user + provider + key type."""

    def __init__(self) -> None:
        self._values: dict[str, str] = _credential_values
        self._lock = _lock

    def store(self, user_id: str, provider: str, key_type: str, value: str) -> None:
        """Persist value in RAM only — never log ``value``."""
        uid = (user_id or "").strip()
        if not uid or not (value or "").strip():
            return
        k = _cred_key(uid, provider, key_type)
        with self._lock:
            self._values[k] = value.strip()
            if len(self._values) > 50_000:
                # crude cap — drop oldest half by arbitrary key order
                for kk in list(self._values.keys())[:25_000]:
                    self._values.pop(kk, None)

    def get(self, user_id: str, provider: str, key_type: str) -> str | None:
        k = _cred_key(user_id, provider, key_type)
        with self._lock:
            v = self._values.get(k)
        return v if v else None

    def has_provider(self, user_id: str, provider: str) -> bool:
        uid = (user_id or "").strip().lower()
        pfx = f"{uid}:{(provider or '').strip().lower()}:"
        with self._lock:
            return any(k.startswith(pfx) for k in self._values.keys())


def get_session_railway_token(user_id: str) -> str | None:
    """Return stored Railway token for this user, if any (never logged)."""
    return credential_session_store.get(user_id, "railway", "railway_token")


# Singleton used across gateway / runners.
credential_session_store = CredentialSessionStore()


def was_credential_guidance_recent(
    user_id: str,
    tag: str,
    *,
    window_sec: float = _DEFAULT_WINDOW_SEC,
) -> bool:
    """True if we already showed full secure-setup copy for this user+tag recently."""
    k = _guidance_key(user_id, tag)
    with _lock:
        ts = _last_guidance_mono.get(k)
    if ts is None:
        return False
    return (time.monotonic() - ts) <= window_sec


def mark_credential_guidance_shown(user_id: str, tag: str) -> None:
    """Record that full guidance was shown (timestamp only)."""
    k = _guidance_key(user_id, tag)
    with _lock:
        _last_guidance_mono[k] = time.monotonic()
        if len(_last_guidance_mono) > 10_000:
            cutoff = time.monotonic() - _DEFAULT_WINDOW_SEC * 2
            for kk in list(_last_guidance_mono.keys()):
                if _last_guidance_mono[kk] < cutoff:
                    del _last_guidance_mono[kk]


__all__ = [
    "CredentialSessionStore",
    "credential_session_store",
    "get_session_railway_token",
    "mark_credential_guidance_shown",
    "was_credential_guidance_recent",
]
