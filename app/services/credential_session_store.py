"""
Non-secret session markers after credential *guidance* was shown in chat.

**Does not store API keys or tokens** — only dedupes UX so repeat pastes get a shorter
acknowledgment in the same process lifetime. Secrets belong in the worker env / vault only.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
# key -> monotonic timestamp when guidance was last shown
_last_guidance_mono: dict[str, float] = {}
_DEFAULT_WINDOW_SEC = 3600.0


def _key(user_id: str, tag: str) -> str:
    return f"{(user_id or '').strip()}:{(tag or 'default').strip()}"


def was_credential_guidance_recent(
    user_id: str,
    tag: str,
    *,
    window_sec: float = _DEFAULT_WINDOW_SEC,
) -> bool:
    """True if we already showed full secure-setup copy for this user+tag recently."""
    k = _key(user_id, tag)
    with _lock:
        ts = _last_guidance_mono.get(k)
    if ts is None:
        return False
    return (time.monotonic() - ts) <= window_sec


def mark_credential_guidance_shown(user_id: str, tag: str) -> None:
    """Record that full guidance was shown (timestamp only)."""
    k = _key(user_id, tag)
    with _lock:
        _last_guidance_mono[k] = time.monotonic()
        if len(_last_guidance_mono) > 10_000:
            # crude cap — drop stale half
            cutoff = time.monotonic() - _DEFAULT_WINDOW_SEC * 2
            for kk in list(_last_guidance_mono.keys()):
                if _last_guidance_mono[kk] < cutoff:
                    del _last_guidance_mono[kk]


__all__ = [
    "mark_credential_guidance_shown",
    "was_credential_guidance_recent",
]
