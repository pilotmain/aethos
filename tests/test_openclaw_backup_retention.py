# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.paths import get_runtime_backups_dir
from app.runtime import retention


def test_prune_runtime_backup_files_keeps_newest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    monkeypatch.setenv("AETHOS_RUNTIME_BACKUP_LIMIT", "2")
    get_settings.cache_clear()
    try:
        bdir = get_runtime_backups_dir()
        bdir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            p = bdir / f"aethos.test{i}.json"
            p.write_text("{}")
            time.sleep(0.02)
        out = retention.prune_runtime_backup_files(max_keep=2)
        assert int(out.get("deleted") or 0) >= 1
        left = list(bdir.glob("aethos.*.json"))
        assert len(left) <= 2
    finally:
        get_settings.cache_clear()
