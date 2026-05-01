"""In-memory per-channel and per-user outbound pacing (Phase 12)."""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)


class GatewayRateLimitExceeded(Exception):
    """Raised when an outbound send would exceed configured limits."""

    pass


# Minimum seconds between any two outbound calls for that logical channel (global pacing).
CHANNEL_MIN_INTERVAL_SEC: dict[str, float] = {
    "slack": 1.0,
    "sms": 0.5,
    "whatsapp": 0.35,
    "email": 0.5,
    "apple_messages": 0.5,
}

USER_WINDOW_SEC = 60.0
USER_MAX_PER_WINDOW = 60

_lock = Lock()
_channel_last_mono: dict[str, float] = {}
_user_events: dict[str, deque[float]] = {}


def acquire_outbound_slot(*, channel: str, user_id: str | None = None) -> None:
    """
    Reserve an outbound slot or raise :exc:`GatewayRateLimitExceeded`.

    * Per-channel minimum spacing (provider-safe pacing).
    * Per user_id + channel sliding window (spam / runaway agent guard).
    """
    now = time.monotonic()
    interval = CHANNEL_MIN_INTERVAL_SEC.get(channel, 0.25)
    with _lock:
        last = _channel_last_mono.get(channel, 0.0)
        if now - last < interval:
            logger.warning(
                "channel_gateway.rate_limit channel=%s reason=channel_pacing interval=%s",
                channel,
                interval,
            )
            raise GatewayRateLimitExceeded(f"channel {channel} outbound pacing")

        if user_id:
            key = f"{channel}:{user_id}"
            dq = _user_events.setdefault(key, deque())
            cutoff = now - USER_WINDOW_SEC
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= USER_MAX_PER_WINDOW:
                logger.warning(
                    "channel_gateway.rate_limit channel=%s user_id=%s… reason=user_burst",
                    channel,
                    (user_id or "")[:16],
                )
                raise GatewayRateLimitExceeded(f"user burst on {channel}")
            dq.append(now)

        _channel_last_mono[channel] = now


def reset_limits_for_tests() -> None:
    with _lock:
        _channel_last_mono.clear()
        _user_events.clear()
