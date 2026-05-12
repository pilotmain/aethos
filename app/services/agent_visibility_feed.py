# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Per-user queued banners when orchestration sub-agents are spawned (next gateway reply)."""

from __future__ import annotations

from collections import deque

_MAX_PER_USER = 24


_queues: dict[str, deque[str]] = {}


def push_agent_spawn_notice(
    user_id: str,
    *,
    agent_name: str,
    domain: str,
    agent_id: str,
) -> None:
    """Queue a one-shot banner for the owner's next gateway interaction."""
    uid = (user_id or "").strip()[:64]
    if not uid:
        return
    msg = (
        f"🆕 New agent created: **@{agent_name}** ({domain}) · id `{agent_id}`\n\n"
        f"💡 You can say: `@{agent_name} <task>` or \"ask {agent_name} to …\""
    )
    q = _queues.setdefault(uid, deque(maxlen=_MAX_PER_USER))
    q.append(msg)


def drain_user_visibility_banner(user_id: str) -> str | None:
    """Drain all pending banners for this user (FIFO). Returns joined text or None."""
    uid = (user_id or "").strip()[:64]
    if not uid or uid not in _queues:
        return None
    q = _queues[uid]
    if not q:
        return None
    parts: list[str] = []
    while q:
        parts.append(q.popleft())
    return "\n\n".join(parts).strip() if parts else None


def clear_visibility_feed_for_tests() -> None:
    """Test helper."""
    _queues.clear()


__all__ = [
    "clear_visibility_feed_for_tests",
    "drain_user_visibility_banner",
    "push_agent_spawn_notice",
]
