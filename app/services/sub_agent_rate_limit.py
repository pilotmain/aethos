"""
In-memory rate limits for sub-agent execution (Week 5, single API worker).

For multi-replica / HA, replace with a shared store (e.g. Redis).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class _Window:
    max_calls: int
    window_seconds: int


class AgentRateLimiter:
    """Rolling window per key. Check before work; record only after success."""

    def __init__(self) -> None:
        self._calls: dict[str, list[float]] = defaultdict(list)

    def reset(self) -> None:
        self._calls.clear()

    def _prune(self, key: str, window_seconds: int) -> None:
        now = time.monotonic()
        self._calls[key] = [t for t in self._calls[key] if now - t < window_seconds]

    def _over_limit(self, key: str, w: _Window) -> bool:
        self._prune(key, w.window_seconds)
        return len(self._calls[key]) >= w.max_calls

    def _record(self, key: str) -> None:
        self._calls[key].append(time.monotonic())

    def check(self, agent_id: str, domain: str, chat_id: str) -> tuple[bool, str | None]:
        s = get_settings()
        w = int(max(1, int(getattr(s, "nexa_agent_rate_limit_window_seconds", 60))))
        lim_agent = _Window(
            max_calls=max(1, int(getattr(s, "nexa_agent_rate_limit_per_agent", 30))), window_seconds=w
        )
        lim_chat = _Window(
            max_calls=max(1, int(getattr(s, "nexa_agent_rate_limit_per_chat", 80))), window_seconds=w
        )
        lim_domain = _Window(
            max_calls=max(1, int(getattr(s, "nexa_agent_rate_limit_per_domain", 40))), window_seconds=w
        )

        checks: list[tuple[str, _Window, str]] = [
            (f"agent:{agent_id}", lim_agent, "agent"),
            (f"chat:{chat_id}", lim_chat, "chat"),
            (f"domain:{domain}", lim_domain, "domain"),
        ]
        for key, lim, label in checks:
            if self._over_limit(key, lim):
                logger.warning(
                    "sub_agent rate_limited %s",
                    label,
                    extra={
                        "nexa_event": "agent_rate_limited",
                        "limit_type": label,
                        "agent_id": agent_id,
                        "chat_id": chat_id,
                        "domain": domain,
                    },
                )
                return (
                    False,
                    f"Rate limit exceeded for {label} (max {lim.max_calls} per {lim.window_seconds}s).",
                )
        return True, None

    def record(self, agent_id: str, domain: str, chat_id: str) -> None:
        for key in (f"agent:{agent_id}", f"chat:{chat_id}", f"domain:{domain}"):
            self._record(key)


_rate_limiter = AgentRateLimiter()


def check_rate_limits(agent_id: str, domain: str, chat_id: str) -> tuple[bool, str | None]:
    return _rate_limiter.check(agent_id, domain, chat_id)


def record_rate_limited_action(agent_id: str, domain: str, chat_id: str) -> None:
    _rate_limiter.record(agent_id, domain, chat_id)


def reset_rate_limiter_for_tests() -> None:
    _rate_limiter.reset()


__all__ = [
    "AgentRateLimiter",
    "check_rate_limits",
    "record_rate_limited_action",
    "reset_rate_limiter_for_tests",
]
