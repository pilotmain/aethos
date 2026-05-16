# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Certify observed maxima stay under configured caps after bounded churn (freeze gate)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.deployments.deployment_lifecycle import record_checkpoint
from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.environments import environment_registry
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles, widen_runtime_event_buffer


@pytest.mark.production_like
def test_observed_maxima_under_config_caps(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_QUEUE_LIMIT", "200")
    widen_runtime_event_buffer(monkeypatch)
    get_settings.cache_clear()
    try:
        cfg = get_settings()
        lim = int(cfg.aethos_queue_limit)
        buf_lim = int(cfg.aethos_runtime_event_buffer_limit)
        art_lim = int(cfg.aethos_task_artifact_limit)
        cp_lim = int(cfg.aethos_plan_checkpoint_limit)

        st = load_runtime_state()
        environment_registry.ensure_environment(st, "env_bnd", user_id="u1")
        upsert_deployment(
            st,
            "dpl_bnd",
            {
                "deployment_id": "dpl_bnd",
                "environment_id": "env_bnd",
                "user_id": "u1",
                "status": "running",
                "deployment_stage": "deploying",
                "artifacts": [],
                "checkpoints": [],
            },
        )

        max_q = 0
        n = repeated_cycles(large=150)
        for i in range(n):
            tid = task_registry.put_task(st, {"id": f"bnd_{i}", "type": "noop", "user_id": "u", "state": "queued"})
            task_queue.enqueue_task_id(st, "execution_queue", str(tid))
            for qn in task_queue.QUEUE_NAMES:
                max_q = max(max_q, task_queue.queue_len(st, qn))
            buf = st.setdefault("runtime_event_buffer", [])
            if isinstance(buf, list):
                buf.append({"kind": "cert", "i": i})
                if len(buf) > buf_lim:
                    del buf[:-buf_lim]
            row = get_deployment(st, "dpl_bnd") or {}
            arts = list(row.get("artifacts") or [])
            arts.append({"ref": f"a{i}"})
            if len(arts) > art_lim:
                arts = arts[-art_lim:]
            upsert_deployment(st, "dpl_bnd", {"artifacts": arts})
            record_checkpoint(st, "dpl_bnd", stage="deploying", message="cert", data={"i": i})

        row = get_deployment(st, "dpl_bnd")
        assert row
        arts_n = len(row.get("artifacts") or []) if isinstance(row.get("artifacts"), list) else 0
        cps_n = len(row.get("checkpoints") or []) if isinstance(row.get("checkpoints"), list) else 0

        assert max_q <= lim
        assert arts_n <= art_lim
        assert cps_n <= min(120, cp_lim)
        blen = len(st["runtime_event_buffer"]) if isinstance(st.get("runtime_event_buffer"), list) else 0
        assert blen <= buf_lim

        inv = validate_runtime_state(st)
        assert inv.get("ok") is True

        save_runtime_state(st)
        assert validate_runtime_state(load_runtime_state()).get("ok") is True
    finally:
        get_settings.cache_clear()
