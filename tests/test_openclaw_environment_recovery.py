# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.environments import environment_registry
from app.environments.environment_recovery import recover_environments_on_boot
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_environment_boot_recovery(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    eid = environment_registry.default_environment_id_for_user(st, "carol")
    environment_registry.ensure_environment(st, eid, user_id="carol")
    em = st.setdefault("environments", {})
    row = em[eid]
    row["status"] = "degraded"
    save_runtime_state(st)
    st2 = load_runtime_state()
    out = recover_environments_on_boot(st2)
    assert out.get("environments_touched", 0) >= 1
    assert (st2.get("environments") or {}).get(eid, {}).get("status") == "recovering"
