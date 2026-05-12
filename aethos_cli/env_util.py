# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Merge key=value updates into a ``.env`` file (native setup wizard)."""

from __future__ import annotations

import re
from pathlib import Path


def _fmt_val(v: str) -> str:
    if re.search(r'[\s#]', v) or v != v.strip():
        esc = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{esc}"'
    return v


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    """Insert or replace ``KEY=value`` lines; preserves unrelated lines and order."""
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = raw.splitlines()
    keys_done: set[str] = set()
    key_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")
    out: list[str] = []
    for line in lines:
        m = key_re.match(line.strip())
        if m:
            k = m.group(1)
            if k in updates:
                out.append(f"{k}={_fmt_val(updates[k])}")
                keys_done.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in keys_done:
            out.append(f"{k}={_fmt_val(v)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


__all__ = ["upsert_env_file"]
