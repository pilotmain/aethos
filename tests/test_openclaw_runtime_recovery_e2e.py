# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.paths import get_runtime_backups_dir
from app.orchestration.orchestrator import orchestration_boot
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_orchestration_boot_cleanup_creates_backup(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    save_runtime_state(st)
    orchestration_boot(st)
    save_runtime_state(st)
    bdir = get_runtime_backups_dir()
    assert bdir.is_dir() and list(bdir.glob("aethos.*.json"))
