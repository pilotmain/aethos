# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""List timestamped runtime backup files."""

from __future__ import annotations

from pathlib import Path

from app.core.paths import get_runtime_backups_dir


def list_runtime_backup_files(*, limit: int = 50) -> list[dict[str, str | int]]:
    d = get_runtime_backups_dir()
    if not d.is_dir():
        return []
    rows: list[tuple[float, Path]] = []
    for p in d.iterdir():
        if p.is_file() and p.suffix == ".json" and p.name.startswith("aethos."):
            try:
                rows.append((p.stat().st_mtime, p))
            except OSError:
                continue
    rows.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, str | int]] = []
    for _mt, p in rows[: max(1, int(limit))]:
        try:
            sz = int(p.stat().st_size)
        except OSError:
            sz = 0
        out.append({"name": p.name, "path": str(p), "bytes": sz})
    return out
