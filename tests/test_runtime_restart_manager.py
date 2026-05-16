# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_restart_manager import build_runtime_restarts, record_restart_event


def test_restart_history_bounded(monkeypatch) -> None:
    store: dict = {"runtime_restart_history": []}

    def _load():
        return dict(store)

    def _save(st):
        store.update(st)

    monkeypatch.setattr("app.services.mission_control.runtime_restart_manager.load_runtime_state", _load)
    monkeypatch.setattr("app.services.mission_control.runtime_restart_manager.save_runtime_state", _save)
    for i in range(30):
        record_restart_event(f"t{i}", ok=True)
    out = build_runtime_restarts()
    assert len(out["restart_history"]) <= 12
