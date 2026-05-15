# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime heartbeat updates ``gateway.last_heartbeat``."""

from __future__ import annotations

import time

from app.runtime.runtime_heartbeat import start_heartbeat_background, stop_heartbeat_background
from app.runtime.runtime_recovery import boot_prepare_runtime_state
from app.runtime.runtime_state import load_runtime_state


def test_heartbeat_updates_last_heartbeat(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_RUNTIME_HEARTBEAT_TEST_FAST", "1")
    monkeypatch.setenv("AETHOS_RUNTIME_HEARTBEAT_SECONDS", "0.25")
    boot_prepare_runtime_state(host="127.0.0.1", port=8010)
    before = (load_runtime_state().get("gateway") or {}).get("last_heartbeat")
    start_heartbeat_background()
    time.sleep(1.1)
    stop_heartbeat_background()
    after = (load_runtime_state().get("gateway") or {}).get("last_heartbeat")
    assert before and after
    assert after != before
