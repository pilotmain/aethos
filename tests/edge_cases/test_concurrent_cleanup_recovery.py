# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.deployments.deployment_recovery import recover_deployments_on_boot
from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state
from app.runtime.integrity.runtime_integrity import validate_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


@pytest.mark.edge_cases
def test_interleaved_cleanup_and_recovery(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    for _ in range(12):
        st = load_runtime_state()
        cleanup_runtime_state(st)
        recover_deployments_on_boot(st)
        save_runtime_state(st)
    assert validate_runtime_state(load_runtime_state()).get("ok") is True
