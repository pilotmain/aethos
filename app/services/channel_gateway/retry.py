# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Exponential backoff retry for outbound gateway sends only (Phase 12)."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from app.services.channel_gateway.gateway_events import record_outbound_failure, record_outbound_success

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SEC = 0.5


def outbound_with_retry(
    *,
    channel: str,
    operation: str,
    func: Callable[[], T],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SEC,
) -> T:
    """
    Run ``func`` with exponential backoff on failure.

    Does not retry permission approvals — only wrap raw outbound transport calls.
    Logs each failure; records terminal success/failure via :mod:`gateway_events`.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
            record_outbound_success(channel)
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "channel_gateway.outbound_retry channel=%s operation=%s attempt=%s/%s error=%s",
                channel,
                operation,
                attempt,
                max_attempts,
                exc,
                exc_info=attempt == max_attempts,
            )
            if attempt >= max_attempts:
                break
            # Full jitter would be overkill; small jitter avoids thundering herd.
            delay = base_delay_seconds * (2 ** (attempt - 1))
            delay *= 0.9 + 0.2 * random.random()
            time.sleep(delay)
    assert last_exc is not None
    record_outbound_failure(channel, str(last_exc))
    raise last_exc
