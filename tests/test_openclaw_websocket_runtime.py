# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import threading
import urllib.parse

from app.main import app
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.services.events.bus import clear_events
from fastapi.testclient import TestClient


def test_websocket_runtime_receive_after_delayed_emit(api_client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    clear_events()
    client, uid = api_client

    def delayed_emit() -> None:
        st = load_runtime_state()
        emit_runtime_event(st, "task_created", task_id="t_ws", user_id=uid, status="queued")
        save_runtime_state(st)

    threading.Timer(0.1, delayed_emit).start()
    q = urllib.parse.quote(uid, safe="")
    with client.websocket_connect(f"/api/v1/runtime/events/ws?user_id={q}") as ws:
        msg = ws.receive_json()
        assert msg.get("type") == "runtime.task_created"
