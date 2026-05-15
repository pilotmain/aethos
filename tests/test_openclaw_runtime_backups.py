# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.core.paths import get_runtime_backups_dir
from app.orchestration import task_registry
from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state


def test_cleanup_writes_timestamped_backup(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    st = load_runtime_state()
    tid = task_registry.put_task(
        st,
        {"type": "workflow", "user_id": "u1", "state": "queued"},
    )
    st.setdefault("execution_queue", []).extend([tid, tid])
    cleanup_runtime_state(st)
    save_runtime_state(st)
    bdir = get_runtime_backups_dir()
    assert bdir.is_dir()
    files = list(bdir.glob("aethos.*.json"))
    assert files, "expected at least one backup JSON under ~/.aethos/backups"
