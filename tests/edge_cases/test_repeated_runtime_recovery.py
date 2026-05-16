# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.runtime.corruption.runtime_repair import repair_runtime_queues_and_metrics
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

from tests.parity_freeze_gate import repeated_cycles


@pytest.mark.edge_cases
def test_repeated_repair_then_recovery_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    for _ in range(repeated_cycles(large=40)):
        st = load_runtime_state()
        repair_runtime_queues_and_metrics(st)
        recover_deployments_on_boot(st)
        save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
