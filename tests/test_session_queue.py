# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lane queue (per-session gateway serialization)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.services.gateway.context import GatewayContext
from app.services.session_queue import SessionQueueManager, gateway_lane_id, session_queue


def test_session_queue_serializes_same_lane() -> None:
    m = SessionQueueManager()
    lane = "test:lane:1"
    depth = {"cur": 0, "peak": 0}

    def work(_i: int) -> None:
        with m.acquire(lane):
            depth["cur"] += 1
            depth["peak"] = max(depth["peak"], depth["cur"])
            time.sleep(0.02)
            depth["cur"] -= 1

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, range(16)))
    assert depth["peak"] == 1


def test_session_queue_different_lanes_can_overlap() -> None:
    m = SessionQueueManager()
    peak = {"v": 0, "cur": 0}
    barrier = threading.Barrier(3)

    def work(lane: str) -> None:
        barrier.wait()
        with m.acquire(lane):
            peak["cur"] += 1
            peak["v"] = max(peak["v"], peak["cur"])
            time.sleep(0.04)
            peak["cur"] -= 1

    threads = [
        threading.Thread(target=work, args=("web:u1:ws1",)),
        threading.Thread(target=work, args=("web:u1:ws2",)),
        threading.Thread(target=work, args=("telegram:u2:c9",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak["v"] >= 2


def test_gateway_lane_id_web() -> None:
    g = GatewayContext(user_id="web_u", channel="web", extras={"web_session_id": "tab-1"})
    assert gateway_lane_id(g) == "web:web_u:wstab-1"


def test_gateway_lane_id_telegram() -> None:
    g = GatewayContext.from_channel(
        "tg_user",
        "telegram",
        {"telegram_chat_id": "4242"},
    )
    lid = gateway_lane_id(g)
    assert lid.startswith("telegram:tg_user:")
    assert "4242" in lid


def test_gateway_lane_id_discord() -> None:
    g = GatewayContext.from_channel(
        "discord:99",
        "discord",
        {"discord_channel_id": "chan-42"},
    )
    assert gateway_lane_id(g) == "discord:discord:99:cchan-42"


def test_singleton_session_queue_acquire() -> None:
    assert hasattr(session_queue, "acquire")
