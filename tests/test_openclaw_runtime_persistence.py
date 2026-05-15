# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent ``aethos.json`` round-trip — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md."""

from __future__ import annotations

from app.runtime.runtime_state import default_runtime_state, load_runtime_state, save_runtime_state


def test_runtime_json_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = default_runtime_state()
    rid = st["runtime_id"]
    st["parity_probe"] = "x"
    save_runtime_state(st)
    got = load_runtime_state()
    assert got["runtime_id"] == rid
    assert got.get("parity_probe") == "x"
