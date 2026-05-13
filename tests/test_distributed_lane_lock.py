# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Distributed lane locks (Redis) + session queue integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.services import distributed_lock
from app.services.session_queue import SessionQueueManager


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    monkeypatch.delenv("NEXA_USE_DISTRIBUTED_QUEUE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


def test_session_queue_redis_path_uses_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_USE_DISTRIBUTED_QUEUE", "true")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    get_settings.cache_clear()
    distributed_lock.reset_distributed_lane_redis_clients()

    mock_redis = MagicMock()
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_redis.lock.return_value = mock_lock

    with patch.object(distributed_lock, "_get_client", return_value=mock_redis):
        mgr = SessionQueueManager()
        with mgr.acquire("web:u1:ws1"):
            pass

    mock_redis.lock.assert_called_once()
    assert mock_redis.lock.call_args[0][0] == "nexa:lane:web:u1:ws1"
    mock_lock.release.assert_called_once()


def test_session_queue_timeout_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_USE_DISTRIBUTED_QUEUE", "true")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    get_settings.cache_clear()

    class _Busy:
        def __enter__(self) -> None:
            raise TimeoutError("busy")

        def __exit__(self, *_a: object) -> bool:
            return False

    with patch.object(distributed_lock, "lane_lock_acquire", lambda *_a, **_k: _Busy()):
        mgr = SessionQueueManager()
        with pytest.raises(TimeoutError):
            with mgr.acquire("lane-x"):
                pass


def test_session_queue_falls_back_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_USE_DISTRIBUTED_QUEUE", "true")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    get_settings.cache_clear()

    with patch.object(distributed_lock, "_get_client", return_value=None):
        mgr = SessionQueueManager()
        with mgr.acquire("fallback-lane"):
            assert True
