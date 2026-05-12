# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Retry/backoff helpers for argv/subprocess paths (distinct from Phase 73 agent Genesis Loop)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    CONSTANT = "constant"


@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0


def retry_delay_seconds(attempt_index: int, config: RetryConfig) -> float:
    """Delay before retry ``attempt_index`` (0-based), after a failed attempt."""
    if attempt_index <= 0:
        return 0.0
    prev = attempt_index - 1
    if config.strategy == RetryStrategy.EXPONENTIAL:
        return float(config.base_delay * (config.backoff_factor**prev))
    if config.strategy == RetryStrategy.LINEAR:
        return float(config.base_delay * attempt_index)
    return float(config.base_delay)


def retry_config_from_settings() -> RetryConfig:
    from app.core.config import get_settings

    s = get_settings()
    raw = str(getattr(s, "nexa_retry_strategy", "exponential") or "exponential").lower().strip()
    try:
        strat = RetryStrategy(raw)
    except ValueError:
        strat = RetryStrategy.EXPONENTIAL
    attempts = max(1, min(10, int(getattr(s, "nexa_host_command_max_attempts", 3) or 3)))
    return RetryConfig(max_attempts=attempts, strategy=strat)


def is_success_dict(result: Any) -> bool:
    if isinstance(result, dict):
        return bool(result.get("success"))
    return True


class SelfHealingExecutor:
    """Generic async retry wrapper (optional fallback)."""

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        args: tuple[Any, ...],
        *,
        retry_config: RetryConfig | None = None,
        fallback_func: Callable[..., Awaitable[Any]] | None = None,
    ) -> Any:
        config = retry_config or RetryConfig()
        last_error: BaseException | None = None
        for attempt in range(config.max_attempts):
            try:
                result = await func(*args)
                if is_success_dict(result):
                    return result
            except Exception as exc:
                last_error = exc
                logger.warning("retry attempt %s failed: %s", attempt + 1, exc)
            if attempt < config.max_attempts - 1:
                delay = retry_delay_seconds(attempt + 1, config)
                await asyncio.sleep(delay)
        if fallback_func is not None:
            return await fallback_func(*args)
        return {"success": False, "error": str(last_error) if last_error else "failed"}


def execute_sync_with_retries(
    fn: Callable[[], T],
    *,
    should_retry: Callable[[T], bool],
    config: RetryConfig | None = None,
) -> T:
    """Run ``fn`` until success or attempts exhausted (blocking)."""
    cfg = config or retry_config_from_settings()
    last: T | None = None
    for attempt in range(cfg.max_attempts):
        last = fn()
        if not should_retry(last):
            return last
        if attempt < cfg.max_attempts - 1:
            delay = retry_delay_seconds(attempt + 1, cfg)
            if delay > 0:
                time.sleep(delay)
    assert last is not None
    return last


__all__ = [
    "RetryConfig",
    "RetryStrategy",
    "SelfHealingExecutor",
    "execute_sync_with_retries",
    "is_success_dict",
    "retry_config_from_settings",
    "retry_delay_seconds",
]
