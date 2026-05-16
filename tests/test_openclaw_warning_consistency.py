# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resilience / cap warning signals stable under repeated snapshot reads (confidence lock)."""

from __future__ import annotations

import copy

from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot


def test_resilience_slice_stable_under_repeated_snapshots(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    first_res = None
    for _ in range(100):
        snap = build_orchestration_runtime_snapshot("u_warn")
        res = snap.get("resilience") or {}
        assert "integrity_ok" in res
        assert "cap_warnings" in res
        assert isinstance(res["cap_warnings"], list)
        if first_res is None:
            first_res = copy.deepcopy(res)
        else:
            assert res == first_res
