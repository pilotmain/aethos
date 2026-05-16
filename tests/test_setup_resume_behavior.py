# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json

from app.services.setup.setup_continuity import SETUP_STATE, build_setup_continuity


def test_setup_resume_behavior(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / ".setup_state.json"
    monkeypatch.setattr("app.services.setup.setup_continuity.SETUP_STATE", state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"v": 1, "step": 2, "data": {"kind": "fresh"}}), encoding="utf-8")
    out = build_setup_continuity()
    assert out["setup_continuity"]["resumable"] is True
    assert out["setup_continuity"]["current_step"] == 2
